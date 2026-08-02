"""Workflow endpoints against a real database.

These use ``ASGITransport`` rather than ``TestClient`` so the app's own lifespan
is skipped and the session factory can be pointed at the test database.

Since Phase 3 every route requires a session. ``client`` (from ``conftest``) is
signed in as the first owner; ``other_client`` is a second, unrelated owner and
``anon_client`` is not signed in at all.
"""

from __future__ import annotations

import uuid

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.unit_of_work import UnitOfWork
from app.domain.enums import IdeaMode
from app.domain.workflow import ApprovalDecision, ApprovalGate, RunStatus

from .conftest import OWNER_EMAIL

pytestmark = pytest.mark.integration


def _payload(mode: IdeaMode = IdeaMode.USER_IDEA) -> dict[str, object]:
    """No ``owner_id``: the API takes ownership from the session."""
    return {
        "idea_mode": mode.value,
        "name": "Test workflow",
        "target_country": "US",
        "output_language": "en",
        "intended_product_uses": ["mug"],
    }


class TestCreateWorkflow:
    @pytest.mark.parametrize("mode", list(IdeaMode))
    async def test_creates_in_every_idea_mode(
        self, client: httpx.AsyncClient, mode: IdeaMode
    ) -> None:
        response = await client.post("/api/v1/workflows", json=_payload(mode))
        assert response.status_code == 201
        body = response.json()
        assert body["idea_mode"] == mode.value
        assert body["state"] == RunStatus.DRAFT.value
        assert body["version"] == 1
        assert response.headers["Location"].endswith(body["id"])

    async def test_the_owner_comes_from_the_session(
        self, client: httpx.AsyncClient, accounts: dict[str, uuid.UUID]
    ) -> None:
        """Not from the body. A client cannot create a workflow for someone else."""
        response = await client.post("/api/v1/workflows", json=_payload())
        assert response.json()["owner_id"] == str(accounts["owner"])

    async def test_a_client_supplied_owner_id_is_refused(
        self, client: httpx.AsyncClient, accounts: dict[str, uuid.UUID]
    ) -> None:
        payload = _payload() | {"owner_id": str(accounts["other"])}
        response = await client.post("/api/v1/workflows", json=payload)
        assert response.status_code == 422

    async def test_unauthenticated_creation_is_refused(
        self, anon_client: httpx.AsyncClient
    ) -> None:
        response = await anon_client.post("/api/v1/workflows", json=_payload())
        assert response.status_code == 401
        assert response.headers["content-type"].startswith("application/problem+json")
        assert response.json()["type"].endswith("/not-authenticated")

    async def test_unknown_idea_mode_is_rejected(self, client: httpx.AsyncClient) -> None:
        payload = _payload()
        payload["idea_mode"] = "vibes-based"
        response = await client.post("/api/v1/workflows", json=payload)
        assert response.status_code == 422

    async def test_extra_fields_are_rejected(self, client: httpx.AsyncClient) -> None:
        payload = _payload()
        payload["is_admin"] = True
        response = await client.post("/api/v1/workflows", json=payload)
        assert response.status_code == 422

    async def test_blank_name_is_rejected(self, client: httpx.AsyncClient) -> None:
        payload = _payload()
        payload["name"] = "   "
        response = await client.post("/api/v1/workflows", json=payload)
        assert response.status_code == 422

    async def test_bad_country_code_is_rejected(self, client: httpx.AsyncClient) -> None:
        payload = _payload()
        payload["target_country"] = "USA"
        response = await client.post("/api/v1/workflows", json=payload)
        assert response.status_code == 422
        assert response.json()["type"].endswith("/validation-error")


class TestReadWorkflows:
    async def test_get_by_id(self, client: httpx.AsyncClient) -> None:
        created = (await client.post("/api/v1/workflows", json=_payload())).json()
        response = await client.get(f"/api/v1/workflows/{created['id']}")
        assert response.status_code == 200
        assert response.json()["id"] == created["id"]

    async def test_unknown_id_returns_404(self, client: httpx.AsyncClient) -> None:
        response = await client.get(f"/api/v1/workflows/{uuid.uuid4()}")
        assert response.status_code == 404

    async def test_malformed_id_returns_422(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/api/v1/workflows/not-a-uuid")
        assert response.status_code == 422

    async def test_list_paginates(self, client: httpx.AsyncClient) -> None:
        for _ in range(3):
            await client.post("/api/v1/workflows", json=_payload())
        response = await client.get("/api/v1/workflows", params={"limit": 2})
        body = response.json()
        assert response.status_code == 200
        assert len(body["items"]) == 2
        assert body["total"] == 3
        assert body["limit"] == 2

    async def test_list_filters_by_state(self, client: httpx.AsyncClient) -> None:
        await client.post("/api/v1/workflows", json=_payload())
        response = await client.get(
            "/api/v1/workflows", params={"state": RunStatus.PRODUCTION.value}
        )
        assert response.json()["total"] == 0


class TestSubmitIdea:
    async def test_stores_the_owner_text_verbatim(self, client: httpx.AsyncClient) -> None:
        workflow = (await client.post("/api/v1/workflows", json=_payload())).json()
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

    async def test_market_led_refuses_an_idea(self, client: httpx.AsyncClient) -> None:
        workflow = (
            await client.post("/api/v1/workflows", json=_payload(IdeaMode.MARKET_LED))
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
    ) -> None:
        """The request's unit of work is rolled back, not half-written.

        The route no longer opens the transaction itself, so this is the
        end-to-end proof that the dependency still rolls back on the way out.
        """
        workflow = (
            await client.post("/api/v1/workflows", json=_payload(IdeaMode.MARKET_LED))
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

    async def test_second_submission_is_a_conflict(self, client: httpx.AsyncClient) -> None:
        workflow = (await client.post("/api/v1/workflows", json=_payload())).json()
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

    async def test_too_short_idea_is_rejected(self, client: httpx.AsyncClient) -> None:
        workflow = (await client.post("/api/v1/workflows", json=_payload())).json()
        response = await client.post(
            f"/api/v1/workflows/{workflow['id']}/ideas", json={"original_text": "no"}
        )
        assert response.status_code == 422

    async def test_missing_idea_returns_404(self, client: httpx.AsyncClient) -> None:
        workflow = (await client.post("/api/v1/workflows", json=_payload())).json()
        response = await client.get(f"/api/v1/workflows/{workflow['id']}/ideas")
        assert response.status_code == 404


class TestGates:
    async def _at_idea_gate(
        self,
        client: httpx.AsyncClient,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> str:
        workflow = (await client.post("/api/v1/workflows", json=_payload())).json()
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
    ) -> None:
        workflow_id = await self._at_idea_gate(client, session_factory)
        response = await client.post(
            f"/api/v1/workflows/{workflow_id}/approvals",
            json={
                "gate": ApprovalGate.IDEA_APPROVAL.value,
                "decision": ApprovalDecision.APPROVED.value,
            },
        )
        assert response.status_code == 201
        assert response.json()["resulting_state"] == RunStatus.IDEA_APPROVED.value
        # The name on the gate evidence comes from the session.
        assert response.json()["actor"] == OWNER_EMAIL

        current = await client.get(f"/api/v1/workflows/{workflow_id}")
        assert current.json()["state"] == RunStatus.IDEA_APPROVED.value

    async def test_the_approving_actor_cannot_be_chosen_by_the_client(
        self,
        client: httpx.AsyncClient,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """An approval is evidence a human decided; the body may not name them."""
        workflow_id = await self._at_idea_gate(client, session_factory)
        response = await client.post(
            f"/api/v1/workflows/{workflow_id}/approvals",
            json={
                "gate": ApprovalGate.IDEA_APPROVAL.value,
                "decision": ApprovalDecision.APPROVED.value,
                "actor": "someone-else@example.invalid",
            },
        )
        assert response.status_code == 422

    async def test_deciding_the_wrong_gate_is_a_conflict(
        self,
        client: httpx.AsyncClient,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        workflow_id = await self._at_idea_gate(client, session_factory)
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

    async def test_gate_on_a_draft_workflow_is_a_conflict(self, client: httpx.AsyncClient) -> None:
        workflow = (await client.post("/api/v1/workflows", json=_payload())).json()
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
    ) -> None:
        workflow_id = await self._at_idea_gate(client, session_factory)
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
    async def test_timeline_tells_the_whole_story(self, client: httpx.AsyncClient) -> None:
        workflow = (await client.post("/api/v1/workflows", json=_payload())).json()
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

    async def test_timeline_never_contains_a_secret(self, client: httpx.AsyncClient) -> None:
        workflow = (await client.post("/api/v1/workflows", json=_payload())).json()
        response = await client.get(f"/api/v1/workflows/{workflow['id']}/timeline")
        for forbidden in ("password", "secret_key", "api_key", "token"):
            assert forbidden not in response.text.lower()


class TestOwnershipIsolation:
    """One owner's workflow is invisible to another owner, on every route.

    Cross-owner access answers 404, not 403: a 403 would confirm the ID exists.
    See ``docs/authentication-and-secrets.md``.
    """

    async def _owned_by_other(self, other_client: httpx.AsyncClient) -> str:
        created = await other_client.post("/api/v1/workflows", json=_payload())
        assert created.status_code == 201
        return str(created.json()["id"])

    async def test_list_shows_only_your_own(
        self, client: httpx.AsyncClient, other_client: httpx.AsyncClient
    ) -> None:
        await self._owned_by_other(other_client)
        mine = (await client.post("/api/v1/workflows", json=_payload())).json()

        listed = (await client.get("/api/v1/workflows")).json()
        assert [item["id"] for item in listed["items"]] == [mine["id"]]
        assert listed["total"] == 1

    async def test_reading_another_owners_workflow_is_a_404(
        self, client: httpx.AsyncClient, other_client: httpx.AsyncClient
    ) -> None:
        foreign = await self._owned_by_other(other_client)
        unknown_id = uuid.uuid4()
        response = await client.get(f"/api/v1/workflows/{foreign}")
        unknown = await client.get(f"/api/v1/workflows/{unknown_id}")

        assert response.status_code == unknown.status_code == 404

        def _shape(payload: dict[str, object], entity_id: str) -> dict[str, object]:
            # Correlation ID and instance path differ per request by design.
            body = {k: v for k, v in payload.items() if k not in {"correlation_id", "instance"}}
            return {k: (str(v).replace(entity_id, "X")) for k, v in body.items()}

        # Identical once the ID is normalised: a workflow that belongs to
        # someone else must look exactly like one that was never created.
        assert _shape(response.json(), foreign) == _shape(unknown.json(), str(unknown_id))

    async def test_every_nested_route_is_scoped(
        self, client: httpx.AsyncClient, other_client: httpx.AsyncClient
    ) -> None:
        foreign = await self._owned_by_other(other_client)

        assert (await client.get(f"/api/v1/workflows/{foreign}/timeline")).status_code == 404
        assert (await client.get(f"/api/v1/workflows/{foreign}/ideas")).status_code == 404
        assert (
            await client.post(
                f"/api/v1/workflows/{foreign}/ideas",
                json={"original_text": "Trying to write into someone else's workflow"},
            )
        ).status_code == 404
        assert (
            await client.post(
                f"/api/v1/workflows/{foreign}/approvals",
                json={
                    "gate": ApprovalGate.IDEA_APPROVAL.value,
                    "decision": ApprovalDecision.APPROVED.value,
                },
            )
        ).status_code == 404

    async def test_a_refused_cross_owner_write_changes_nothing(
        self,
        client: httpx.AsyncClient,
        other_client: httpx.AsyncClient,
    ) -> None:
        foreign = await self._owned_by_other(other_client)
        await client.post(f"/api/v1/workflows/{foreign}/ideas", json={"original_text": "Not yours"})
        # The real owner still sees no idea at all.
        assert (await other_client.get(f"/api/v1/workflows/{foreign}/ideas")).status_code == 404
