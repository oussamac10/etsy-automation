from __future__ import annotations

import pytest

from worker.idempotency import idempotency_key


def test_same_inputs_produce_the_same_key() -> None:
    a = idempotency_key("image", scope="run-1", inputs={"prompt": "p", "size": "1024"})
    b = idempotency_key("image", scope="run-1", inputs={"size": "1024", "prompt": "p"})
    assert a == b, "dict ordering must not change the key"


def test_different_inputs_produce_different_keys() -> None:
    a = idempotency_key("image", scope="run-1", inputs={"prompt": "p"})
    b = idempotency_key("image", scope="run-1", inputs={"prompt": "q"})
    assert a != b


def test_scope_isolates_runs() -> None:
    a = idempotency_key("image", scope="run-1", inputs={"prompt": "p"})
    b = idempotency_key("image", scope="run-2", inputs={"prompt": "p"})
    assert a != b


def test_operation_is_part_of_the_key() -> None:
    a = idempotency_key("image", scope="run-1", inputs={"prompt": "p"})
    b = idempotency_key("upscale", scope="run-1", inputs={"prompt": "p"})
    assert a != b


def test_key_is_readable_and_prefixed() -> None:
    key = idempotency_key("image", scope="run-1", inputs={"prompt": "p"})
    assert key.startswith("image:run-1:")


@pytest.mark.parametrize(("operation", "scope"), [("", "run-1"), ("image", "")])
def test_operation_and_scope_are_required(operation: str, scope: str) -> None:
    with pytest.raises(ValueError):
        idempotency_key(operation, scope=scope, inputs={})
