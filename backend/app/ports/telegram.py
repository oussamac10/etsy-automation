from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class TelegramGateway(Protocol):
    """Port for communicating with the Telegram Bot API."""

    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str = "HTML",
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        """Send a text message to a chat."""
        ...

    async def get_updates(
        self,
        offset: int | None = None,
        timeout: int = 30,  # noqa: ASYNC109 - Telegram's long-poll timeout, not a client deadline
    ) -> list[dict[str, Any]]:
        """Fetch pending updates (for long polling)."""
        ...

    async def set_webhook(self, url: str, secret_token: str | None = None) -> None:
        """Set or remove (if url is empty) the webhook endpoint."""
        ...
