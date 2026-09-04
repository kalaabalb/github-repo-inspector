from app.integrations.github import GitHubClient
from app.services.ai.gemini import GeminiProvider
from app.services.ai.provider import AIProvider
from app.services.repositories import RepositoryService


def get_repository_service() -> RepositoryService:
    return RepositoryService(GitHubClient())


def get_ai_provider() -> AIProvider:
    return GeminiProvider()
