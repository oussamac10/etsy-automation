from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scripts.generate_schema_docs import (  # noqa: E402
    DOCS_PATH,
    generate_schema_markdown,
)


def test_database_schema_documentation_is_up_to_date() -> None:
    """Ensure docs/DATABASE_SCHEMA.md is generated and matches active SQLAlchemy models."""
    expected_content = generate_schema_markdown()

    if os.environ.get("UPDATE_SCHEMA_DOCS") == "1":
        DOCS_PATH.parent.mkdir(parents=True, exist_ok=True)
        DOCS_PATH.write_text(expected_content, encoding="utf-8")

    assert DOCS_PATH.exists(), (
        f"{DOCS_PATH} does not exist. Run python backend/scripts/generate_schema_docs.py"
    )
    actual_content = DOCS_PATH.read_text(encoding="utf-8")

    assert actual_content == expected_content, (
        "docs/DATABASE_SCHEMA.md is out of date with SQLAlchemy models. "
        "Run python backend/scripts/generate_schema_docs.py to update it."
    )
