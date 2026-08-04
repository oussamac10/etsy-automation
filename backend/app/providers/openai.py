from __future__ import annotations

import json
import httpx

from app.ports.errors import ProviderError, ProviderErrorKind
from app.ports.providers import TextRequest, TextResponse


class OpenAISynthesisAdapter:
    """Live OpenAI Structured Synthesis Adapter.

    Communicates with OpenAI Chat Completions API via HTTP.
    """

    name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-4o-mini", timeout_seconds: float = 60.0) -> None:
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

        # Request structured JSON format from the model
        payload: dict[str, object] = {
            "model": self._model,
            "messages": messages,
            "response_format": {"type": "json_object"},
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

            # Double-check JSON validity
            try:
                json.loads(text)
            except json.JSONDecodeError as exc:
                raise ProviderError(
                    kind=ProviderErrorKind.INVALID_REQUEST,
                    provider=self.name,
                    operation="generate",
                    message="Model failed to return valid JSON payload.",
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
