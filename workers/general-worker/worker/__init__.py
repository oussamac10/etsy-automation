"""Background worker.

Delivery is at least once, so every actor must be idempotent (see
workers/general-worker/CLAUDE.md). Phase 1 provides the broker wiring, the retry policy
and a health task; real jobs arrive with the phases that own them.
"""

__version__ = "0.1.0"
