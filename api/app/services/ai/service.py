from pydantic import ValidationError

from app.schemas.ai import AIProjectExplanation
from app.schemas.report import ProjectReport
from app.services.ai.prompts import build_explanation_prompt
from app.services.ai.provider import AIProvider, AIProviderError


class AIExplanationService:
    def __init__(self, provider: AIProvider) -> None:
        self.provider = provider

    async def explain(self, report: ProjectReport) -> AIProjectExplanation:
        prompt = build_explanation_prompt(report)
        try:
            result = await self.provider.generate_project_explanation(prompt)
            return AIProjectExplanation.model_validate(result)
        except ValidationError as exc:
            raise AIProviderError from exc
