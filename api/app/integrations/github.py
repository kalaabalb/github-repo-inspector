import logging
import posixpath
import tarfile
import tempfile
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Literal
from pathlib import PurePosixPath
from urllib.parse import quote, urljoin, urlsplit

import httpx

from app.core.config import settings
from app.schemas.analysis import AnalysisLimitations, RepositorySnapshot
from app.schemas.repository import RepositoryMetadata

logger = logging.getLogger(__name__)


EndpointCategory = Literal[
    "repository metadata",
    "repository tree",
    "configuration file",
    "source file",
    "repository archive",
]
_TRUSTED_ARCHIVE_HOSTS = {"api.github.com", "github.com", "codeload.github.com"}
_SAFE_RATE_LIMIT_HEADERS = (
    "x-ratelimit-limit",
    "x-ratelimit-remaining",
    "x-ratelimit-reset",
    "retry-after",
)


@dataclass(frozen=True)
class GitHubRateLimitDetails:
    endpoint_category: EndpointCategory
    status_code: int
    headers: dict[str, str]


class GitHubRepositoryNotFoundError(Exception):
    """Raised when GitHub cannot find the requested repository."""


class GitHubRateLimitError(Exception):
    """Raised when GitHub rejects a request because of rate limiting."""

    def __init__(self, details: GitHubRateLimitDetails | None = None) -> None:
        self.details = details
        self.endpoint_category = details.endpoint_category if details else None
        self.status_code = details.status_code if details else None
        self.rate_limit_headers = details.headers if details else {}
        super().__init__("GitHub API rate limit reached")


class GitHubAPIError(Exception):
    """Raised for an unexpected GitHub API response."""


class GitHubNetworkError(Exception):
    """Raised when GitHub cannot be reached."""


class _ArchiveContentSkipped(Exception):
    """Raised when a selected archive member exceeds a content bound."""


class GitHubClient:
    async def get_repository(self, owner: str, repo: str) -> RepositoryMetadata:
        endpoint = f"{settings.github_api_base_url}/repos/{owner}/{repo}"

        try:
            async with httpx.AsyncClient(timeout=settings.github_timeout_seconds) as client:
                response = await client.get(
                    endpoint,
                    headers={"Accept": "application/vnd.github+json"},
                )
        except httpx.RequestError as exc:
            raise GitHubNetworkError from exc

        if response.status_code == 404:
            raise GitHubRepositoryNotFoundError

        if _is_rate_limited(response):
            raise _rate_limit_error(response, "repository metadata")

        if response.is_error:
            raise GitHubAPIError

        try:
            return RepositoryMetadata.model_validate(_metadata_fields(response.json()))
        except (ValueError, TypeError, KeyError) as exc:
            raise GitHubAPIError from exc

    async def get_repository_snapshot(
        self, metadata: RepositoryMetadata
    ) -> RepositorySnapshot:
        try:
            async with httpx.AsyncClient(timeout=settings.github_timeout_seconds) as client:
                with tempfile.SpooledTemporaryFile(
                    max_size=settings.github_max_archive_bytes
                ) as archive_file:
                    await self._download_archive(client, metadata, archive_file)
                    return await self._snapshot_from_archive(archive_file, metadata)
        except (GitHubRepositoryNotFoundError, GitHubRateLimitError, GitHubAPIError):
            raise
        except httpx.RequestError as exc:
            raise GitHubNetworkError from exc

    async def _download_archive(
        self,
        client: httpx.AsyncClient,
        metadata: RepositoryMetadata,
        destination: Any,
    ) -> None:
        endpoint = (
            f"{settings.github_api_base_url}/repos/{metadata.full_name}"
            f"/tarball/{quote(metadata.default_branch, safe='')}"
        )
        for _ in range(3):
            try:
                async with client.stream(
                    "GET",
                    endpoint,
                    headers={"Accept": "application/vnd.github+json"},
                    follow_redirects=False,
                ) as response:
                    if 300 <= response.status_code < 400:
                        location = response.headers.get("location")
                        endpoint = _trusted_archive_redirect(endpoint, location)
                        continue

                    _raise_for_github_response(response, "repository archive")
                    content_length = response.headers.get("content-length")
                    if content_length is not None:
                        try:
                            if int(content_length) > settings.github_max_archive_bytes:
                                raise GitHubAPIError
                        except ValueError as exc:
                            raise GitHubAPIError from exc

                    total_bytes = 0
                    async for chunk in response.aiter_bytes():
                        total_bytes += len(chunk)
                        if total_bytes > settings.github_max_archive_bytes:
                            raise GitHubAPIError
                        destination.write(chunk)
                    destination.seek(0)
                    return
            except (GitHubRepositoryNotFoundError, GitHubRateLimitError, GitHubAPIError):
                raise
            except httpx.RequestError as exc:
                raise GitHubNetworkError from exc
        raise GitHubAPIError

    async def _snapshot_from_archive(
        self, archive_file: Any, metadata: RepositoryMetadata
    ) -> RepositorySnapshot:
        try:
            with tarfile.open(fileobj=archive_file, mode="r:*") as archive:
                entries, members, scan_notes, archive_truncated = _archive_entries(archive)
                entries = sorted(entries, key=lambda entry: entry["path"])
                paths_truncated = len(entries) > settings.github_max_tree_paths
                entries = entries[: settings.github_max_tree_paths]
                files = [entry["path"] for entry in entries if entry["type"] == "blob"]
                directories = [entry["path"] for entry in entries if entry["type"] == "tree"]
                file_sizes = {
                    entry["path"]: entry["size"]
                    for entry in entries
                    if entry["type"] == "blob" and isinstance(entry.get("size"), int)
                }
                member_by_path = {
                    path: member for path, member in members.items() if path in file_sizes
                }

                async def read_file(path: str, max_bytes: int) -> bytes:
                    member = member_by_path[path]
                    if member.size > max_bytes:
                        raise _ArchiveContentSkipped
                    extracted = archive.extractfile(member)
                    if extracted is None:
                        raise GitHubAPIError
                    content = extracted.read(max_bytes + 1)
                    if len(content) > max_bytes:
                        raise _ArchiveContentSkipped
                    return content

                file_contents, content_truncated, content_notes = await self._get_config_contents(
                    files, file_sizes, read_file
                )
                (
                    source_file_contents,
                    source_files_inspected,
                    source_files_skipped,
                    source_files_truncated,
                    source_content_truncated,
                    source_notes,
                ) = await self._get_source_contents(entries, read_file)
        except (tarfile.TarError, EOFError, OSError, KeyError) as exc:
            raise GitHubAPIError from exc

        notes = list(scan_notes)
        notes.extend(content_notes)
        notes.extend(source_notes)
        notes.append("Only bounded repository content was inspected; source inspection was selective.")
        if paths_truncated:
            notes.append(f"Only the first {settings.github_max_tree_paths} tree paths were analyzed.")
        return RepositorySnapshot(
            metadata=metadata,
            files=files,
            directories=directories,
            file_contents=file_contents,
            source_file_contents=source_file_contents,
            source_files_inspected=source_files_inspected,
            source_files_skipped=source_files_skipped,
            source_files_truncated=source_files_truncated,
            source_content_truncated=source_content_truncated,
            source_limitation_notes=source_notes,
            file_sizes=file_sizes,
            limitations=AnalysisLimitations(
                tree_truncated=False,
                paths_truncated=paths_truncated or archive_truncated,
                content_truncated=content_truncated or source_content_truncated or archive_truncated,
                notes=notes,
            ),
        )

    async def _get_config_contents(
        self,
        files: list[str],
        file_sizes: dict[str, int],
        read_file: Callable[[str, int], Awaitable[bytes]],
    ) -> tuple[dict[str, str], bool, list[str]]:
        contents: dict[str, str] = {}
        notes: list[str] = []
        total_bytes = 0
        content_truncated = False
        fetched_files = 0
        for path in files:
            if not _is_relevant_config(path):
                continue
            if fetched_files >= settings.github_max_config_files:
                content_truncated = True
                notes.append("The configuration file request limit was reached.")
                break
            if total_bytes >= settings.github_max_total_config_bytes:
                content_truncated = True
                notes.append("The configuration content limit was reached.")
                break

            tree_size = file_sizes.get(path)
            if (
                isinstance(tree_size, int)
                and total_bytes + tree_size > settings.github_max_total_config_bytes
            ):
                content_truncated = True
                notes.append(f"Skipped configuration file over the total size limit: {path}")
                continue

            try:
                fetched_files += 1
                if (
                    path in file_sizes
                    and file_sizes[path] > settings.github_max_config_file_bytes
                ):
                    content_truncated = True
                    notes.append(f"Skipped configuration file over the size limit: {path}")
                    continue
                decoded = await read_file(path, settings.github_max_config_file_bytes)
                if total_bytes + len(decoded) > settings.github_max_total_config_bytes:
                    content_truncated = True
                    notes.append(f"Skipped configuration file over the total size limit: {path}")
                    continue
                try:
                    contents[path] = decoded.decode("utf-8")
                except UnicodeDecodeError:
                    content_truncated = True
                    notes.append(f"Skipped binary configuration file: {path}")
                    continue
                total_bytes += len(decoded)
            except _ArchiveContentSkipped:
                content_truncated = True
                notes.append(f"Skipped configuration file over the size limit: {path}")
            except (GitHubRepositoryNotFoundError, GitHubRateLimitError, GitHubAPIError):
                raise
        return contents, content_truncated, notes

    async def _get_source_contents(
        self,
        entries: list[dict[str, Any]],
        read_file: Callable[[str, int], Awaitable[bytes]],
    ) -> tuple[dict[str, str], list[str], list[str], list[str], bool, list[str]]:
        candidates = _select_source_files(entries)
        contents: dict[str, str] = {}
        inspected: list[str] = []
        skipped: list[str] = []
        truncated: list[str] = []
        notes: list[str] = []
        total_bytes = 0
        source_content_truncated = False
        inspected_directories: set[str] = set()

        for path, size in candidates:
            directory = path.rsplit("/", 1)[0] if "/" in path else ""
            if directory not in inspected_directories and len(inspected_directories) >= settings.github_max_source_directories:
                skipped.append(path)
                source_content_truncated = True
                continue
            if len(inspected) >= settings.github_max_source_files:
                skipped.append(path)
                source_content_truncated = True
                continue
            if size is not None and size > settings.github_max_source_file_bytes:
                truncated.append(path)
                source_content_truncated = True
                notes.append(f"Skipped source file over the per-file limit: {path}")
                continue
            if total_bytes >= settings.github_max_total_source_bytes:
                skipped.append(path)
                source_content_truncated = True
                continue

            try:
                decoded = await read_file(path, settings.github_max_source_file_bytes)
                if total_bytes + len(decoded) > settings.github_max_total_source_bytes:
                    skipped.append(path)
                    source_content_truncated = True
                    continue
                try:
                    contents[path] = decoded.decode("utf-8")
                except UnicodeDecodeError:
                    skipped.append(path)
                    source_content_truncated = True
                    notes.append(f"Skipped binary source file: {path}")
                    continue
                inspected.append(path)
                inspected_directories.add(directory)
                total_bytes += len(decoded)
            except _ArchiveContentSkipped:
                truncated.append(path)
                source_content_truncated = True
                notes.append(f"Skipped source file over the per-file limit: {path}")
            except (GitHubRepositoryNotFoundError, GitHubRateLimitError, GitHubAPIError):
                raise

        if skipped:
            notes.append(f"Skipped {len(skipped)} source files because of inspection limits.")
        if truncated:
            notes.append(f"{len(truncated)} source files exceeded the per-file limit.")
        return contents, inspected, skipped, truncated, source_content_truncated, notes


def _metadata_fields(payload: Any) -> dict[str, Any]:
    """Select only fields that are part of the public API response."""
    if not isinstance(payload, dict):
        raise TypeError("GitHub response must be a JSON object")

    owner_payload = payload.get("owner")
    if not isinstance(owner_payload, dict) or not isinstance(owner_payload.get("login"), str):
        raise KeyError("GitHub response has no owner login")

    return {
        "owner": owner_payload["login"],
        "name": payload["name"],
        "full_name": payload["full_name"],
        "description": payload.get("description"),
        "html_url": payload["html_url"],
        "default_branch": payload["default_branch"],
        "language": payload.get("language"),
        "stargazers_count": payload["stargazers_count"],
        "forks_count": payload["forks_count"],
        "open_issues_count": payload["open_issues_count"],
        "private": payload["private"],
    }


def _raise_for_github_response(
    response: httpx.Response, endpoint_category: EndpointCategory
) -> None:
    if response.status_code == 404:
        raise GitHubRepositoryNotFoundError
    if _is_rate_limited(response):
        raise _rate_limit_error(response, endpoint_category)
    if response.is_error:
        raise GitHubAPIError


def _trusted_archive_redirect(current_url: str, location: str | None) -> str:
    if not location:
        raise GitHubAPIError
    target = urlsplit(urljoin(current_url, location))
    if (
        target.scheme != "https"
        or target.hostname not in _TRUSTED_ARCHIVE_HOSTS
        or target.username is not None
        or target.password is not None
        or target.port is not None
    ):
        raise GitHubAPIError
    return target.geturl()


def _archive_entries(
    archive: tarfile.TarFile,
) -> tuple[list[dict[str, Any]], dict[str, tarfile.TarInfo], list[str], bool]:
    entries: list[dict[str, Any]] = []
    entry_keys: set[tuple[str, str]] = set()
    members: dict[str, tarfile.TarInfo] = {}
    notes: list[str] = []
    root: str | None = None
    total_uncompressed = 0
    truncated = False
    skipped_link = False

    for member_index, member in enumerate(archive):
        if member_index >= settings.github_max_archive_members:
            truncated = True
            notes.append("The archive member limit was reached.")
            break

        raw_path = member.name
        if "\x00" in raw_path or raw_path.startswith("/") or "\\" in raw_path:
            raise GitHubAPIError
        parts = raw_path.split("/")
        if any(part in {"", ".", ".."} for part in parts[:-1]) or ".." in parts:
            raise GitHubAPIError
        if root is None and parts:
            root = parts[0]
        relative_parts = parts[1:] if root and parts[0] == root else parts
        relative_path = "/".join(relative_parts).rstrip("/")
        if not relative_path or posixpath.normpath(relative_path) != relative_path:
            continue
        if member.issym() or member.islnk():
            if not skipped_link:
                notes.append("Symlink and hardlink archive members were skipped.")
                skipped_link = True
            continue
        if member.isdir():
            _add_archive_entry(entries, entry_keys, relative_path, "tree")
            continue
        if not member.isfile():
            continue

        if member.size < 0:
            raise GitHubAPIError
        total_uncompressed += member.size
        if total_uncompressed > settings.github_max_archive_uncompressed_bytes:
            truncated = True
            notes.append("The archive uncompressed-size limit was reached.")
            break
        _add_archive_entry(entries, entry_keys, relative_path, "blob", member.size)
        for parent in PurePosixPath(relative_path).parents:
            if str(parent) != ".":
                _add_archive_entry(entries, entry_keys, str(parent), "tree")
        members[relative_path] = member

    return entries, members, notes, truncated


def _add_archive_entry(
    entries: list[dict[str, Any]],
    entry_keys: set[tuple[str, str]],
    path: str,
    entry_type: Literal["blob", "tree"],
    size: int | None = None,
) -> None:
    key = (path, entry_type)
    if key in entry_keys:
        return
    entry_keys.add(key)
    entry = {"path": path, "type": entry_type}
    if entry_type == "blob" and size is not None:
        entry["size"] = size
    entries.append(entry)


def _is_rate_limited(response: httpx.Response) -> bool:
    return response.status_code == 429 or (
        response.status_code == 403
        and response.headers.get("x-ratelimit-remaining") == "0"
    )


def _rate_limit_error(
    response: httpx.Response, endpoint_category: EndpointCategory
) -> GitHubRateLimitError:
    safe_headers = {
        name: response.headers[name]
        for name in _SAFE_RATE_LIMIT_HEADERS
        if name in response.headers
    }
    details = GitHubRateLimitDetails(
        endpoint_category=endpoint_category,
        status_code=response.status_code,
        headers=safe_headers,
    )
    logger.warning(
        "GitHub rate limit response: endpoint_category=%s status_code=%s headers=%s",
        details.endpoint_category,
        details.status_code,
        details.headers,
    )
    return GitHubRateLimitError(details)


def _is_relevant_config(path: str) -> bool:
    names = {
        "pubspec.yaml",
        "package.json",
        "requirements.txt",
        "pyproject.toml",
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "cargo.toml",
        "go.mod",
        "composer.json",
        ".gitignore",
    }
    filename = PurePosixPath(path).name.lower()
    return filename in names or filename.startswith("readme")


SOURCE_EXTENSIONS = {
    ".py", ".dart", ".js", ".jsx", ".ts", ".tsx", ".java", ".kt", ".go",
    ".rs", ".php", ".rb", ".cs", ".c", ".h", ".cpp", ".hpp", ".yaml",
    ".yml", ".json", ".toml",
}
IGNORED_SOURCE_DIRECTORIES = {
    ".git", "node_modules", "build", "dist", "target", "vendor", "generated",
    "coverage", "cache", "__pycache__", ".dart_tool",
}
PRIORITY_SOURCE_DIRECTORIES = {
    "app", "api", "src", "lib", "server", "backend", "frontend", "client",
    "routes", "controllers", "services", "auth", "config", "configuration",
}
PRIORITY_SOURCE_NAMES = {
    "main", "app", "index", "server", "api", "router", "routes", "auth",
    "login", "controller", "service", "config", "settings",
}
LOCKFILE_NAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "pubspec.lock", "poetry.lock",
    "cargo.lock", "go.sum", "composer.lock",
}
ALREADY_INGESTED_CONFIG_NAMES = {
    "pubspec.yaml", "package.json", "requirements.txt", "pyproject.toml", "pom.xml",
    "build.gradle", "build.gradle.kts", "cargo.toml", "go.mod", "composer.json",
    ".gitignore",
}


def _select_source_files(entries: list[dict[str, Any]]) -> list[tuple[str, int | None]]:
    candidates: list[tuple[int, str, int | None]] = []
    for entry in entries:
        if entry.get("type") != "blob":
            continue
        path = entry["path"]
        pure_path = PurePosixPath(path)
        filename = pure_path.name.lower()
        extension = pure_path.suffix.lower()
        parts = {part.lower() for part in pure_path.parts[:-1]}
        if (
            extension not in SOURCE_EXTENSIONS
            or filename in LOCKFILE_NAMES
            or filename in ALREADY_INGESTED_CONFIG_NAMES
            or filename.startswith("readme")
        ):
            continue
        if parts & IGNORED_SOURCE_DIRECTORIES:
            continue
        directory = path.rsplit("/", 1)[0] if "/" in path else ""
        directory_parts = {part.lower() for part in directory.split("/") if part}
        score = 0
        score += 40 * len(directory_parts & PRIORITY_SOURCE_DIRECTORIES)
        if pure_path.stem.lower() in PRIORITY_SOURCE_NAMES:
            score += 25
        if extension in {".yaml", ".yml", ".json", ".toml"}:
            score += 10
        score -= len(pure_path.parts)
        size = entry.get("size") if isinstance(entry.get("size"), int) else None
        candidates.append((-score, path, size))
    candidates.sort()
    return [(path, size) for _, path, size in candidates]
