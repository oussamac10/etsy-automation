"""SQLAlchemy-backed repository implementations.

Each class satisfies the matching protocol in ``app/ports/repositories.py``.
They own the ORM; nothing above this layer sees a ``Session``, a ``select()`` or
a model attribute assignment.

None of these methods commits. Transaction boundaries belong to the use case, so
a single unit of work can write an entity, its transition and its audit event
together or not at all.
"""

from app.infrastructure.repositories.approval import SqlApprovalRepository
from app.infrastructure.repositories.audit import SqlAuditRepository
from app.infrastructure.repositories.auth import SqlSessionRepository
from app.infrastructure.repositories.concept import SqlConceptRepository
from app.infrastructure.repositories.cost import SqlCostRepository
from app.infrastructure.repositories.idea import SqlIdeaRepository
from app.infrastructure.repositories.outbox import SqlOutboxRepository
from app.infrastructure.repositories.owner_settings import (
    SqlOwnerSettingsRepository,
    SqlProviderCredentialRepository,
)
from app.infrastructure.repositories.production import SqlProductionJobRepository
from app.infrastructure.repositories.research import SqlResearchRepository
from app.infrastructure.repositories.telegram import SqlTelegramConnectionRepository
from app.infrastructure.repositories.user import SqlUserRepository
from app.infrastructure.repositories.workflow import SqlWorkflowRepository
from app.infrastructure.repositories.artwork import (
    SqlArtworkJobRepository,
    SqlAssetRepository,
)

__all__ = [
    "SqlApprovalRepository",
    "SqlArtworkJobRepository",
    "SqlAssetRepository",
    "SqlAuditRepository",
    "SqlConceptRepository",
    "SqlCostRepository",
    "SqlIdeaRepository",
    "SqlOutboxRepository",
    "SqlOwnerSettingsRepository",
    "SqlProductionJobRepository",
    "SqlProviderCredentialRepository",
    "SqlResearchRepository",
    "SqlSessionRepository",
    "SqlTelegramConnectionRepository",
    "SqlUserRepository",
    "SqlWorkflowRepository",
]
