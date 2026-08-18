"""SQLAlchemy 2 typed mappings.

Every model lives here, behind the repositories in
``app/infrastructure/repositories``. Nothing outside the infrastructure layer
imports these classes: use cases talk to repository protocols, and the domain
layer knows nothing about SQLAlchemy at all.

Conventions used throughout:

* UUID primary keys, generated in Python so an entity has an identity before it
  is flushed.
* Timezone-aware UTC timestamps (``TIMESTAMP WITH TIME ZONE``).
* Enums are PostgreSQL enum types built from the domain enums, so an invalid
  value fails at the database.
* Money is a ``BIGINT`` of minor units plus a currency code. Never a float.
* Append-only tables (approvals, audit events, idea revisions) carry no
  ``updated_at`` — nothing updates them.
"""

from app.infrastructure.models.approval import Approval
from app.infrastructure.models.artwork import ArtworkJob, Asset
from app.infrastructure.models.audit import AuditEvent, WorkflowFailure
from app.infrastructure.models.auth import UserSession
from app.infrastructure.models.base import Base, TimestampMixin, UuidMixin
from app.infrastructure.models.concept import DesignPrompt, ProductConcept
from app.infrastructure.models.cost import ProviderUsage
from app.infrastructure.models.idea import OriginalIdea, OriginalIdeaRevision
from app.infrastructure.models.listing import ListingDraft, ProductionJob
from app.infrastructure.models.outbox import OutboxMessage
from app.infrastructure.models.owner_settings import OwnerSettings, ProviderCredential
from app.infrastructure.models.research import (
    KeywordCluster,
    ResearchEvidence,
    ResearchRun,
)
from app.infrastructure.models.telegram import TelegramConnection
from app.infrastructure.models.trademark import TrademarkRecord
from app.infrastructure.models.user import User
from app.infrastructure.models.workflow import ProductWorkflow, WorkflowTransition

__all__ = [
    "Approval",
    "ArtworkJob",
    "Asset",
    "AuditEvent",
    "Base",
    "DesignPrompt",
    "KeywordCluster",
    "ListingDraft",
    "OriginalIdea",
    "OriginalIdeaRevision",
    "OutboxMessage",
    "OwnerSettings",
    "ProductConcept",
    "ProductWorkflow",
    "ProductionJob",
    "ProviderCredential",
    "ProviderUsage",
    "ResearchEvidence",
    "ResearchRun",
    "TelegramConnection",
    "TimestampMixin",
    "TrademarkRecord",
    "User",
    "UserSession",
    "UuidMixin",
    "WorkflowFailure",
    "WorkflowTransition",
]
