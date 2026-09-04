from dataclasses import dataclass
import re
from urllib.parse import SplitResult, urlsplit

from app.integrations.github import GitHubClient
from app.schemas.analysis import AnalysisReport
from app.schemas.report import ProjectReport
from app.services.analyzer import analyze_repository
from app.services.report_builder import build_project_report
from app.schemas.repository import RepositoryMetadata


class InvalidRepositoryUrlError(ValueError):
    """Raised when input is not a supported public GitHub repository URL."""


class RepositoryAnalysisError(Exception):
    """Raised when the repository cannot be converted into an analysis report."""


@dataclass(frozen=True)
class RepositoryReference:
    owner: str
    repo: str


def parse_github_repository_url(url: str) -> RepositoryReference:
    parsed = urlsplit(url)
    if not _is_github_url(parsed):
        raise InvalidRepositoryUrlError

    path_parts = parsed.path.split("/")
    if len(path_parts) not in {3, 4} or path_parts[0] != "":
        raise InvalidRepositoryUrlError
    if len(path_parts) == 4 and path_parts[3] != "":
        raise InvalidRepositoryUrlError

    owner, repo = path_parts[1], path_parts[2]
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not _is_valid_identifier(owner) or not _is_valid_identifier(repo):
        raise InvalidRepositoryUrlError

    return RepositoryReference(owner=owner, repo=repo)


def validate_repository_identifiers(owner: str, repo: str) -> RepositoryReference:
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not _is_valid_identifier(owner) or not _is_valid_identifier(repo):
        raise InvalidRepositoryUrlError
    return RepositoryReference(owner=owner, repo=repo)


def _is_valid_identifier(value: str) -> bool:
    return re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value) is not None


def _is_github_url(parsed: SplitResult) -> bool:
    try:
        port = parsed.port
    except ValueError:
        return False

    return (
        parsed.scheme == "https"
        and parsed.hostname == "github.com"
        and parsed.username is None
        and parsed.password is None
        and port is None
        and not parsed.query
        and not parsed.fragment
    )


class RepositoryService:
    def __init__(self, github_client: GitHubClient) -> None:
        self.github_client = github_client

    async def get_metadata(self, reference: RepositoryReference) -> RepositoryMetadata:
        return await self.github_client.get_repository(reference.owner, reference.repo)

    async def inspect(self, reference: RepositoryReference) -> ProjectReport:
        metadata = await self.get_metadata(reference)
        snapshot = await self.github_client.get_repository_snapshot(metadata)
        try:
            analysis = analyze_repository(snapshot)
            return build_project_report(analysis)
        except Exception as exc:
            raise RepositoryAnalysisError from exc
