from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

from worker.idempotency import idempotency_key
from worker.tasks import run_production_task


def test_production_idempotency_key() -> None:
    job_id = "f0000000-0000-0000-0000-000000000001"
    key = idempotency_key("production", scope=job_id, inputs={"profile": "etsy-png-standard"})
    assert key.startswith(f"production:{job_id}:")


def test_run_production_task_actor_metadata() -> None:
    assert run_production_task.queue_name == "production"
    assert run_production_task.actor_name == "run_production_task"


@patch("worker.tasks._run_production_async")
def test_run_production_task_invokes_async(mock_run_async: MagicMock) -> None:
    mock_run_async.return_value = None
    wf_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())

    with patch("asyncio.run") as mock_asyncio_run:
        run_production_task(workflow_id=wf_id, production_job_id=job_id)
        mock_asyncio_run.assert_called_once()
