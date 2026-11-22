"""Build a RepositorySnapshot from a local folder or ZIP archive (no network).

The snapshot goes through the same analyzer as GitHub repositories, with the same
bounds: limited paths, limited files, limited bytes. Archives are only ever read in
memory. Nothing is extracted to disk, executed or installed.
"""

from __future__ import annotations

import io
import os
import re
import zipfile
from collections.abc import Callable
from pathlib import Path, PurePosixPath

from app.core.config import settings
from app.integrations.github import _is_relevant_config, _select_source_files
from app.schemas.analysis import AnalysisLimitations, RepositorySnapshot
from app.schemas.repository import RepositoryMetadata

# Directories that are noise for inspection and can be huge.
SKIPPED_DIRECTORIES = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", ".dart_tool", ".gradle",
    ".idea", ".next", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox",
}


class LocalSourceError(ValueError):
    """Raised when a folder or archive cannot be inspected."""


def snapshot_from_directory(root: str | os.PathLike[str], name: str | None = None) -> RepositorySnapshot:
    base = Path(root).expanduser().resolve()
    if not base.is_dir():
        raise LocalSourceError(f"Not a folder: {root}")
    entries: list[tuple[str, int]] = []
    visited = 0
    for current, dirs, files in os.walk(base, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in SKIPPED_DIRECTORIES and not os.path.islink(os.path.join(current, d)))
        for filename in sorted(files):
            visited += 1
            if visited > settings.local_max_walk_files:
                raise LocalSourceError("The folder contains too many files to inspect safely.")
            full = Path(current) / filename
            if full.is_symlink() or not full.is_file():
                continue
            try:
                size = full.stat().st_size
            except OSError:
                continue
            relative = full.relative_to(base).as_posix()
            entries.append((relative, size))

    def read(path: str, limit: int) -> bytes | None:
        try:
            with open(base / path, "rb") as handle:
                return handle.read(limit + 1)
        except OSError:
            return None

    return _build_snapshot(name or base.name or "folder", entries, read, "folder")


def snapshot_from_zip(data: bytes, name: str = "archive") -> RepositorySnapshot:
    if len(data) > settings.local_max_archive_bytes:
        raise LocalSourceError("The archive is too large to inspect.")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise LocalSourceError("The file is not a valid ZIP archive.") from exc

    with archive:
        infos = archive.infolist()
        if len(infos) > settings.local_max_archive_entries:
            raise LocalSourceError("The archive contains too many entries to inspect safely.")
        safe: dict[str, zipfile.ZipInfo] = {}
        for info in infos:
            path = _safe_member_path(info)
            if path is not None:
                safe[path] = info
        prefix = _common_prefix(list(safe))
        by_path = {path[len(prefix):]: info for path, info in safe.items() if path[len(prefix):]}
        entries = [(path, info.file_size) for path, info in by_path.items()]

        def read(path: str, limit: int) -> bytes | None:
            info = by_path.get(path)
            if info is None:
                return None
            try:
                with archive.open(info) as handle:
                    return handle.read(limit + 1)
            except (OSError, RuntimeError, zipfile.BadZipFile):
                return None

        return _build_snapshot(_clean_name(name), entries, read, "ZIP archive")


def _safe_member_path(info: zipfile.ZipInfo) -> str | None:
    if info.is_dir() or info.flag_bits & 0x1:  # directory or encrypted
        return None
    if (info.external_attr >> 16) & 0o170000 == 0o120000:  # symlink
        return None
    path = info.filename.replace("\\", "/")
    parts = [part for part in PurePosixPath(path).parts if part not in ("", ".")]
    if not parts or path.startswith("/") or ".." in parts or re.match(r"^[A-Za-z]:", parts[0]):
        return None
    if any(part in SKIPPED_DIRECTORIES for part in parts[:-1]):
        return None
    return "/".join(parts)


def _common_prefix(paths: list[str]) -> str:
    """GitHub-style archives wrap everything in one folder; strip it."""
    if not paths:
        return ""
    first = {path.split("/", 1)[0] for path in paths}
    if len(first) == 1 and all("/" in path for path in paths):
        return next(iter(first)) + "/"
    return ""


def _clean_name(name: str) -> str:
    stem = PurePosixPath(name.replace("\\", "/")).name
    if stem.lower().endswith(".zip"):
        stem = stem[:-4]
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "-", stem).strip("-.")
    return stem or "archive"


def _build_snapshot(
    name: str,
    entries: list[tuple[str, int]],
    read: Callable[[str, int], bytes | None],
    kind: str,
) -> RepositorySnapshot:
    entries = sorted(entries)
    paths_truncated = len(entries) > settings.github_max_tree_paths
    entries = entries[: settings.github_max_tree_paths]
    files = [path for path, _ in entries]
    file_sizes = {path: size for path, size in entries}
    directories = sorted({parent for path in files for parent in _parents(path)})

    config_contents, config_truncated, config_notes = _read_config(files, file_sizes, read)
    (source_contents, inspected, skipped, truncated, source_truncated, source_notes) = _read_source(
        [{"path": path, "type": "blob", "size": size} for path, size in entries], read
    )

    notes = list(config_notes) + list(source_notes)
    notes.append(f"Analyzed a local {kind}; GitHub metadata (stars, forks, default branch) is not available.")
    notes.append("Only bounded content was inspected; source inspection was selective.")
    if paths_truncated:
        notes.append(f"Only the first {settings.github_max_tree_paths} paths were analyzed.")

    metadata = RepositoryMetadata(
        owner="local",
        name=name,
        full_name=f"local/{name}",
        description=None,
        html_url=f"local://{name}",
        default_branch="(local)",
        language=None,
        stargazers_count=0,
        forks_count=0,
        open_issues_count=0,
        private=False,
        source="local",
    )
    return RepositorySnapshot(
        metadata=metadata,
        files=files,
        directories=directories,
        file_contents=config_contents,
        source_file_contents=source_contents,
        source_files_inspected=inspected,
        source_files_skipped=skipped,
        source_files_truncated=truncated,
        source_content_truncated=source_truncated,
        source_limitation_notes=source_notes,
        file_sizes=file_sizes,
        limitations=AnalysisLimitations(
            tree_truncated=False,
            paths_truncated=paths_truncated,
            content_truncated=config_truncated or source_truncated,
            notes=notes,
        ),
    )


def _parents(path: str) -> list[str]:
    parts = path.split("/")[:-1]
    return ["/".join(parts[: i + 1]) for i in range(len(parts))]


def _decode(raw: bytes) -> str | None:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _read_config(
    files: list[str], sizes: dict[str, int], read: Callable[[str, int], bytes | None]
) -> tuple[dict[str, str], bool, list[str]]:
    contents: dict[str, str] = {}
    notes: list[str] = []
    truncated = False
    total = 0
    for path in files:
        if not _is_relevant_config(path):
            continue
        if total >= settings.github_max_total_config_bytes:
            truncated = True
            notes.append("The configuration content limit was reached.")
            break
        if sizes.get(path, 0) > settings.github_max_config_file_bytes:
            truncated = True
            notes.append(f"Skipped configuration file over the size limit: {path}")
            continue
        raw = read(path, settings.github_max_config_file_bytes)
        text = _decode(raw) if raw is not None else None
        if text is None or len(raw) > settings.github_max_config_file_bytes:
            truncated = True
            notes.append(f"Skipped unreadable configuration file: {path}")
            continue
        if total + len(raw) > settings.github_max_total_config_bytes:
            truncated = True
            notes.append(f"Skipped configuration file over the total size limit: {path}")
            continue
        total += len(raw)
        contents[path] = text
    return contents, truncated, notes


def _read_source(
    entries: list[dict], read: Callable[[str, int], bytes | None]
) -> tuple[dict[str, str], list[str], list[str], list[str], bool, list[str]]:
    contents: dict[str, str] = {}
    inspected: list[str] = []
    skipped: list[str] = []
    truncated: list[str] = []
    notes: list[str] = []
    total = 0
    any_truncated = False
    directories: set[str] = set()
    for path, size in _select_source_files(entries):
        directory = path.rsplit("/", 1)[0] if "/" in path else ""
        if directory not in directories and len(directories) >= settings.github_max_source_directories:
            skipped.append(path)
            any_truncated = True
            continue
        if len(inspected) >= settings.github_max_source_files or total >= settings.github_max_total_source_bytes:
            skipped.append(path)
            any_truncated = True
            continue
        if size is not None and size > settings.github_max_source_file_bytes:
            truncated.append(path)
            any_truncated = True
            notes.append(f"Skipped source file over the per-file limit: {path}")
            continue
        raw = read(path, settings.github_max_source_file_bytes)
        text = _decode(raw) if raw is not None else None
        if text is None:
            skipped.append(path)
            any_truncated = True
            notes.append(f"Skipped unreadable source file: {path}")
            continue
        if len(raw) > settings.github_max_source_file_bytes:
            truncated.append(path)
            any_truncated = True
            notes.append(f"Skipped source file over the per-file limit: {path}")
            continue
        if total + len(raw) > settings.github_max_total_source_bytes:
            skipped.append(path)
            any_truncated = True
            continue
        total += len(raw)
        directories.add(directory)
        contents[path] = text
        inspected.append(path)
    if skipped:
        notes.append(f"Skipped {len(skipped)} source files because of inspection limits or read errors.")
    if truncated:
        notes.append(f"{len(truncated)} source files exceeded the per-file limit.")
    return contents, inspected, skipped, truncated, any_truncated, notes
