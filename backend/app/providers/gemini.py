from __future__ import annotations

from typing import Any
import asyncio
import base64
import httpx
from decimal import Decimal

from app.ports.errors import ProviderError, ProviderErrorKind
from app.ports.providers import ImageRequest, ImageResponse, ImageCandidate, TextRequest, TextResponse
from app.providers.openai import ResearchSynthesisSchema


class GeminiImageAdapter:
    """Live Google Gemini image-generation adapter.

    Communicates with Google AI Studio REST API using the v1beta generateContent endpoint.
    Default model: gemini-3.1-flash-image
    Premium model: gemini-3-pro-image
    """

    name = "gemini"

    def __init__(
        self,
        api_key: str,
        default_model: str = "gemini-3.1-flash-image",
        timeout_seconds: float = 60.0,
    ) -> None:
        self._api_key = api_key
        self._default_model = default_model
        self._timeout = timeout_seconds

    async def _generate_single(
        self, client: httpx.AsyncClient, model: str, prompt: str, aspect_ratio: str | None
    ) -> ImageCandidate:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        
        headers = {
            "x-goog-api-key": self._api_key,
            "Content-Type": "application/json",
        }

        # Build content payload
        payload: dict[str, Any] = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ],
            "generationConfig": {
                "responseModalities": ["IMAGE"]
            }
        }

        # Add image config if aspect ratio is provided
        if aspect_ratio:
            payload["generationConfig"]["imageConfig"] = {
                "aspectRatio": aspect_ratio
            }

        response = await client.post(url, headers=headers, json=payload)

        if response.status_code == 401:
            raise ProviderError(
                kind=ProviderErrorKind.AUTHENTICATION,
                provider=self.name,
                operation="generate",
                message="Invalid API Key or unauthorized request to Gemini.",
            )
        elif response.status_code == 429:
            raise ProviderError(
                kind=ProviderErrorKind.RATE_LIMITED,
                provider=self.name,
                operation="generate",
                message="Gemini API rate limit exceeded.",
            )
        elif response.status_code >= 500:
            raise ProviderError(
                kind=ProviderErrorKind.RETRYABLE,
                provider=self.name,
                operation="generate",
                message=f"Gemini server error: {response.status_code}",
            )
        elif response.status_code >= 400:
            raise ProviderError(
                kind=ProviderErrorKind.INVALID_REQUEST,
                provider=self.name,
                operation="generate",
                message=f"Gemini bad request: {response.text}",
            )

        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise ProviderError(
                kind=ProviderErrorKind.INVALID_REQUEST,
                provider=self.name,
                operation="generate",
                message=f"Gemini API returned no candidates. Raw response: {response.text}",
            )

        parts = candidates[0].get("content", {}).get("parts", [])
        
        # Look for inlineData representing the image bytes
        inline_data = None
        for part in parts:
            if "inlineData" in part:
                inline_data = part["inlineData"]
                break

        if not inline_data or "data" not in inline_data:
            raise ProviderError(
                kind=ProviderErrorKind.INVALID_REQUEST,
                provider=self.name,
                operation="generate",
                message="Gemini API did not return image inlineData in parts.",
            )

        mime_type = inline_data.get("mimeType", "image/png")
        b64_data = inline_data["data"]
        
        try:
            image_bytes = base64.b64decode(b64_data)
        except Exception as exc:
            raise ProviderError(
                kind=ProviderErrorKind.INVALID_REQUEST,
                provider=self.name,
                operation="generate",
                message=f"Failed to decode base64 image data from Gemini: {exc!s}",
            ) from exc

        return ImageCandidate(
            image_bytes=image_bytes,
            mime_type=mime_type,
        )

    async def generate(self, request: ImageRequest) -> ImageResponse:
        model = request.model or self._default_model
        
        # Format the prompt by appending the negative prompt if provided
        prompt = request.positive_prompt
        if request.negative_prompt:
            prompt += f"\n[Avoid: {request.negative_prompt}]"

        try:
            # We call in parallel using asyncio.gather to acquire multiple candidates
            # because native candidateCount is often constrained to 1 for image generation.
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                tasks = [
                    self._generate_single(client, model, prompt, request.aspect_ratio)
                    for _ in range(request.candidate_count)
                ]
                candidates = await asyncio.gather(*tasks)

            # Determine model unit price
            if "pro" in model:
                unit_price = Decimal("0.15")
            else:
                unit_price = Decimal("0.03")

            cost_usd = unit_price * request.candidate_count

            return ImageResponse(
                candidates=list(candidates),
                model=model,
                cost_usd=cost_usd,
            )

        except httpx.TimeoutException as exc:
            raise ProviderError(
                kind=ProviderErrorKind.RETRYABLE,
                provider=self.name,
                operation="generate",
                message="Gemini API request timed out.",
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderError(
                kind=ProviderErrorKind.RETRYABLE,
                provider=self.name,
                operation="generate",
                message=f"HTTP request error: {exc!s}",
            ) from exc


def inline_refs(schema: Any, defs: dict | None = None) -> Any:
    """Recursively resolves OpenAPI $ref references to inline schemas."""
    if defs is None:
        defs = schema.get("$defs", {})

    if isinstance(schema, dict):
        if "$ref" in schema:
            ref_path = schema["$ref"]
            ref_name = ref_path.split("/")[-1]
            ref_schema = defs.get(ref_name, {})
            return inline_refs(ref_schema, defs)
        
        if "anyOf" in schema:
            subschemas = schema["anyOf"]
            non_null_subschema = None
            is_nullable = False
            for sub in subschemas:
                if isinstance(sub, dict) and sub.get("type") == "null":
                    is_nullable = True
                else:
                    non_null_subschema = sub
            
            if non_null_subschema is not None:
                resolved_sub = inline_refs(non_null_subschema, defs)
                if isinstance(resolved_sub, dict):
                    merged = {k: v for k, v in resolved_sub.items()}
                    if is_nullable:
                        merged["nullable"] = True
                    for k in ["title", "description"]:
                        if k in schema and k not in merged:
                            merged[k] = schema[k]
                    return merged

        return {
            k: inline_refs(v, defs)
            for k, v in schema.items()
            if k != "$defs" and k != "additionalProperties"
        }
    elif isinstance(schema, list):
        return [inline_refs(item, defs) for item in schema]
    return schema


class GeminiSynthesisAdapter:
    """Live Google Gemini Structured Synthesis Adapter.

    Communicates with Google AI Studio REST API using the v1beta generateContent endpoint.
    """

    name = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-flash-latest",
        timeout_seconds: float = 60.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds

    async def generate(self, request: TextRequest) -> TextResponse:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}:generateContent"

        headers = {
            "x-goog-api-key": self._api_key,
            "Content-Type": "application/json",
        }

        # Format content for Gemini API
        payload: dict[str, Any] = {
            "contents": [
                {
                    "parts": [
                        {"text": request.prompt}
                    ]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": inline_refs(ResearchSynthesisSchema.model_json_schema())
            }
        }

        if request.system:
            payload["systemInstruction"] = {
                "parts": [
                    {"text": request.system}
                ]
            }

        if request.max_output_tokens:
            payload["generationConfig"]["maxOutputTokens"] = request.max_output_tokens

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, headers=headers, json=payload)

            if response.status_code == 401:
                raise ProviderError(
                    kind=ProviderErrorKind.AUTHENTICATION,
                    provider=self.name,
                    operation="generate",
                    message="Invalid API Key or unauthorized request to Gemini.",
                )
            elif response.status_code == 429:
                raise ProviderError(
                    kind=ProviderErrorKind.RATE_LIMITED,
                    provider=self.name,
                    operation="generate",
                    message="Gemini API rate limit exceeded.",
                )
            elif response.status_code >= 500:
                raise ProviderError(
                    kind=ProviderErrorKind.RETRYABLE,
                    provider=self.name,
                    operation="generate",
                    message=f"Gemini server error: {response.status_code}",
                )
            elif response.status_code >= 400:
                raise ProviderError(
                    kind=ProviderErrorKind.INVALID_REQUEST,
                    provider=self.name,
                    operation="generate",
                    message=f"Gemini bad request: {response.text}",
                )

            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise ProviderError(
                    kind=ProviderErrorKind.INVALID_REQUEST,
                    provider=self.name,
                    operation="generate",
                    message="Gemini response did not return any candidates.",
                )

            part = candidates[0].get("content", {}).get("parts", [{}])[0]
            text = part.get("text", "")
            if not text:
                raise ProviderError(
                    kind=ProviderErrorKind.INVALID_REQUEST,
                    provider=self.name,
                    operation="generate",
                    message="Gemini response candidate text is empty.",
                )

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

            usage = data.get("usageMetadata", {})
            input_tokens = usage.get("promptTokenCount", 0)
            output_tokens = usage.get("candidatesTokenCount", 0)

            return TextResponse(
                text=text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model=self._model,
            )

        except httpx.TimeoutException as exc:
            raise ProviderError(
                kind=ProviderErrorKind.RETRYABLE,
                provider=self.name,
                operation="generate",
                message="Gemini API request timed out.",
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderError(
                kind=ProviderErrorKind.RETRYABLE,
                provider=self.name,
                operation="generate",
                message=f"HTTP request error: {exc!s}",
            ) from exc

