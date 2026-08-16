from __future__ import annotations

from typing import Any
import asyncio
import base64
import httpx
from decimal import Decimal

from app.ports.errors import ProviderError, ProviderErrorKind
from app.ports.providers import ImageRequest, ImageResponse, ImageCandidate, TextRequest, TextResponse
from app.providers.openai import ResearchSynthesisSchema


ALLOWED_GEMINI_SCHEMA_KEYS = {
    "type",
    "format",
    "description",
    "nullable",
    "enum",
    "maxItems",
    "minItems",
    "properties",
    "required",
    "items",
}


def clean_gemini_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Clean JSON schema for Google Gemini responseSchema.

    1. Inlines $defs / $ref because Google Gemini responseSchema does not support $defs / $ref.
    2. Converts anyOf/oneOf null unions into nullable: True.
    3. Recursively removes unsupported keywords like additionalProperties, title, $schema, default, etc.
    """
    defs = schema.get("$defs", {})

    def resolve_schema_node(obj: Any) -> Any:
        if not isinstance(obj, dict):
            if isinstance(obj, list):
                return [resolve_schema_node(elem) for elem in obj]
            return obj

        # Handle $ref
        if "$ref" in obj:
            ref_key = obj["$ref"].split("/")[-1]
            if ref_key in defs:
                resolved_target = resolve_schema_node(defs[ref_key])
                other_keys = {
                    k: resolve_schema_node(v)
                    for k, v in obj.items()
                    if k != "$ref" and k in ALLOWED_GEMINI_SCHEMA_KEYS
                }
                if isinstance(resolved_target, dict):
                    return {**resolved_target, **other_keys}
                return resolved_target

        # Handle anyOf / oneOf (e.g. nullable: anyOf [type: string, type: null])
        if "anyOf" in obj or "oneOf" in obj:
            sub_list = obj.get("anyOf") or obj.get("oneOf") or []
            sub_types = [resolve_schema_node(sub) for sub in sub_list if isinstance(sub, dict)]
            non_null = [sub for sub in sub_types if sub.get("type") != "null"]
            if non_null:
                res = dict(non_null[0])
                res["nullable"] = True
                return res

        cleaned: dict[str, Any] = {}
        for k, v in obj.items():
            if k == "properties" and isinstance(v, dict):
                cleaned["properties"] = {
                    prop_name: resolve_schema_node(prop_schema)
                    for prop_name, prop_schema in v.items()
                }
            elif k == "items":
                cleaned["items"] = resolve_schema_node(v)
            elif k in ALLOWED_GEMINI_SCHEMA_KEYS:
                if isinstance(v, (dict, list)):
                    cleaned[k] = resolve_schema_node(v)
                else:
                    cleaned[k] = v
        return cleaned

    return resolve_schema_node(schema)


inline_refs = clean_gemini_schema


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
        self,
        client: httpx.AsyncClient,
        model: str,
        prompt: str,
        aspect_ratio: str | None,
        reference_image_bytes: bytes | None = None,
        reference_image_mime_type: str | None = None,
    ) -> ImageCandidate:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        
        headers = {
            "x-goog-api-key": self._api_key,
            "Content-Type": "application/json",
        }

        # Build content parts
        parts: list[dict[str, Any]] = []
        if reference_image_bytes:
            parts.append({
                "inlineData": {
                    "mimeType": reference_image_mime_type or "image/png",
                    "data": base64.b64encode(reference_image_bytes).decode("utf-8"),
                }
            })
        parts.append({"text": prompt})

        # Build content payload
        payload: dict[str, Any] = {
            "contents": [
                {
                    "parts": parts
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

        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                response = await client.post(url, headers=headers, json=payload)

                if response.status_code == 401:
                    raise ProviderError(
                        kind=ProviderErrorKind.AUTHENTICATION,
                        provider=self.name,
                        operation="generate",
                        message="Invalid API Key or unauthorized request to Gemini.",
                    )
                elif response.status_code == 429:
                    if attempt < max_attempts:
                        await asyncio.sleep(2.0 * attempt)
                        continue
                    raise ProviderError(
                        kind=ProviderErrorKind.RATE_LIMITED,
                        provider=self.name,
                        operation="generate",
                        retry_after_seconds=5.0,
                        message="Gemini API rate limit exceeded.",
                    )
                elif response.status_code >= 500:
                    if attempt < max_attempts:
                        await asyncio.sleep(1.5 * attempt)
                        continue
                    raise ProviderError(
                        kind=ProviderErrorKind.RETRYABLE,
                        provider=self.name,
                        operation="generate",
                        retry_after_seconds=5.0,
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

            except (httpx.TimeoutException, httpx.RequestError) as net_exc:
                if attempt < max_attempts:
                    await asyncio.sleep(1.5 * attempt)
                    continue
                raise ProviderError(
                    kind=ProviderErrorKind.RETRYABLE,
                    provider=self.name,
                    operation="generate",
                    retry_after_seconds=5.0,
                    message=f"Gemini image request error: {net_exc!s}",
                ) from net_exc

        raise ProviderError(
            kind=ProviderErrorKind.RETRYABLE,
            provider=self.name,
            operation="generate",
            retry_after_seconds=5.0,
            message="Gemini image generation failed after retries.",
        )

    async def generate(self, request: ImageRequest) -> ImageResponse:
        model = request.model or self._default_model
        
        # Calculate aspect ratio string from dimensions
        aspect_ratio: str | None = None
        if request.width and request.height:
            if request.width == request.height:
                aspect_ratio = "1:1"
            elif request.width > request.height:
                aspect_ratio = "4:3" if abs(request.width / request.height - 4/3) < 0.1 else "16:9"
            else:
                aspect_ratio = "3:4" if abs(request.height / request.width - 4/3) < 0.1 else "9:16"

        candidate_count = request.candidate_count or 1
        prompt = request.positive_prompt
        if request.reference_image_bytes is not None:
            isolation_instruction = (
                "Keep the artwork isolated on a plain clean background suitable for automatic background removal. "
                "Do not add scenery, gradients, shadows extending to the canvas edges, frames, borders, or textured backgrounds."
            )
            prompt = f"{prompt}\n{isolation_instruction}"

        if request.negative_prompt:
            prompt = f"{prompt}\nAvoid: {request.negative_prompt}"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                tasks = [
                    self._generate_single(
                        client,
                        model,
                        prompt,
                        aspect_ratio,
                        reference_image_bytes=request.reference_image_bytes,
                        reference_image_mime_type=request.reference_image_mime_type,
                    )
                    for _ in range(candidate_count)
                ]
                candidates = await asyncio.gather(*tasks)

            # Determine approximate pricing
            is_premium = "pro" in model.lower()
            cost_per_image = Decimal("0.040") if is_premium else Decimal("0.020")
            total_cost = cost_per_image * Decimal(len(candidates))

            return ImageResponse(
                candidates=list(candidates),
                model=model,
                cost_usd=total_cost,
            )

        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(
                kind=ProviderErrorKind.RETRYABLE,
                provider=self.name,
                operation="generate",
                message=f"Unexpected error in Gemini image generation: {exc!s}",
            ) from exc


class GeminiSynthesisAdapter:
    """Live Google Gemini Structured Synthesis Adapter.

    Communicates with Google AI Studio REST API using the v1beta generateContent endpoint.
    Includes built-in exponential backoff for transient 503 Service Unavailable and rate-limit errors.
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

        models_to_try = [self._model]
        if "flash" in self._model:
            for alt in ("gemini-2.5-flash", "gemini-1.5-flash", "gemini-2.0-flash"):
                if alt not in models_to_try:
                    models_to_try.append(alt)

        last_exc: Exception | None = None
        max_attempts_per_model = 3

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for current_model in models_to_try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent"
                for attempt in range(1, max_attempts_per_model + 1):
                    try:
                        response = await client.post(url, headers=headers, json=payload)

                        if response.status_code == 401:
                            raise ProviderError(
                                kind=ProviderErrorKind.AUTHENTICATION,
                                provider=self.name,
                                operation="generate",
                                message="Invalid API Key or unauthorized request to Gemini.",
                            )
                        elif response.status_code == 429:
                            if attempt < max_attempts_per_model:
                                await asyncio.sleep(2.0 * attempt)
                                continue
                            raise ProviderError(
                                kind=ProviderErrorKind.RATE_LIMITED,
                                provider=self.name,
                                operation="generate",
                                retry_after_seconds=5.0,
                                message="Gemini API rate limit exceeded.",
                            )
                        elif response.status_code >= 500:
                            if attempt < max_attempts_per_model:
                                await asyncio.sleep(1.5 * attempt)
                                continue
                            last_exc = ProviderError(
                                kind=ProviderErrorKind.RETRYABLE,
                                provider=self.name,
                                operation="generate",
                                retry_after_seconds=5.0,
                                message=f"Gemini server error: {response.status_code}",
                            )
                            break
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
                            model=current_model,
                        )

                    except (httpx.TimeoutException, httpx.RequestError) as net_exc:
                        if attempt < max_attempts_per_model:
                            await asyncio.sleep(1.5 * attempt)
                            continue
                        last_exc = ProviderError(
                            kind=ProviderErrorKind.RETRYABLE,
                            provider=self.name,
                            operation="generate",
                            retry_after_seconds=5.0,
                            message=f"Gemini network error: {net_exc!s}",
                        )
                        break

        if last_exc:
            raise last_exc

        raise ProviderError(
            kind=ProviderErrorKind.RETRYABLE,
            provider=self.name,
            operation="generate",
            retry_after_seconds=5.0,
            message="Gemini synthesis failed after multiple attempts.",
        )
