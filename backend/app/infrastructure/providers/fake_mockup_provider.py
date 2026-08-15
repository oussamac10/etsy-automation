"""Deterministic FakeMockupProvider for testing and offline local development.

Produces valid simulated mockup images and mimics the Printful async task lifecycle
without network dependency.
"""

from __future__ import annotations

import io
import uuid
from typing import Any

from app.infrastructure.mockup_catalog import get_product_config
from app.ports.errors import ProviderError, ProviderErrorKind
from app.ports.mockup_provider import MockupProvider, MockupTaskResult

try:
    from PIL import Image, ImageDraw  # type: ignore
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class FakeMockupProvider(MockupProvider):
    """Deterministic fake mockup provider for automated tests and offline use."""

    def __init__(
        self,
        *,
        pending_cycles: int = 0,
        failed_products: set[str] | None = None,
        simulate_auth_error: bool = False,
        simulate_rate_limit: bool = False,
        simulate_server_error: bool = False,
    ) -> None:
        self._pending_cycles = pending_cycles
        self._failed_products = failed_products or set()
        self._simulate_auth_error = simulate_auth_error
        self._simulate_rate_limit = simulate_rate_limit
        self._simulate_server_error = simulate_server_error

        # task_id -> {"status": ..., "product_type": ..., "polls_left": ..., "urls": ...}
        self._tasks: dict[str, dict[str, Any]] = {}

    def _generate_mockup_bytes(self, product_type: str) -> bytes:
        """Generate a valid 1200x1200 JPEG for the simulated mockup."""
        if PIL_AVAILABLE:
            img = Image.new("RGB", (1200, 1200), color=(240, 240, 245))
            draw = ImageDraw.Draw(img)
            draw.rectangle([100, 100, 1100, 1100], outline=(180, 180, 200), width=4)
            draw.text((200, 580), f"SIMULATED MOCKUP: {product_type.upper()}", fill=(60, 60, 80))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            return buf.getvalue()
        else:
            # Minimal fallback valid 1x1 JPEG bytes if PIL is not installed
            return (
                b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00"
                b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
                b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
                b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff"
                b"\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f"
                b"\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00"
                b"\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08"
                b"\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
            )

    async def create_mockup_task(
        self,
        product_type: str,
        image_url: str,
        *,
        placement: str = "front",
        format: str = "jpg",
    ) -> MockupTaskResult:
        if self._simulate_auth_error:
            raise ProviderError(
                kind=ProviderErrorKind.AUTHENTICATION,
                provider="fake_mockup",
                operation="create_mockup_task",
                message="Simulated fake mockup authentication error",
            )
        if self._simulate_rate_limit:
            raise ProviderError(
                kind=ProviderErrorKind.RATE_LIMITED,
                provider="fake_mockup",
                operation="create_mockup_task",
                message="Simulated fake mockup rate limit exceeded",
            )
        if self._simulate_server_error:
            raise ProviderError(
                kind=ProviderErrorKind.RETRYABLE,
                provider="fake_mockup",
                operation="create_mockup_task",
                message="Simulated fake mockup server 500 error",
            )

        # Validate product type against catalog
        config = get_product_config(product_type)
        task_id = f"fake_task_{uuid.uuid4().hex[:12]}"

        if product_type in self._failed_products:
            self._tasks[task_id] = {
                "status": "failed",
                "product_type": product_type,
                "polls_left": 0,
                "error": f"Simulated provider failure for product: {product_type}",
                "urls": [],
            }
            return MockupTaskResult(task_id=task_id, status="pending", mockup_urls=[])

        status = "pending" if self._pending_cycles > 0 else "completed"
        mockup_url = f"fake://mockup/{product_type}/{task_id}.jpg"

        self._tasks[task_id] = {
            "status": status,
            "product_type": product_type,
            "polls_left": self._pending_cycles,
            "urls": [mockup_url],
            "error": None,
        }

        return MockupTaskResult(
            task_id=task_id,
            status=status,
            mockup_urls=[mockup_url] if status == "completed" else [],
        )

    async def get_mockup_task(self, external_task_id: str) -> MockupTaskResult:
        task = self._tasks.get(external_task_id)
        if not task:
            raise ProviderError(
                kind=ProviderErrorKind.INVALID_REQUEST,
                provider="fake_mockup",
                operation="get_mockup_task",
                message=f"No such task with ID {external_task_id}",
            )

        if task["status"] == "failed":
            return MockupTaskResult(
                task_id=external_task_id,
                status="failed",
                mockup_urls=[],
                error_message=task.get("error", "Mockup generation failed"),
            )

        if task["polls_left"] > 0:
            task["polls_left"] -= 1
            return MockupTaskResult(
                task_id=external_task_id,
                status="pending",
                mockup_urls=[],
            )

        task["status"] = "completed"
        return MockupTaskResult(
            task_id=external_task_id,
            status="completed",
            mockup_urls=task["urls"],
        )

    async def download_mockup(self, mockup_url: str) -> bytes:
        # Determine product type from URL or fallback
        product_type = "tshirt"
        for p in ["tshirt", "sweatshirt", "tote_bag", "mug"]:
            if p in mockup_url:
                product_type = p
                break
        return self._generate_mockup_bytes(product_type)
