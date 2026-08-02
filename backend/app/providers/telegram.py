from __future__ import annotations

from typing import Any

import httpx

from app.ports.errors import ProviderError, ProviderErrorKind
from app.ports.telegram import TelegramGateway


def escape_html(text: str) -> str:
    """Escape text for Telegram HTML parse mode."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class RealTelegramGateway(TelegramGateway):
    """Communicates with the live Telegram Bot API."""

    def __init__(self, bot_token: str, http_client: httpx.AsyncClient) -> None:
        self._bot_token = bot_token
        self._http_client = http_client
        self._base_url = f"https://api.telegram.org/bot{bot_token}"

    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str = "HTML",
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        url = f"{self._base_url}/sendMessage"
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            response = await self._http_client.post(url, json=payload)
            if response.status_code == 429:
                retry_after = 5.0
                import contextlib

                with contextlib.suppress(Exception):
                    params = response.json().get("parameters", {})
                    retry_after = float(params.get("retry_after", 5.0))
                raise ProviderError(
                    kind=ProviderErrorKind.RATE_LIMITED,
                    provider="telegram",
                    operation="send_message",
                    message="Telegram rate limit exceeded",
                    retry_after_seconds=retry_after,
                )
            elif response.status_code in (401, 403):
                raise ProviderError(
                    kind=ProviderErrorKind.AUTHENTICATION,
                    provider="telegram",
                    operation="send_message",
                    message=f"Telegram authorization failed: {response.text}",
                )
            elif response.status_code >= 400:
                raise ProviderError(
                    kind=ProviderErrorKind.INVALID_REQUEST,
                    provider="telegram",
                    operation="send_message",
                    message=f"Telegram returned error: {response.text}",
                )
        except httpx.RequestError as exc:
            raise ProviderError(
                kind=ProviderErrorKind.RETRYABLE,
                provider="telegram",
                operation="send_message",
                message=f"Network error: {exc}",
            ) from exc

    async def get_updates(
        self, offset: int | None = None, timeout: int = 30
    ) -> list[dict[str, Any]]:  # noqa: ASYNC109
        url = f"{self._base_url}/getUpdates"
        payload: dict[str, Any] = {"timeout": timeout}
        if offset is not None:
            payload["offset"] = offset

        try:
            response = await self._http_client.post(url, json=payload, timeout=timeout + 5.0)
            if response.status_code >= 400:
                raise ProviderError(
                    kind=ProviderErrorKind.INVALID_REQUEST,
                    provider="telegram",
                    operation="get_updates",
                    message=f"Telegram returned error: {response.text}",
                )
            data = response.json()
            if not data.get("ok"):
                raise ProviderError(
                    kind=ProviderErrorKind.INVALID_REQUEST,
                    provider="telegram",
                    operation="get_updates",
                    message=f"Telegram API response ok=False: {data}",
                )
            result = data.get("result")
            if not isinstance(result, list):
                result = []
            return result
        except httpx.RequestError as exc:
            raise ProviderError(
                kind=ProviderErrorKind.RETRYABLE,
                provider="telegram",
                operation="get_updates",
                message=f"Network error: {exc}",
            ) from exc

    async def set_webhook(self, url: str, secret_token: str | None = None) -> None:
        api_url = f"{self._base_url}/setWebhook"
        payload = {"url": url}
        if secret_token:
            payload["secret_token"] = secret_token

        try:
            response = await self._http_client.post(api_url, json=payload)
            if response.status_code >= 400:
                raise ProviderError(
                    kind=ProviderErrorKind.INVALID_REQUEST,
                    provider="telegram",
                    operation="set_webhook",
                    message=f"Telegram returned error: {response.text}",
                )
        except httpx.RequestError as exc:
            raise ProviderError(
                kind=ProviderErrorKind.RETRYABLE,
                provider="telegram",
                operation="set_webhook",
                message=f"Network error: {exc}",
            ) from exc


class FakeTelegramGateway(TelegramGateway):
    """In-memory gateway for testing and local development without keys."""

    def __init__(self) -> None:
        self.sent_messages: list[dict[str, Any]] = []
        self.mock_updates: list[dict[str, Any]] = []
        self.webhook_url: str | None = None
        self.webhook_secret: str | None = None

    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str = "HTML",
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        self.sent_messages.append(
            {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "reply_markup": reply_markup,
            }
        )

    async def get_updates(
        self, offset: int | None = None, timeout: int = 30
    ) -> list[dict[str, Any]]:  # noqa: ASYNC109
        if offset is None:
            return self.mock_updates
        result = [u for u in self.mock_updates if u.get("update_id", 0) >= offset]
        return result

    async def set_webhook(self, url: str, secret_token: str | None = None) -> None:
        self.webhook_url = url
        self.webhook_secret = secret_token
