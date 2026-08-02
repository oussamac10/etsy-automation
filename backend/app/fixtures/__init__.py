"""Deterministic development fixtures.

Everything created here is **development data**. It is not real market research:
no observation describes a genuine Etsy listing, and no row contains a sales
figure, a search volume or a revenue number, because inventing one is forbidden
by CLAUDE.md and there would be nowhere honest to put it.

Every ID is a fixed UUID so the seed is idempotent and a test can assert against
a known identifier.
"""

from app.fixtures.dev_seed import (
    DEV_DATA_MARKER,
    FIXTURE_IDS,
    seed_development_data,
)

__all__ = ["DEV_DATA_MARKER", "FIXTURE_IDS", "seed_development_data"]
