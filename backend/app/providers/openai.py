from __future__ import annotations

from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.ports.errors import ProviderError, ProviderErrorKind
from app.ports.providers import TextRequest, TextResponse

# --------------------------------------------------------------------------
# Strict OpenAI Response Schemas (Pydantic V2)
# In strict mode, all properties must be required.
# --------------------------------------------------------------------------


class BaseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class KeywordClusterSchema(BaseSchema):
    primary_phrase: str = Field(...)
    attributes: list[str] = Field(...)
    recipient_occasion_terms: list[str] = Field(...)
    use_case_terms: list[str] = Field(...)
    competition_level: Literal["saturated", "crowded", "differentiable", "thin"] = Field(...)
    competition_note: str = Field(...)
    relevance_rank: int = Field(..., ge=0, le=100)


class GenerationMetadataSchema(BaseSchema):
    aspect: str = Field(...)
    quality_tier: str = Field(...)


class PromptSchema(BaseSchema):
    positive_prompt: str = Field(...)
    negative_prompt: str = Field(...)
    typography_instructions: str | None = Field(...)
    exact_slogan: str | None = Field(...)
    intended_product_uses: list[str] = Field(...)
    style_notes: str | None = Field(...)
    palette: str | None = Field(...)
    post_generation_checklist: list[str] = Field(...)
    generation_metadata: GenerationMetadataSchema = Field(...)


class ConceptScoreBreakdownSchema(BaseSchema):
    demand: int = Field(..., ge=1, le=5)
    competition_opportunity: int = Field(..., ge=1, le=5)
    seasonal_timing: int = Field(..., ge=1, le=5)
    buyer_clarity: int = Field(..., ge=1, le=5)
    differentiation: int = Field(..., ge=1, le=5)
    product_versatility: int = Field(..., ge=1, le=5)
    ip_safety: int = Field(..., ge=1, le=5)


class ConceptSchema(BaseSchema):
    title: str = Field(...)
    description: str = Field(...)
    differentiation: str = Field(...)
    target_buyer: str = Field(...)
    buyer_use_case: str = Field(...)
    seasonality: Literal["evergreen", "seasonal", "both"] = Field(...)
    risk_level: Literal["low", "medium", "high"] = Field(...)
    risk_note: str = Field(...)
    score_breakdown: ConceptScoreBreakdownSchema = Field(...)
    score_explanation: str = Field(...)
    fidelity: Literal["High", "Medium", "Low"] = Field(...)
    origin: Literal["user", "market", "hybrid"] = Field(...)
    prompt: PromptSchema = Field(...)


class ResearchSynthesisSchema(BaseSchema):
    confidence: Literal["high", "medium", "low"] = Field(...)
    proposed_test: str | None = Field(...)
    keyword_clusters: list[KeywordClusterSchema] = Field(...)
    concepts: list[ConceptSchema] = Field(...)


class OpenAISynthesisAdapter:
    """Live OpenAI Structured Synthesis Adapter.

    Communicates with OpenAI Chat Completions API via HTTP.
    """

    name = "openai"

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        timeout_seconds: float = 60.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds

    async def generate(self, request: TextRequest) -> TextResponse:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        messages: list[dict[str, str]] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.prompt})

        # Request structured JSON format using strict json_schema mode
        schema_cls = request.schema_class or ResearchSynthesisSchema
        schema_name = getattr(schema_cls, "__name__", "structured_response").lower()
        payload: dict[str, object] = {
            "model": self._model,
            "messages": messages,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": schema_cls.model_json_schema(),
                },
            },
        }

        if request.max_output_tokens:
            payload["max_tokens"] = request.max_output_tokens

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=payload,
                )

            if response.status_code == 401:
                raise ProviderError(
                    kind=ProviderErrorKind.AUTHENTICATION,
                    provider=self.name,
                    operation="generate",
                    message="Invalid API Key or unauthorized request.",
                )
            elif response.status_code == 429:
                raise ProviderError(
                    kind=ProviderErrorKind.RATE_LIMITED,
                    provider=self.name,
                    operation="generate",
                    message="OpenAI API rate limit exceeded.",
                )
            elif response.status_code >= 500:
                raise ProviderError(
                    kind=ProviderErrorKind.RETRYABLE,
                    provider=self.name,
                    operation="generate",
                    message=f"OpenAI server error: {response.status_code}",
                )
            elif response.status_code >= 400:
                raise ProviderError(
                    kind=ProviderErrorKind.INVALID_REQUEST,
                    provider=self.name,
                    operation="generate",
                    message=f"OpenAI bad request: {response.text}",
                )

            data = response.json()
            choice = data["choices"][0]["message"]
            text = choice["content"]
            usage = data["usage"]

            # Double-check schema validation
            try:
                ResearchSynthesisSchema.model_validate_json(text)
            except Exception as exc:
                raise ProviderError(
                    kind=ProviderErrorKind.INVALID_REQUEST,
                    provider=self.name,
                    operation="generate",
                    message=f"Model response did not validate against strict schema: {exc}",
                ) from exc

            return TextResponse(
                text=text,
                input_tokens=usage["prompt_tokens"],
                output_tokens=usage["completion_tokens"],
                model=self._model,
            )

        except httpx.TimeoutException as exc:
            raise ProviderError(
                kind=ProviderErrorKind.RETRYABLE,
                provider=self.name,
                operation="generate",
                message="OpenAI API request timed out.",
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderError(
                kind=ProviderErrorKind.RETRYABLE,
                provider=self.name,
                operation="generate",
                message=f"HTTP request error: {exc}",
            ) from exc
