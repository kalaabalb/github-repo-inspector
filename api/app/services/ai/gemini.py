import asyncio

from google import genai
from google.genai import types

from app.core.config import settings
from app.schemas.ai import AIProjectExplanation
from app.services.ai.provider import (
    AIProviderNetworkError,
    AIProviderRateLimitError,
    AIProviderUnavailableError,
    AIProviderError,
)


class GeminiProvider:
    provider_name = "gemini"

    def __init__(self, api_key: str | None = None, model_name: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else settings.gemini_api_key
        self.model_name = model_name or settings.gemini_model

    async def generate_project_explanation(
        self, prompt: str
    ) -> AIProjectExplanation:
        if not self.api_key:
            raise AIProviderUnavailableError

        try:
            result = await asyncio.to_thread(self._generate, prompt)
            if isinstance(result, AIProjectExplanation):
                return result
            return AIProjectExplanation.model_validate_json(result.text)
        except AIProviderError:
            raise
        except Exception as exc:
            message = str(exc).lower()
            if "quota" in message or "rate" in message or "429" in message:
                raise AIProviderRateLimitError from exc
            if "timeout" in message or "connect" in message or "network" in message:
                raise AIProviderNetworkError from exc
            raise AIProviderError from exc

    def _generate(self, prompt: str):
        client = genai.Client(api_key=self.api_key)
        return client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=AIProjectExplanation,
                max_output_tokens=settings.gemini_max_output_tokens,
            ),
        )
