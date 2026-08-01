"""Request and response models.

Deliberately separate from both the ORM models and the domain: an API contract
should be able to stay stable while either of those changes, and a response
should never be able to leak a column that was added for internal use.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.enums import IdeaMode
from app.domain.workflow import ApprovalDecision, ApprovalGate, RunStatus

CountryCode = Annotated[str, Field(min_length=2, max_length=2, pattern=r"^[A-Za-z]{2}$")]
LanguageCode = Annotated[str, Field(min_length=2, max_length=10)]


class CreateWorkflowRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_id: uuid.UUID
    idea_mode: IdeaMode
    name: Annotated[str, Field(min_length=1, max_length=200)]
    target_country: CountryCode
    output_language: LanguageCode
    target_marketplace: Annotated[str, Field(max_length=50)] = "etsy"
    target_buyer: Annotated[str | None, Field(max_length=2000)] = None
    intended_product_uses: Annotated[list[str], Field(max_length=20)] = []

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be blank")
        return value.strip()


class SubmitIdeaRequest(BaseModel):
    """The owner's own words.

    ``original_text`` is stored exactly as sent — no trimming beyond the
    surrounding whitespace a form adds, no rewriting, no normalisation. The
    normalised form is derived and stored separately.
    """

    model_config = ConfigDict(extra="forbid")

    original_text: Annotated[str, Field(min_length=3, max_length=4000)]
    slogan: Annotated[str | None, Field(max_length=300)] = None
    desired_style: Annotated[str | None, Field(max_length=300)] = None
    audience: Annotated[str | None, Field(max_length=300)] = None
    occasion: Annotated[str | None, Field(max_length=200)] = None
    season: Annotated[str | None, Field(max_length=100)] = None
    product_uses: Annotated[list[str], Field(max_length=20)] = []


class WorkflowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    idea_mode: IdeaMode
    name: str
    target_marketplace: str
    target_country: str
    output_language: str
    target_buyer: str | None
    intended_product_uses: list[str]
    state: RunStatus
    version: int
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


class WorkflowListResponse(BaseModel):
    items: list[WorkflowResponse]
    total: int
    limit: int
    offset: int


class OriginalIdeaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_id: uuid.UUID
    #: The owner's verbatim submission. Never an optimised rewrite.
    original_text: str
    slogan: str | None
    desired_style: str | None
    audience: str | None
    occasion: str | None
    season: str | None
    product_uses: list[str]
    revision_count: int
    created_at: datetime


class TimelineEntryResponse(BaseModel):
    kind: str
    occurred_at: str
    summary: str
    detail: dict[str, object]


class TimelineResponse(BaseModel):
    workflow_id: uuid.UUID
    state: RunStatus
    entries: list[TimelineEntryResponse]


class GateDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gate: ApprovalGate
    decision: ApprovalDecision
    actor: Annotated[str, Field(min_length=1, max_length=200)] = "owner"
    comment: Annotated[str | None, Field(max_length=4000)] = None
    revision_request: Annotated[str | None, Field(max_length=4000)] = None
    #: What was reviewed. An approval refers to a version, not just an entity.
    target_type: Annotated[str, Field(max_length=60)] = "ProductWorkflow"
    target_id: uuid.UUID | None = None
    target_version: int | None = None


class ApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_id: uuid.UUID
    gate: ApprovalGate
    decision: ApprovalDecision
    actor: str
    comment: str | None
    revision_request: str | None
    previous_state: RunStatus
    resulting_state: RunStatus
    target_type: str
    target_version: int | None
    decided_at: datetime | None
    created_at: datetime
