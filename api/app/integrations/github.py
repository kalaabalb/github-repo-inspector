import base64
from typing import Any
from pathlib import PurePosixPath
from urllib.parse import quote

import httpx

from app.core.config import settings
from app.schemas.analysis import AnalysisLimitations, RepositorySnapshot
from app.schemas.repository import RepositoryMetadata


class GitHubRepositoryNotFoundError(Exception):
    """Raised when GitHub cannot find the requested repository."""


class GitHubRateLimitError(Exception):
    """Raised when GitHub rejects a request because of rate limiting."""


class GitHubAPIError(Exception):
    """Raised for an unexpected GitHub API response."""


class GitHubNetworkError(Exception):
    """Raised when GitHub cannot be reached."""


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
            raise GitHubRateLimitError

        if response.is_error:
            raise GitHubAPIError

        try:
            return RepositoryMetadata.model_validate(_metadata_fields(response.json()))
        except (ValueError, TypeError, KeyError) as exc:
            raise GitHubAPIError from exc

    async def get_repository_snapshot(
        self, metadata: RepositoryMetadata
    ) -> RepositorySnapshot:
        branch = quote(metadata.default_branch, safe="")
        endpoint = (
            f"{settings.github_api_base_url}/repos/{metadata.full_name}"
            f"/git/trees/{branch}?recursive=1"
        )

        try:
            async with httpx.AsyncClient(timeout=settings.github_timeout_seconds) as client:
                response = await client.get(
                    endpoint,
                    headers={"Accept": "application/vnd.github+json"},
                )
                if _is_empty_repository(response):
                    return RepositorySnapshot(
                        metadata=metadata,
                        limitations=AnalysisLimitations(
                            tree_truncated=False,
                            paths_truncated=False,
                            content_truncated=False,
                            notes=[
                                "The repository has no commit tree to inspect.",
                                "Only bounded repository content was inspected.",
                            ],
                        ),
                    )
                _raise_for_github_response(response)
                tree_payload = response.json()
                entries = _tree_entries(tree_payload)
                tree_truncated = bool(tree_payload.get("truncated", False))
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
                file_contents, content_truncated, content_notes = await self._get_config_contents(
                    client, metadata, files
                )
                (
                    source_file_contents,
                    source_files_inspected,
                    source_files_skipped,
                    source_files_truncated,
                    source_content_truncated,
                    source_notes,
                ) = await self._get_source_contents(
                    client, metadata, entries
                )
        except (GitHubRepositoryNotFoundError, GitHubRateLimitError, GitHubAPIError):
            raise
        except httpx.RequestError as exc:
            raise GitHubNetworkError from exc

        notes = list(content_notes)
        notes.extend(source_notes)
        notes.append("Only bounded repository content was inspected; source inspection was selective.")
        if tree_truncated:
            notes.append("GitHub marked the repository tree as truncated.")
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
                tree_truncated=tree_truncated,
                paths_truncated=paths_truncated,
                content_truncated=content_truncated or source_content_truncated,
                notes=notes,
            ),
        )

    async def _get_config_contents(
        self,
        client: httpx.AsyncClient,
        metadata: RepositoryMetadata,
        files: list[str],
    ) -> tuple[dict[str, str], bool, list[str]]:
        contents: dict[str, str] = {}
        notes: list[str] = []
        total_bytes = 0
        content_truncated = False
        for path in files:
            if not _is_relevant_config(path):
                continue
            if total_bytes >= settings.github_max_total_config_bytes:
                content_truncated = True
                notes.append("The configuration content limit was reached.")
                break

            encoded_path = quote(path, safe="")
            endpoint = (
                f"{settings.github_api_base_url}/repos/{metadata.full_name}"
                f"/contents/{encoded_path}?ref={quote(metadata.default_branch, safe='')}"
            )
            try:
                response = await client.get(
                    endpoint,
                    headers={"Accept": "application/vnd.github+json"},
                )
                _raise_for_github_response(response)
                payload = response.json()
                size = payload.get("size", 0) if isinstance(payload, dict) else 0
                if not isinstance(size, int) or size > settings.github_max_config_file_bytes:
                    content_truncated = True
                    notes.append(f"Skipped configuration file over the size limit: {path}")
                    continue
                encoding = payload.get("encoding") if isinstance(payload, dict) else None
                encoded_content = payload.get("content") if isinstance(payload, dict) else None
                if encoding != "base64" or not isinstance(encoded_content, str):
                    raise GitHubAPIError
                decoded = base64.b64decode("".join(encoded_content.split()), validate=True)
                if total_bytes + len(decoded) > settings.github_max_total_config_bytes:
                    content_truncated = True
                    notes.append(f"Skipped configuration file over the total size limit: {path}")
                    continue
                contents[path] = decoded.decode("utf-8")
                total_bytes += len(decoded)
            except (GitHubRepositoryNotFoundError, GitHubRateLimitError, GitHubAPIError):
                raise
            except (httpx.RequestError, UnicodeDecodeError, ValueError) as exc:
                if isinstance(exc, httpx.RequestError):
                    raise GitHubNetworkError from exc
                raise GitHubAPIError from exc
        return contents, content_truncated, notes

    async def _get_source_contents(
        self,
        client: httpx.AsyncClient,
        metadata: RepositoryMetadata,
        entries: list[dict[str, Any]],
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

            endpoint = (
                f"{settings.github_api_base_url}/repos/{metadata.full_name}"
                f"/contents/{quote(path, safe='')}?ref={quote(metadata.default_branch, safe='')}"
            )
            try:
                response = await client.get(
                    endpoint,
                    headers={"Accept": "application/vnd.github+json"},
                )
                _raise_for_github_response(response)
                payload = response.json()
                payload_size = payload.get("size") if isinstance(payload, dict) else None
                if isinstance(payload_size, int) and payload_size > settings.github_max_source_file_bytes:
                    truncated.append(path)
                    source_content_truncated = True
                    notes.append(f"Skipped source file over the per-file limit: {path}")
                    continue
                encoding = payload.get("encoding") if isinstance(payload, dict) else None
                encoded_content = payload.get("content") if isinstance(payload, dict) else None
                if encoding != "base64" or not isinstance(encoded_content, str):
                    raise GitHubAPIError
                decoded = base64.b64decode("".join(encoded_content.split()), validate=True)
                if len(decoded) > settings.github_max_source_file_bytes:
                    truncated.append(path)
                    source_content_truncated = True
                    notes.append(f"Skipped source file over the per-file limit: {path}")
                    continue
                if total_bytes + len(decoded) > settings.github_max_total_source_bytes:
                    skipped.append(path)
                    source_content_truncated = True
                    continue
                contents[path] = decoded.decode("utf-8")
                inspected.append(path)
                inspected_directories.add(directory)
                total_bytes += len(decoded)
            except (GitHubRepositoryNotFoundError, GitHubRateLimitError, GitHubAPIError):
                raise
            except (httpx.RequestError, UnicodeDecodeError, ValueError) as exc:
                if isinstance(exc, httpx.RequestError):
                    raise GitHubNetworkError from exc
                raise GitHubAPIError from exc

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


def _raise_for_github_response(response: httpx.Response) -> None:
    if response.status_code == 404:
        raise GitHubRepositoryNotFoundError
    if _is_rate_limited(response):
        raise GitHubRateLimitError
    if response.is_error:
        raise GitHubAPIError


def _is_empty_repository(response: httpx.Response) -> bool:
    if response.status_code != 409:
        return False
    try:
        payload = response.json()
    except ValueError:
        return False
    return isinstance(payload, dict) and "empty" in str(payload.get("message", "")).lower()


def _is_rate_limited(response: httpx.Response) -> bool:
    return response.status_code == 429 or (
        response.status_code == 403
        and response.headers.get("x-ratelimit-remaining") == "0"
    )


def _tree_entries(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("tree"), list):
        raise GitHubAPIError
    entries: list[dict[str, Any]] = []
    for entry in payload["tree"]:
        if (
            isinstance(entry, dict)
            and isinstance(entry.get("path"), str)
            and entry.get("type") in {"blob", "tree"}
        ):
            item = {"path": entry["path"], "type": entry["type"]}
            if isinstance(entry.get("size"), int):
                item["size"] = entry["size"]
            entries.append(item)
    return entries


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
