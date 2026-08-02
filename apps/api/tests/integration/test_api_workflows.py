"""Workflow endpoints against a real database.

These use ``ASGITransport`` rather than ``TestClient`` so the app's own lifespan
is skipped and the session factory can be pointed at the test database.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.unit_of_work import UnitOfWork
from app.domain.enums import IdeaMode
from app.domain.workflow import ApprovalDecision, ApprovalGate, RunStatus
from app.main import create_app
from app.settings import Settings

pytestmark = pytest.mark.integration


@pytest.fixture
async def client(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(settings)
    app.state.session_factory = session_factory
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client


@pytest.fixture
async def owner_id(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> uuid.UUID:
    async with UnitOfWork(session_factory) as uow:
        user = await uow.users.add(email="api@example.invalid", display_name="API Owner")
        await uow.commit()
        return user.id


def _payload(owner_id: uuid.UUID, mode: IdeaMode = IdeaMode.USER_IDEA) -> dict[str, object]:
    return {
        "owner_id": str(owner_id),
        "idea_mode": mode.value,
        "name": "Test workflow",
        "target_country": "US",
        "output_language": "en",
        "intended_product_uses": ["mug"],
    }


class TestCreateWorkflow:
    @pytest.mark.parametrize("mode", list(IdeaMode))
    async def test_creates_in_every_idea_mode(
        self, client: httpx.AsyncClient, owner_id: uuid.UUID, mode: IdeaMode
    ) -> None:
        response = await client.post("/api/v1/workflows", json=_payload(owner_id, mode))
        assert response.status_code == 201
        body = response.json()
        assert body["idea_mode"] == mode.value
        assert body["state"] == RunStatus.DRAFT.value
        assert body["version"] == 1
        assert response.headers["Location"].endswith(body["id"])

    async def test_unknown_owner_returns_404(self, client: httpx.AsyncClient) -> None:
        response = await client.post("/api/v1/workflows", json=_payload(uuid.uuid4()))
        assert response.status_code == 404
        assert response.headers["content-type"].startswith("application/problem+json")
        assert response.json()["type"].endswith("/not-found")

    async def test_unknown_idea_mode_is_rejected(
        self, client: httpx.AsyncClient, owner_id: uuid.UUID
    ) -> None:
        payload = _payload(owner_id)
        payload["idea_mode"] = "vibes-based"
        response = await client.post("/api/v1/workflows", json=payload)
        assert response.status_code == 422

    async def test_extra_fields_are_rejected(
        self, client: httpx.AsyncClient, owner_id: uuid.UUID
    ) -> None:
        payload = _payload(owner_id)
        payload["is_admin"] = True
        response = await client.post("/api/v1/workflows", json=payload)
        assert response.status_code == 422

    async def test_blank_name_is_rejected(
        self, client: httpx.AsyncClient, owner_id: uuid.UUID
    ) -> None:
        payload = _payload(owner_id)
        payload["name"] = "   "
        response = await client.post("/api/v1/workflows", json=payload)
        assert response.status_code == 422

    async def test_bad_country_code_is_rejected(
        self, client: httpx.AsyncClient, owner_id: uuid.UUID
    ) -> None:
        payload = _payload(owner_id)
        payload["target_country"] = "USA"
        response = await client.post("/api/v1/workflows", json=payload)
        assert response.status_code == 422
        assert response.json()["type"].endswith("/validation-error")


class TestReadWorkflows:
    async def test_get_by_id(self, client: httpx.AsyncClient, owner_id: uuid.UUID) -> None:
        created = (await client.post("/api/v1/workflows", json=_payload(owner_id))).json()
        response = await client.get(f"/api/v1/workflows/{created['id']}")
        assert response.status_code == 200
        assert response.json()["id"] == created["id"]

    async def test_unknown_id_returns_404(self, client: httpx.AsyncClient) -> None:
        response = await client.get(f"/api/v1/workflows/{uuid.uuid4()}")
        assert response.status_code == 404

    async def test_malformed_id_returns_422(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/api/v1/workflows/not-a-uuid")
        assert response.status_code == 422

    async def test_list_paginates(self, client: httpx.AsyncClient, owner_id: uuid.UUID) -> None:
        for _ in range(3):
            await client.post("/api/v1/workflows", json=_payload(owner_id))
        response = await client.get("/api/v1/workflows", params={"limit": 2})
        body = response.json()
        assert response.status_code == 200
        assert len(body["items"]) == 2
        assert body["total"] == 3
        assert body["limit"] == 2

    async def test_list_filters_by_state(
        self, client: httpx.AsyncClient, owner_id: uuid.UUID
    ) -> None:
        await client.post("/api/v1/workflows", json=_payload(owner_id))
        response = await client.get(
            "/api/v1/workflows", params={"state": RunStatus.PRODUCTION.value}
        )
        assert response.json()["total"] == 0


class TestSubmitIdea:
    async def test_stores_the_owner_text_verbatim(
        self, client: httpx.AsyncClient, owner_id: uuid.UUID
    ) -> None:
        workflow = (await client.post("/api/v1/workflows", json=_payload(owner_id))).json()
        original = (
            "A hand-drawn sleepy fox curled around a steaming mug — cosy, "
            "not cute-cartoon. Don't make it twee."
        )
        response = await client.post(
            f"/api/v1/workflows/{workflow['id']}/ideas",
            json={"original_text": original, "slogan": "Slow Mornings"},
        )
        assert response.status_code == 201
        # Character for character, including the dash and the apostrophe.
        assert response.json()["original_text"] == original

        fetched = await client.get(f"/api/v1/workflows/{workflow['id']}/ideas")
        assert fetched.json()["original_text"] == original

    async def test_market_led_refuses_an_idea(
        self, client: httpx.AsyncClient, owner_id: uuid.UUID
    ) -> None:
        workflow = (
            await client.post("/api/v1/workflows", json=_payload(owner_id, IdeaMode.MARKET_LED))
        ).json()
        response = await client.post(
            f"/api/v1/workflows/{workflow['id']}/ideas",
            json={"original_text": "I have an idea after all"},
        )
        assert response.status_code == 422
        assert response.json()["type"].endswith("/invalid-idea-mode")

    async def test_a_refused_submission_leaves_no_trace(
        self,
        client: httpx.AsyncClient,
        session_factory: async_sessionmaker[AsyncSession],
        owner_id: uuid.UUID,
    ) -> None:
        """The request's unit of work is rolled back, not half-written.

        The route no longer opens the transaction itself, so this is the
        end-to-end proof that the dependency still rolls back on the way out.
        """
        workflow = (
            await client.post("/api/v1/workflows", json=_payload(owner_id, IdeaMode.MARKET_LED))
        ).json()
        workflow_id = uuid.UUID(workflow["id"])

        async with UnitOfWork(session_factory) as uow:
            events_before = len(await uow.audit.for_workflow(workflow_id))

        assert (
            await client.post(
                f"/api/v1/workflows/{workflow_id}/ideas",
                json={"original_text": "I have an idea after all"},
            )
        ).status_code == 422

        async with UnitOfWork(session_factory) as uow:
            assert await uow.ideas.get_for_workflow(workflow_id) is None
            # No audit row either: the refusal is not a thing that happened to
            # the workflow, and a partial write would say it was.
            assert len(await uow.audit.for_workflow(workflow_id)) == events_before

    async def test_second_submission_is_a_conflict(
        self, client: httpx.AsyncClient, owner_id: uuid.UUID
    ) -> None:
        workflow = (await client.post("/api/v1/workflows", json=_payload(owner_id))).json()
        body = {"original_text": "The first thing I said"}
        assert (
            await client.post(f"/api/v1/workflows/{workflow['id']}/ideas", json=body)
        ).status_code == 201

        response = await client.post(
            f"/api/v1/workflows/{workflow['id']}/ideas",
            json={"original_text": "A completely different thing"},
        )
        assert response.status_code == 409
        assert response.json()["type"].endswith("/immutable-field")

        # And the first text is still what comes back.
        fetched = await client.get(f"/api/v1/workflows/{workflow['id']}/ideas")
        assert fetched.json()["original_text"] == "The first thing I said"

    async def test_idea_for_unknown_workflow_returns_404(self, client: httpx.AsyncClient) -> None:
        response = await client.post(
            f"/api/v1/workflows/{uuid.uuid4()}/ideas",
            json={"original_text": "Some idea"},
        )
        assert response.status_code == 404

    async def test_too_short_idea_is_rejected(
        self, client: httpx.AsyncClient, owner_id: uuid.UUID
    ) -> None:
        workflow = (await client.post("/api/v1/workflows", json=_payload(owner_id))).json()
        response = await client.post(
            f"/api/v1/workflows/{workflow['id']}/ideas", json={"original_text": "no"}
        )
        assert response.status_code == 422

    async def test_missing_idea_returns_404(
        self, client: httpx.AsyncClient, owner_id: uuid.UUID
    ) -> None:
        workflow = (await client.post("/api/v1/workflows", json=_payload(owner_id))).json()
        response = await client.get(f"/api/v1/workflows/{workflow['id']}/ideas")
        assert response.status_code == 404


class TestGates:
    async def _at_idea_gate(
        self,
        client: httpx.AsyncClient,
        session_factory: async_sessionmaker[AsyncSession],
        owner_id: uuid.UUID,
    ) -> str:
        workflow = (await client.post("/api/v1/workflows", json=_payload(owner_id))).json()
        async with UnitOfWork(session_factory) as uow:
            entity = await uow.workflows.get(uuid.UUID(workflow["id"]))
            assert entity is not None
            for to_state in (
                RunStatus.RESEARCH_QUEUED,
                RunStatus.RESEARCHING,
                RunStatus.IDEA_REVIEW,
            ):
                await uow.workflows.transition(
                    entity,
                    to_state=to_state,
                    expected_version=entity.version,
                    reason="test",
                )
            await uow.commit()
        return str(workflow["id"])

    async def test_approval_advances_the_workflow(
        self,
        client: httpx.AsyncClient,
        session_factory: async_sessionmaker[AsyncSession],
        owner_id: uuid.UUID,
    ) -> None:
        workflow_id = await self._at_idea_gate(client, session_factory, owner_id)
        response = await client.post(
            f"/api/v1/workflows/{workflow_id}/approvals",
            json={
                "gate": ApprovalGate.IDEA_APPROVAL.value,
                "decision": ApprovalDecision.APPROVED.value,
                "actor": "owner",
            },
        )
        assert response.status_code == 201
        assert response.json()["resulting_state"] == RunStatus.IDEA_APPROVED.value

        current = await client.get(f"/api/v1/workflows/{workflow_id}")
        assert current.json()["state"] == RunStatus.IDEA_APPROVED.value

    async def test_deciding_the_wrong_gate_is_a_conflict(
        self,
        client: httpx.AsyncClient,
        session_factory: async_sessionmaker[AsyncSession],
        owner_id: uuid.UUID,
    ) -> None:
        workflow_id = await self._at_idea_gate(client, session_factory, owner_id)
        response = await client.post(
            f"/api/v1/workflows/{workflow_id}/approvals",
            json={
                "gate": ApprovalGate.LISTING_APPROVAL.value,
                "decision": ApprovalDecision.APPROVED.value,
            },
        )
        assert response.status_code == 409
        assert response.json()["type"].endswith("/gate-not-satisfied")
        assert response.json()["gate"] == ApprovalGate.LISTING_APPROVAL.value

    async def test_gate_on_a_draft_workflow_is_a_conflict(
        self, client: httpx.AsyncClient, owner_id: uuid.UUID
    ) -> None:
        workflow = (await client.post("/api/v1/workflows", json=_payload(owner_id))).json()
        response = await client.post(
            f"/api/v1/workflows/{workflow['id']}/approvals",
            json={
                "gate": ApprovalGate.IDEA_APPROVAL.value,
                "decision": ApprovalDecision.APPROVED.value,
            },
        )
        assert response.status_code == 409

    async def test_rejection_moves_back_and_is_kept(
        self,
        client: httpx.AsyncClient,
        session_factory: async_sessionmaker[AsyncSession],
        owner_id: uuid.UUID,
    ) -> None:
        workflow_id = await self._at_idea_gate(client, session_factory, owner_id)
        await client.post(
            f"/api/v1/workflows/{workflow_id}/approvals",
            json={
                "gate": ApprovalGate.IDEA_APPROVAL.value,
                "decision": ApprovalDecision.REJECTED.value,
                "comment": "Not this one",
            },
        )
        current = await client.get(f"/api/v1/workflows/{workflow_id}")
        assert current.json()["state"] == RunStatus.DRAFT.value

        timeline = (await client.get(f"/api/v1/workflows/{workflow_id}/timeline")).json()
        approvals = [e for e in timeline["entries"] if e["kind"] == "approval"]
        assert len(approvals) == 1
        assert approvals[0]["detail"]["decision"] == ApprovalDecision.REJECTED.value


class TestTimeline:
    async def test_timeline_tells_the_whole_story(
        self, client: httpx.AsyncClient, owner_id: uuid.UUID
    ) -> None:
        workflow = (await client.post("/api/v1/workflows", json=_payload(owner_id))).json()
        await client.post(
            f"/api/v1/workflows/{workflow['id']}/ideas",
            json={"original_text": "The owner's original words"},
        )

        response = await client.get(f"/api/v1/workflows/{workflow['id']}/timeline")
        assert response.status_code == 200
        body = response.json()
        assert body["state"] == RunStatus.DRAFT.value

        kinds = {entry["kind"] for entry in body["entries"]}
        assert "transition" in kinds
        assert "audit" in kinds

    async def test_timeline_for_unknown_workflow_returns_404(
        self, client: httpx.AsyncClient
    ) -> None:
        response = await client.get(f"/api/v1/workflows/{uuid.uuid4()}/timeline")
        assert response.status_code == 404

    async def test_timeline_never_contains_a_secret(
        self, client: httpx.AsyncClient, owner_id: uuid.UUID
    ) -> None:
        workflow = (await client.post("/api/v1/workflows", json=_payload(owner_id))).json()
        response = await client.get(f"/api/v1/workflows/{workflow['id']}/timeline")
        for forbidden in ("password", "secret_key", "api_key", "token"):
            assert forbidden not in response.text.lower()
