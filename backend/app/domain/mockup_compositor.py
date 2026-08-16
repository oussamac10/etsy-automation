"""Domain logic for compositing and synchronizing mockups with master PNGs."""
from __future__ import annotations

import base64
import hashlib
import logging
import uuid
from typing import Any, cast

import httpx

from app.application.unit_of_work import UnitOfWork
from app.infrastructure.mockup_template_store import MockupTemplateStore
from app.infrastructure.models.artwork import Asset
from app.ports.providers import ObjectStorage
from app.providers.s3 import S3ObjectStorage

logger = logging.getLogger(__name__)


async def recomposite_workflow_mockups(
    uow: UnitOfWork,
    storage: ObjectStorage,
    workflow_id: uuid.UUID,
    master_bytes: bytes,
    master_asset_id: uuid.UUID,
    owner_id: uuid.UUID,
    image_worker_url: str,
) -> list[Asset]:
    """Recomposite all existing mockups for a workflow using a newly produced master PNG."""
    all_assets = await uow.assets.list_for_workflow(workflow_id)
    mockup_assets = [
        a for a in all_assets
        if (a.provenance and a.provenance.get("asset_type") == "mockup") or "/mockups/" in a.storage_key
    ]
    if not mockup_assets:
        return []

    store = MockupTemplateStore(cast(S3ObjectStorage, storage))
    updated_assets: list[Asset] = []

    async with httpx.AsyncClient(timeout=45.0) as http_client:
        for mockup in mockup_assets:
            prov = mockup.provenance or {}
            tpl_key_val = prov.get("template_storage_key")
            tpl_key: str | None = str(tpl_key_val) if tpl_key_val else None

            if not tpl_key and prov.get("template_id"):
                tpl = await store.get_template(owner_id=owner_id, template_id=str(prov["template_id"]))
                if tpl:
                    tpl_key = tpl.storage_key

            if not tpl_key:
                continue

            try:
                template_bytes = await storage.get(tpl_key)
            except Exception as e:
                logger.warning("Could not load template %s for mockup %s: %s", tpl_key, mockup.id, e)
                continue

            placement = prov.get("placement") or {
                "left_pct": 0.25,
                "top_pct": 0.25,
                "width_pct": 0.50,
                "height_pct": 0.50,
                "angle_deg": 0.0,
                "blend_mode": "multiply",
            }

            worker_payload = {
                "artwork_base64": base64.b64encode(master_bytes).decode("utf-8"),
                "template_base64": base64.b64encode(template_bytes).decode("utf-8"),
                "placement": placement,
                "format": "jpeg",
                "quality": 92,
            }

            try:
                resp = await http_client.post(
                    f"{image_worker_url.rstrip('/')}/pipeline/custom-mockup",
                    json=worker_payload,
                )
                if resp.status_code != 200:
                    logger.error("Image worker failed to recomposite mockup %s: %s", mockup.id, resp.text[:200])
                    continue

                result_data = resp.json()
                composited_bytes = base64.b64decode(result_data["mockup_base64"])
                await storage.put(mockup.storage_key, composited_bytes, content_type="image/jpeg")

                mockup.derived_from_id = master_asset_id
                mockup.byte_size = len(composited_bytes)
                mockup.checksum_sha256 = hashlib.sha256(composited_bytes).hexdigest()
                mockup.width = result_data.get("width", mockup.width or 1200)
                mockup.height = result_data.get("height", mockup.height or 1200)
                mockup.provenance = dict(
                    prov,
                    source_asset_id=str(master_asset_id),
                    template_storage_key=tpl_key,
                )
                await uow.session.flush()
                updated_assets.append(mockup)
            except Exception as exc:
                logger.exception("Error recompositing mockup %s: %s", mockup.id, exc)

    return updated_assets
