"""Domain vocabulary shared by the models, repositories and API.

Every enum here is stored as a PostgreSQL enum type, so adding a member needs a
migration. That is deliberate: these are the words the product is defined in,
and a typo should fail at the database rather than at read time.
"""

from __future__ import annotations

from enum import StrEnum


class IdeaMode(StrEnum):
    """How a workflow gets its starting concept.

    The mode is fixed when the workflow is created. It decides what research is
    allowed to do with the owner's words, which is why it is a strict enum and
    not a free-text hint.
    """

    #: No personal idea. Research proposes concepts from market evidence alone.
    MARKET_LED = "market-led"
    #: The owner supplied the concept. Research validates it; it never replaces it.
    USER_IDEA = "user-idea"
    #: The owner supplied a direction, combined with market evidence.
    HYBRID = "hybrid"


class ConceptOrigin(StrEnum):
    """Where a proposed concept came from.

    Recorded on every concept so a ranked list can never quietly present a
    machine-generated idea as the owner's own, or the reverse.
    """

    #: Derived from the owner's original idea, preserving its intent.
    USER = "user"
    #: Proposed from market evidence with no personal input.
    MARKET = "market"
    #: The owner's idea repositioned using market evidence.
    HYBRID = "hybrid"


class SourceType(StrEnum):
    """What kind of source a piece of evidence came from."""

    MARKETPLACE = "marketplace"
    BLOG = "blog"
    FORUM = "forum"
    API = "api"
    TRENDS = "trends"
    OTHER = "other"
    #: Produced by a fake provider. Never counts as real evidence.
    FAKE = "fake"


class SignalStrength(StrEnum):
    """A qualitative signal.

    Deliberately qualitative: the product must never invent a search volume, a
    sales count or a percentage, so evidence carries a judgement plus the
    observation that supports it, not a fabricated number.
    """

    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    UNKNOWN = "unknown"


class CompetitionLevel(StrEnum):
    """How crowded a keyword cluster looked when it was observed."""

    SATURATED = "saturated"
    CROWDED = "crowded"
    DIFFERENTIABLE = "differentiable"
    THIN = "thin"
    UNKNOWN = "unknown"


class Seasonality(StrEnum):
    """When a concept sells, as far as the evidence shows."""

    EVERGREEN = "evergreen"
    SEASONAL = "seasonal"
    BOTH = "both"
    UNKNOWN = "unknown"


class ConfidenceLevel(StrEnum):
    """How much the evidence actually supports a conclusion."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ConceptStatus(StrEnum):
    """A concept's position in the idea gate.

    ``ARCHIVED`` exists so a low-scoring concept can be set aside without being
    deleted — a low score must never remove a concept the owner supplied.
    """

    PROPOSED = "proposed"
    SHORTLISTED = "shortlisted"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class ProviderName(StrEnum):
    """Providers the ledger can attribute cost to.

    ``FAKE`` is the only one Phase 2 can record, because no real adapter exists.
    """

    FAKE = "fake"
    OPENAI = "openai"
    RECRAFT = "recraft"
    ETSY = "etsy"
    USPTO = "uspto"
    TAVILY = "tavily"
    GEMINI = "gemini"
    TELEGRAM = "telegram"


class CostStatus(StrEnum):
    """Where a ledger entry is in its lifecycle.

    ``ESTIMATED`` is written before dispatch and reserved against the budget;
    ``RECONCILED`` replaces the estimate with the units the provider actually
    reported.
    """

    ESTIMATED = "estimated"
    RECONCILED = "reconciled"
    #: The operation never ran, so the reservation was released.
    VOIDED = "voided"


class QualityTier(StrEnum):
    """How much the owner is willing to spend on a generation.

    ``DRAFT`` is the economical setting used for alternatives; ``FINAL`` is
    chosen explicitly. There is no automatic upgrade between them: the product
    rule is that a run never silently moves to a more expensive model.
    """

    DRAFT = "draft"
    STANDARD = "standard"
    FINAL = "final"


class AuditAction(StrEnum):
    """The audit vocabulary. Append-only; entries are never updated or deleted."""

    ENTITY_CREATED = "entity_created"
    #: Security-relevant events. The payload never carries a credential.
    LOGIN_SUCCEEDED = "login_succeeded"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    SETTINGS_UPDATED = "settings_updated"
    CREDENTIAL_STORED = "credential_stored"
    CREDENTIAL_DELETED = "credential_deleted"
    TELEGRAM_PAIRED = "telegram_paired"
    TELEGRAM_DISCONNECTED = "telegram_disconnected"
    IDEA_REVISED = "idea_revised"
    WORKFLOW_TRANSITION = "workflow_transition"
    APPROVAL_DECISION = "approval_decision"
    COST_RECORDED = "cost_recorded"
    JOB_STATUS_CHANGED = "job_status_changed"
    FAILURE_RECORDED = "failure_recorded"
    RETRY_SCHEDULED = "retry_scheduled"
    ARCHIVED = "archived"


class ProductUse(StrEnum):
    """Physical products a design is intended for."""

    TSHIRT = "tshirt"
    MUG = "mug"
    TOTE = "tote"
    STICKER = "sticker"
    WALL_ART = "wall_art"
    TUMBLER = "tumbler"
    CARD = "card"
    PHONE_CASE = "phone_case"
    OTHER = "other"
