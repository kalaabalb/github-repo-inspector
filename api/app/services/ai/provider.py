from typing import Protocol

from app.schemas.ai import AIProjectExplanation


class AIProviderError(Exception):
    """Base error for controlled AI provider failures."""


class AIProviderUnavailableError(AIProviderError):
    """Raised when an AI provider is not configured."""


class AIProviderRateLimitError(AIProviderError):
    """Raised when an AI provider rate limit or quota is reached."""


class AIProviderNetworkError(AIProviderError):
    """Raised when an AI provider cannot be reached."""


class AIProvider(Protocol):
    provider_name: str
    model_name: str

    async def generate_project_explanation(
        self, prompt: str
    ) -> AIProjectExplanation: ...
