from dataclasses import dataclass
from collections import OrderedDict
import asyncio
import re
import time
from collections.abc import Awaitable, Callable
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


@dataclass
class _InspectionCacheEntry:
    expires_at: float
    report: ProjectReport


class InspectionCache:
    """Short-lived report cache with bounded storage and request coalescing."""

    def __init__(
        self,
        ttl_seconds: float = 300.0,
        max_entries: int = 128,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._clock = clock
        self._entries: OrderedDict[str, _InspectionCacheEntry] = OrderedDict()
        self._inflight: dict[str, asyncio.Task[ProjectReport]] = {}

    async def get_or_create(
        self,
        key: str,
        factory: Callable[[], Awaitable[ProjectReport]],
    ) -> ProjectReport:
        now = self._clock()
        entry = self._entries.get(key)
        if entry is not None:
            if entry.expires_at > now:
                self._entries.move_to_end(key)
                return entry.report.model_copy(deep=True)
            self._entries.pop(key, None)

        task = self._inflight.get(key)
        if task is None:
            task = asyncio.create_task(factory())
            self._inflight[key] = task

        try:
            report = await task
        finally:
            if task.done() and self._inflight.get(key) is task:
                self._inflight.pop(key, None)

        self._entries[key] = _InspectionCacheEntry(
            expires_at=self._clock() + self.ttl_seconds,
            report=report.model_copy(deep=True),
        )
        self._entries.move_to_end(key)
        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)
        return report.model_copy(deep=True)

    @property
    def entry_count(self) -> int:
        return len(self._entries)


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
    def __init__(
        self,
        github_client: GitHubClient,
        cache: InspectionCache | None = None,
    ) -> None:
        self.github_client = github_client
        self.cache = cache or _default_inspection_cache

    async def get_metadata(self, reference: RepositoryReference) -> RepositoryMetadata:
        return await self.github_client.get_repository(reference.owner, reference.repo)

    async def inspect(self, reference: RepositoryReference) -> ProjectReport:
        key = f"{reference.owner.lower()}/{reference.repo.lower()}"
        return await self.cache.get_or_create(
            key,
            lambda: self._inspect_uncached(reference),
        )

    async def _inspect_uncached(self, reference: RepositoryReference) -> ProjectReport:
        metadata = await self.get_metadata(reference)
        snapshot = await self.github_client.get_repository_snapshot(metadata)
        try:
            analysis = analyze_repository(snapshot)
            return build_project_report(analysis)
        except Exception as exc:
            raise RepositoryAnalysisError from exc


_default_inspection_cache = InspectionCache()
