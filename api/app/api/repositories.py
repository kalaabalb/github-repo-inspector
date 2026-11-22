from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.dependencies import get_ai_provider, get_repository_service
from app.integrations.github import (
    GitHubAPIError,
    GitHubNetworkError,
    GitHubRateLimitError,
    GitHubRepositoryNotFoundError,
)
from app.schemas.ai import AIExplanationResponse, ExplainRequest
from app.schemas.report import ProjectReport
from app.services.ai.prompts import PromptTooLargeError
from app.services.ai.provider import (
    AIProvider,
    AIProviderError,
    AIProviderNetworkError,
    AIProviderRateLimitError,
    AIProviderUnavailableError,
)
from app.services.ai.service import AIExplanationService
from app.schemas.repository import RepositoryInspectRequest, RepositoryMetadata
from app.core.config import settings
from app.services.local_source import LocalSourceError, snapshot_from_zip
from app.services.repositories import (
    build_report_from_snapshot,
    InvalidRepositoryUrlError,
    RepositoryService,
    RepositoryAnalysisError,
    parse_github_repository_url,
    validate_repository_identifiers,
)

router = APIRouter(prefix="/api/v1/repositories", tags=["repositories"])


@router.get("/{owner}/{repo}", response_model=RepositoryMetadata)
async def get_repository_metadata(
    owner: str,
    repo: str,
    service: RepositoryService = Depends(get_repository_service),
) -> RepositoryMetadata:
    try:
        reference = validate_repository_identifiers(owner, repo)
        return await service.get_metadata(reference)
    except InvalidRepositoryUrlError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid GitHub repository identifier",
        ) from exc
    except GitHubRepositoryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found") from exc
    except GitHubRateLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="GitHub API rate limit reached") from exc
    except GitHubNetworkError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="GitHub API unavailable") from exc
    except GitHubAPIError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="GitHub API returned an invalid response") from exc


@router.post("/inspect", response_model=ProjectReport)
async def inspect_repository_url(
    request: RepositoryInspectRequest,
    service: RepositoryService = Depends(get_repository_service),
) -> ProjectReport:
    try:
        reference = parse_github_repository_url(str(request.url))
        return await service.inspect(reference)
    except InvalidRepositoryUrlError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="URL must be an HTTPS GitHub repository URL",
        ) from exc
    except GitHubRepositoryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found") from exc
    except GitHubRateLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="GitHub API rate limit reached") from exc
    except GitHubNetworkError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="GitHub API unavailable") from exc
    except GitHubAPIError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="GitHub API returned an invalid response") from exc
    except RepositoryAnalysisError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Repository analysis failed") from exc


@router.post("/inspect-archive", response_model=ProjectReport)
async def inspect_archive(request: Request, name: str = "archive") -> ProjectReport:
    """Analyze an uploaded ZIP (raw request body). Works without any GitHub access."""
    limit = settings.local_max_archive_bytes
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Archive is too large")
    chunks: list[bytes] = []
    received = 0
    async for chunk in request.stream():
        received += len(chunk)
        if received > limit:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Archive is too large")
        chunks.append(chunk)
    try:
        snapshot = snapshot_from_zip(b"".join(chunks), name=name)
        return build_report_from_snapshot(snapshot)
    except LocalSourceError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except RepositoryAnalysisError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Archive analysis failed") from exc


@router.post("/explain", response_model=AIExplanationResponse)
async def explain_repository(
    request: ExplainRequest,
    provider: AIProvider = Depends(get_ai_provider),
) -> AIExplanationResponse:
    if getattr(provider, "api_key", True) is None:
        return AIExplanationResponse(
            available=False,
            provider=provider.provider_name,
            model=provider.model_name,
            reason="Gemini API key is not configured.",
        )
    try:
        explanation = await AIExplanationService(provider).explain(request.report)
        return AIExplanationResponse(
            available=True,
            provider=provider.provider_name,
            model=provider.model_name,
            explanation=explanation,
        )
    except AIProviderUnavailableError as exc:
        return AIExplanationResponse(
            available=False,
            provider=provider.provider_name,
            model=provider.model_name,
            reason="Gemini API key is not configured.",
        )
    except PromptTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Project report is too large for AI explanation",
        ) from exc
    except AIProviderRateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Gemini API rate limit or quota reached",
        ) from exc
    except AIProviderNetworkError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gemini API unavailable",
        ) from exc
    except AIProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Gemini explanation failed",
        ) from exc
