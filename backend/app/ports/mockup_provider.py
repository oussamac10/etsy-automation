"""MockupProvider port definition.

Decouples realistic mockup generation from specific external providers (e.g. Printful).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class MockupTaskResult:
    task_id: str
    status: str  # "pending", "completed", "failed"
    mockup_urls: list[str]
    error_message: str | None = None


@runtime_checkable
class MockupProvider(Protocol):
    """Protocol for realistic mockup generation services."""

    async def create_mockup_task(
        self,
        product_type: str,
        image_url: str,
        *,
        placement: str = "front",
        format: str = "jpg",
    ) -> MockupTaskResult:
        """Submit a mockup generation task to the provider."""
        ...

    async def get_mockup_task(self, external_task_id: str) -> MockupTaskResult:
        """Poll the status of an in-flight mockup generation task."""
        ...

    async def download_mockup(self, mockup_url: str) -> bytes:
        """Download rendered mockup image bytes from a temporary provider URL."""
        ...
