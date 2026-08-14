import asyncio
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from app.application.unit_of_work import UnitOfWork
from app.domain.workflow import RunStatus
from app.infrastructure.health import ComponentHealth, ComponentStatus
from app.infrastructure.models.workflow import ProductWorkflow

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def mock_health_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure health checks return deterministic values without real connections."""

    async def mock_ok(*args: Any, **kwargs: Any) -> ComponentHealth:
        return ComponentHealth(status=ComponentStatus.OK, latency_ms=10)

    monkeypatch.setattr("app.application.telegram.check_database", mock_ok)
    monkeypatch.setattr("app.application.telegram.check_redis", mock_ok)
    monkeypatch.setattr("app.application.telegram.check_image_worker", mock_ok)


class TestTelegramSettings:
    async def test_get_telegram_status_unpaired(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/api/v1/settings/telegram")
        assert response.status_code == 200
        body = response.json()
        assert body["paired"] is False
        assert body["telegram_username"] is None
        assert body["pairing_code_expires_at"] is None

    async def test_generate_pairing_code(self, client: httpx.AsyncClient) -> None:
        response = await client.post("/api/v1/settings/telegram/pairing-code")
        assert response.status_code == 200
        body = response.json()
        assert len(body["pairing_code"]) == 6
        assert body["pairing_code"].isdigit()
        assert "expires_at" in body

        # Verify connection status now reflects active pairing code
        status_resp = await client.get("/api/v1/settings/telegram")
        assert status_resp.status_code == 200
        assert status_resp.json()["pairing_code_expires_at"] == body["expires_at"]

    async def test_disconnect_telegram(self, client: httpx.AsyncClient) -> None:
        # Generate code first
        await client.post("/api/v1/settings/telegram/pairing-code")

        # Disconnect
        response = await client.delete("/api/v1/settings/telegram")
        assert response.status_code == 204

        # Verify status is clean
        status_resp = await client.get("/api/v1/settings/telegram")
        assert status_resp.json()["pairing_code_expires_at"] is None


class TestTelegramWebhookCommands:
    async def test_webhook_secret_verification(
        self, anon_client: httpx.AsyncClient, api_app: Any
    ) -> None:
        # Set secret token in app settings config
        settings = api_app.state.settings
        original_secret = settings.telegram_webhook_secret

        try:
            from pydantic import SecretStr

            # Pydantic model bypass:
            settings.__dict__["telegram_webhook_secret"] = SecretStr("testsecret")

            # Request without correct secret token should fail
            response = await anon_client.post(
                "/api/v1/telegram/webhook/wrongsecret",
                json={"update_id": 1},
            )
            assert response.status_code == 403

            # Request with correct secret token should succeed
            response = await anon_client.post(
                "/api/v1/telegram/webhook/testsecret",
                json={"update_id": 1},
            )
            assert response.status_code == 200
        finally:
            settings.__dict__["telegram_webhook_secret"] = original_secret

    async def test_webhook_flow_pairing_and_commands(
        self,
        client: httpx.AsyncClient,
        anon_client: httpx.AsyncClient,
        api_app: Any,
        session_factory: Any,
    ) -> None:
        # Flush Redis db 1 to ensure a clean starting point
        await api_app.state.redis.flushdb()

        # 1. Generate pairing code via settings API
        code_resp = await client.post("/api/v1/settings/telegram/pairing-code")
        code = code_resp.json()["pairing_code"]

        # Dynamic update ID counter to avoid duplicate collisions
        import random

        up_id = random.randint(1000000, 9000000)  # noqa: S311

        # 2. Pair account via Telegram webhook update
        update_payload: dict[str, Any] = {
            "update_id": up_id,
            "message": {
                "message_id": 101,
                "from": {
                    "id": 999888,
                    "username": "test_owner",
                },
                "chat": {
                    "id": 777666,
                    "type": "private",
                },
                "text": code,
            },
        }

        # Clear gateway sent messages
        api_app.state.telegram_gateway.sent_messages.clear()

        # Post update payload to webhook
        response = await anon_client.post("/api/v1/telegram/webhook/none", json=update_payload)
        assert response.status_code == 200

        # Give background tasks time to run
        await asyncio.sleep(0.2)

        # Check pairing confirmation message
        sent = api_app.state.telegram_gateway.sent_messages
        assert len(sent) == 1
        assert "Successfully connected" in sent[0]["text"]

        # Verify pairing in database connection row
        async with UnitOfWork(session_factory) as uow:
            conn = await uow.telegram_connections.get_by_telegram_user_id(999888)
            assert conn is not None
            assert conn.telegram_chat_id == 777666
            assert conn.telegram_username == "test_owner"

        # 3. Test Command: /status
        up_id += 1
        update_payload["update_id"] = up_id
        update_payload["message"]["text"] = "/status"
        sent.clear()

        await anon_client.post("/api/v1/telegram/webhook/none", json=update_payload)
        await asyncio.sleep(0.2)
        assert len(sent) == 1
        assert "Etsy PNG Automation Status" in sent[0]["text"]

        # 4. Test Command: /pause and /resume
        up_id += 1
        update_payload["update_id"] = up_id
        update_payload["message"]["text"] = "/pause"
        sent.clear()

        await anon_client.post("/api/v1/telegram/webhook/none", json=update_payload)
        await asyncio.sleep(0.2)
        assert len(sent) == 1
        assert "PAUSED" in sent[0]["text"]

        async with UnitOfWork(session_factory) as uow:
            conn = await uow.telegram_connections.get_by_telegram_user_id(999888)
            assert conn is not None
            settings_row = await uow.owner_settings.get_for_user(conn.user_id)
            assert settings_row is not None
            assert settings_row.is_paused is True

        up_id += 1
        update_payload["update_id"] = up_id
        update_payload["message"]["text"] = "/resume"
        sent.clear()

        await anon_client.post("/api/v1/telegram/webhook/none", json=update_payload)
        await asyncio.sleep(0.2)
        assert len(sent) == 1
        assert "RESUMED" in sent[0]["text"]

        async with UnitOfWork(session_factory) as uow:
            conn = await uow.telegram_connections.get_by_telegram_user_id(999888)
            assert conn is not None
            settings_row = await uow.owner_settings.get_for_user(conn.user_id)
            assert settings_row is not None
            assert settings_row.is_paused is False

        # 5. Test Command: /jobs
        # Seed a dummy workflow in database
        async with UnitOfWork(session_factory) as uow:
            conn = await uow.telegram_connections.get_by_telegram_user_id(999888)
            assert conn is not None
            wf = ProductWorkflow(
                owner_id=conn.user_id,
                idea_mode="user-idea",
                name="Test Workflow Job",
                target_marketplace="etsy",
                target_country="US",
                output_language="en",
                state=RunStatus.RESEARCHING,
            )
            uow.session.add(wf)
            await uow.commit()
            wf_id = wf.id

        up_id += 1
        update_payload["update_id"] = up_id
        update_payload["message"]["text"] = "/jobs"
        sent.clear()

        await anon_client.post("/api/v1/telegram/webhook/none", json=update_payload)
        await asyncio.sleep(0.2)
        assert len(sent) == 1
        assert "Test Workflow Job" in sent[0]["text"]

        # 6. Test Command: /job <id>
        up_id += 1
        update_payload["update_id"] = up_id
        update_payload["message"]["text"] = f"/job {wf_id}"
        sent.clear()

        await anon_client.post("/api/v1/telegram/webhook/none", json=update_payload)
        await asyncio.sleep(0.2)
        assert len(sent) == 1
        assert "Job Details" in sent[0]["text"]
        assert str(wf_id) in sent[0]["text"]

        # 7. Test Command: /cancel <id>
        up_id += 1
        update_payload["update_id"] = up_id
        update_payload["message"]["text"] = f"/cancel {wf_id}"
        sent.clear()

        await anon_client.post("/api/v1/telegram/webhook/none", json=update_payload)
        await asyncio.sleep(0.2)
        assert len(sent) == 1
        assert "CANCELLED" in sent[0]["text"]

        async with UnitOfWork(session_factory) as uow:
            wf_check = await uow.workflows.get(wf_id)
            assert wf_check is not None
            assert wf_check.state == RunStatus.CANCELLED

        # 8. Test Command: /disconnect
        up_id += 1
        update_payload["update_id"] = up_id
        update_payload["message"]["text"] = "/disconnect"
        sent.clear()

        await anon_client.post("/api/v1/telegram/webhook/none", json=update_payload)
        await asyncio.sleep(0.2)
        assert len(sent) == 1
        assert "disconnected" in sent[0]["text"]

        # Verify not paired anymore
        async with UnitOfWork(session_factory) as uow:
            conn = await uow.telegram_connections.get_by_telegram_user_id(999888)
            assert conn is None

    async def test_webhook_concept_inline_approval(
        self,
        client: httpx.AsyncClient,
        anon_client: httpx.AsyncClient,
        api_app: Any,
        session_factory: Any,
    ) -> None:
        # Flush Redis
        await api_app.state.redis.flushdb()

        # 1. Generate pairing code via settings API
        code_resp = await client.post("/api/v1/settings/telegram/pairing-code")
        code = code_resp.json()["pairing_code"]

        # 2. Pair account
        up_id = 2000000
        update_payload: dict[str, Any] = {
            "update_id": up_id,
            "message": {
                "message_id": 201,
                "from": {"id": 888777, "username": "approver_owner"},
                "chat": {"id": 666555, "type": "private"},
                "text": code,
            },
        }
        api_app.state.telegram_gateway.sent_messages.clear()
        response = await anon_client.post("/api/v1/telegram/webhook/none", json=update_payload)
        assert response.status_code == 200
        await asyncio.sleep(0.2)

        # 3. Create workflow and a product concept inside IDEA_REVIEW state
        from app.infrastructure.models.concept import DesignPrompt, ProductConcept
        async with UnitOfWork(session_factory) as uow:
            conn = await uow.telegram_connections.get_by_telegram_user_id(888777)
            assert conn is not None
            wf = ProductWorkflow(
                owner_id=conn.user_id,
                idea_mode="market-led",
                name="Inline Approval Job",
                target_marketplace="etsy",
                target_country="US",
                output_language="en",
                state=RunStatus.IDEA_REVIEW,
            )
            uow.session.add(wf)
            await uow.session.flush()

            concept = ProductConcept(
                workflow_id=wf.id,
                title="Cute Autumn Cat Mug",
                description="Autumn themed cat illustration mug design.",
                origin="market",
                differentiation="Hand painted watercolor look",
                seasonality="seasonal",
                risk_level="low",
                score=4.5,
                score_breakdown={"demand": 5, "competition": 4},
                status="proposed",
            )
            uow.session.add(concept)
            await uow.session.flush()

            prompt = DesignPrompt(
                concept_id=concept.id,
                version=1,
                positive_prompt="Watercolor cute cat scarf",
                negative_prompt="photorealistic",
                intended_product_uses=["mug"],
            )
            uow.session.add(prompt)
            await uow.commit()
            wf_id = wf.id
            concept_id = concept.id

        # 4. Request job info via /job <id>
        up_id += 1
        update_payload["update_id"] = up_id
        update_payload["message"]["text"] = f"/job {wf_id}"
        api_app.state.telegram_gateway.sent_messages.clear()

        await anon_client.post("/api/v1/telegram/webhook/none", json=update_payload)
        await asyncio.sleep(0.2)

        # Check inline keyboard is returned in details response
        sent = api_app.state.telegram_gateway.sent_messages
        assert len(sent) == 1
        assert "Ranked Concepts (Gate 1):" in sent[0]["text"]
        reply_markup = sent[0].get("reply_markup")
        assert reply_markup is not None
        assert "inline_keyboard" in reply_markup
        inline_buttons = reply_markup["inline_keyboard"]
        assert len(inline_buttons) == 2
        assert inline_buttons[0][0]["text"] == "Approve Concept 1"
        assert inline_buttons[0][0]["callback_data"] == f"approve:{concept_id}:1"

        # 5. Simulate clicking Approve Concept 1 via callback query
        up_id += 1
        callback_payload: dict[str, Any] = {
            "update_id": up_id,
            "callback_query": {
                "id": "query123",
                "from": {"id": 888777, "username": "approver_owner"},
                "message": {
                    "message_id": 202,
                    "chat": {"id": 666555, "type": "private"},
                    "text": "Ranked Concepts (Gate 1):",
                },
                "data": f"approve:{concept_id}:1",
            },
        }
        api_app.state.telegram_gateway.sent_messages.clear()

        response = await anon_client.post("/api/v1/telegram/webhook/none", json=callback_payload)
        assert response.status_code == 200
        await asyncio.sleep(0.2)

        # Assert approval success message is sent
        sent = api_app.state.telegram_gateway.sent_messages
        assert len(sent) == 1
        assert "approved successfully" in sent[0]["text"]

        # Verify state in DB transitioned to IDEA_APPROVED
        async with UnitOfWork(session_factory) as uow:
            wf_check = await uow.workflows.get(wf_id)
            assert wf_check is not None
            assert wf_check.state == RunStatus.IDEA_APPROVED


class TestTelegramSecurityAndValidation:
    async def test_help_command_html_validation(self, session_factory: Any, api_app: Any) -> None:
        import re

        from app.application.telegram import handle_telegram_command

        async with UnitOfWork(session_factory) as uow:
            # We don't need a paired user for /help since it is allowed anonymously
            response = await handle_telegram_command(
                uow=uow,
                redis=api_app.state.redis,
                http_client=api_app.state.http_client,
                engine=api_app.state.engine,
                settings=api_app.state.settings,
                telegram_gateway=api_app.state.telegram_gateway,
                telegram_user_id=12345,
                telegram_chat_id=12345,
                telegram_username="test",
                text="/help",
                now=datetime.now(UTC),
            )

        # All tags must be valid Telegram HTML: <b>, </b>, <code>, </code> etc.
        # Find all occurrences of '<' in the text
        tags = re.findall(r"<([^>]+)>", response)
        valid_tags = {"b", "/b", "code", "/code", "i", "/i", "strong", "/strong"}
        for tag in tags:
            # Ensure it is a valid tag and NOT a raw placeholder like <id> or <job_id>
            tag_name = tag.split()[0]
            assert tag_name in valid_tags, f"Invalid HTML tag or raw placeholder found: <{tag}>"

    async def test_bot_token_redaction_in_errors(self) -> None:
        from app.ports.errors import ProviderError
        from app.providers.telegram import RealTelegramGateway

        bot_token = "123456:SECRET_BOT_TOKEN_STRING"

        def mock_raise(request: httpx.Request) -> httpx.Response:
            raise httpx.RequestError(f"Connection failed for {request.url}", request=request)

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_raise))
        gateway = RealTelegramGateway(bot_token, mock_client)

        with pytest.raises(ProviderError) as exc_info:
            await gateway.send_message(chat_id=12345, text="Hello")

        # The raw secret bot token must NOT appear in the exception representation or message
        error_msg = str(exc_info.value)
        assert bot_token not in error_msg
        assert "[REDACTED_TELEGRAM_TOKEN]" in error_msg

        # Verify no traceback context is chained that contains the token (due to raise from None)
        assert exc_info.value.__cause__ is None

    def test_bot_token_redaction_in_logs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.infrastructure.logging import redact_secrets

        bot_token = "123456:SECRET_BOT_TOKEN_STRING"
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", bot_token)

        # Emulate log message
        log_event = {
            "event": f"Connecting to URL https://api.telegram.org/bot{bot_token}/sendMessage",
            "nested": {
                "url": f"https://api.telegram.org/bot{bot_token}/getUpdates",
                "auth": f"Bearer {bot_token}",
            },
            "list_field": [f"token:{bot_token}"],
        }

        redacted = redact_secrets(None, "info", log_event)

        # Assert token is completely scrubbed from all fields
        assert bot_token not in redacted["event"]
        assert "[REDACTED_TELEGRAM_TOKEN]" in redacted["event"]
        assert bot_token not in redacted["nested"]["url"]
        assert "[REDACTED_TELEGRAM_TOKEN]" in redacted["nested"]["url"]
        assert bot_token not in redacted["nested"]["auth"]
        assert "[REDACTED_TELEGRAM_TOKEN]" in redacted["nested"]["auth"]
        assert bot_token not in redacted["list_field"][0]
        assert "[REDACTED_TELEGRAM_TOKEN]" in redacted["list_field"][0]
