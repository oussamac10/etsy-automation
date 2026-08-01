"""Idempotency keys for paid and external operations.

A key is derived from the *inputs* that determine the result, so a duplicate
delivery of the same message produces the same key and the operation is billed
once. Keys never contain a secret.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def idempotency_key(operation: str, *, scope: str, inputs: dict[str, Any]) -> str:
    """Build a stable key for ``operation`` within ``scope`` (usually a run ID).

    ``inputs`` is serialised with sorted keys so dictionary ordering cannot
    change the key.
    """
    if not operation or not scope:
        raise ValueError("operation and scope are required")
    payload = json.dumps(inputs, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(f"{operation}|{scope}|{payload}".encode()).hexdigest()
    return f"{operation}:{scope}:{digest[:32]}"
