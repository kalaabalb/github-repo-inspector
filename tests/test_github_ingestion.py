import asyncio
import io
import tarfile
from contextlib import contextmanager

import httpx
import pytest

from app.core.config import settings
from app.integrations.github import (
    GitHubAPIError,
    GitHubClient,
    GitHubRateLimitError,
    _archive_entries,
    _raise_for_github_response,
    _trusted_archive_redirect,
)
from app.schemas.repository import RepositoryMetadata
from app.services.repositories import InspectionCache, RepositoryReference, RepositoryService


def metadata() -> RepositoryMetadata:
    return RepositoryMetadata(
        owner="octocat",
        name="Hello-World",
        full_name="octocat/Hello-World",
        description=None,
        html_url="https://github.com/octocat/Hello-World",
        default_branch="release/v2",
        language="Python",
        stargazers_count=0,
        forks_count=0,
        open_issues_count=0,
        private=False,
    )


def make_archive(files: dict[str, bytes], links: list[tuple[str, str]] | None = None) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        root = "Hello-World-abc123/"
        for path, content in files.items():
            info = tarfile.TarInfo(root + path)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
        for path, target in links or []:
            info = tarfile.TarInfo(root + path)
            info.type = tarfile.SYMTYPE
            info.linkname = target
            archive.addfile(info)
    return output.getvalue()


class StreamResponse:
    def __init__(self, response: httpx.Response, chunks: list[bytes] | None = None) -> None:
        self._response = response
        self._chunks = chunks or [response.content]

    def __getattr__(self, name):
        return getattr(self._response, name)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def aiter_bytes(self):
        for chunk in self._chunks:
            yield chunk


class ArchiveClient:
    def __init__(self, responses: list[httpx.Response | tuple[httpx.Response, list[bytes]]]) -> None:
        self.responses = responses
        self.urls: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def get(self, url: str, **kwargs) -> httpx.Response:
        self.urls.append(url)
        return self.responses.pop(0)

    def stream(self, method: str, url: str, **kwargs) -> StreamResponse:
        self.urls.append(url)
        result = self.responses.pop(0)
        if isinstance(result, tuple):
            return StreamResponse(result[0], result[1])
        return StreamResponse(result)


def response(status: int, *, content: bytes = b"", headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(
        status,
        content=content,
        headers=headers,
        request=httpx.Request("GET", "https://api.github.com/repos/octocat/Hello-World/tarball/release%2Fv2"),
    )


@contextmanager
def patch_settings(**values):
    originals = {name: getattr(settings, name) for name in values}
    for name, value in values.items():
        object.__setattr__(settings, name, value)
    try:
        yield
    finally:
        for name, value in originals.items():
            object.__setattr__(settings, name, value)


def test_uncached_inspection_uses_metadata_and_one_archive_request(monkeypatch) -> None:
    archive = make_archive({"README.md": b"# Hello World\n", "src/main.py": b"print('x')\n"})
    metadata_payload = {
        "owner": {"login": "octocat"},
        "name": "Hello-World",
        "full_name": "octocat/Hello-World",
        "html_url": "https://github.com/octocat/Hello-World",
        "default_branch": "release/v2",
        "language": "Python",
        "stargazers_count": 0,
        "forks_count": 0,
        "open_issues_count": 0,
        "private": False,
    }
    client = ArchiveClient([
        httpx.Response(200, json=metadata_payload, request=httpx.Request("GET", "https://api.github.com/repos/octocat/Hello-World")),
        response(200, content=archive),
    ])
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)

    report = asyncio.run(
        RepositoryService(GitHubClient(), cache=InspectionCache()).inspect(
            RepositoryReference("octocat", "Hello-World")
        )
    )

    assert report.repository.full_name == "octocat/Hello-World"
    assert len(client.urls) == 2
    assert client.urls[1].endswith("/tarball/release%2Fv2")


def test_archive_redirects_to_trusted_host(monkeypatch) -> None:
    archive = make_archive({"README.md": b"readme"})
    client = ArchiveClient([
        response(302, headers={"location": "https://codeload.github.com/octocat/Hello-World/tar.gz/abc"}),
        response(200, content=archive),
    ])
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)

    snapshot = asyncio.run(GitHubClient().get_repository_snapshot(metadata()))

    assert snapshot.files == ["README.md"]
    assert client.urls[1].startswith("https://codeload.github.com/")


@pytest.mark.parametrize(
    "location",
    [
        "https://evil.example/archive.tar.gz",
        "http://codeload.github.com/octocat/Hello-World/tar.gz/abc",
        "https://codeload.github.com.evil.example/archive.tar.gz",
        "https://user:pass@codeload.github.com/archive.tar.gz",
    ],
)
def test_archive_redirect_rejects_untrusted_destination(location: str) -> None:
    with pytest.raises(GitHubAPIError):
        _trusted_archive_redirect("https://api.github.com/repos/a/b/tarball/main", location)


def test_archive_compressed_size_limit(monkeypatch) -> None:
    archive = make_archive({"README.md": b"content"})
    client = ArchiveClient([response(200, content=archive)])
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)

    with patch_settings(github_max_archive_bytes=len(archive) - 1):
        with pytest.raises(GitHubAPIError):
            asyncio.run(GitHubClient().get_repository_snapshot(metadata()))


def test_archive_member_count_limit() -> None:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for index in range(3):
            info = tarfile.TarInfo(f"root/file-{index}.py")
            info.size = 1
            archive.addfile(info, io.BytesIO(b"x"))
    with patch_settings(github_max_archive_members=2):
        with tarfile.open(fileobj=io.BytesIO(output.getvalue()), mode="r:gz") as archive:
            _, _, notes, truncated = _archive_entries(archive)

    assert truncated is True
    assert any("member limit" in note for note in notes)


def test_archive_uncompressed_size_limit(monkeypatch) -> None:
    archive = make_archive({"src/main.py": b"x" * 20})
    client = ArchiveClient([response(200, content=archive)])
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)

    with patch_settings(github_max_archive_uncompressed_bytes=10):
        snapshot = asyncio.run(GitHubClient().get_repository_snapshot(metadata()))

    assert snapshot.limitations.content_truncated is True
    assert any("uncompressed-size" in note for note in snapshot.limitations.notes)


@pytest.mark.parametrize("path", ["../outside.py", "/absolute.py", "safe/../outside.py"])
def test_archive_rejects_unsafe_paths(path: str) -> None:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        info = tarfile.TarInfo(f"root/{path}")
        info.size = 1
        archive.addfile(info, io.BytesIO(b"x"))

    with tarfile.open(fileobj=io.BytesIO(output.getvalue()), mode="r:gz") as archive:
        with pytest.raises(GitHubAPIError):
            _archive_entries(archive)


def test_archive_skips_symlinks_and_hardlinks() -> None:
    archive_bytes = make_archive({"src/main.py": b"x"}, [("src/link.py", "main.py")])
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as archive:
        entries, _, notes, _ = _archive_entries(archive)

    assert {entry["path"] for entry in entries} == {"src/main.py", "src"}
    assert any("Symlink" in note for note in notes)


def test_archive_rejects_nul_path() -> None:
    member = tarfile.TarInfo("root/safe\x00.py")

    class OneMemberArchive:
        def __iter__(self):
            return iter([member])

    with pytest.raises(GitHubAPIError):
        _archive_entries(OneMemberArchive())


def test_malformed_archive_is_rejected(monkeypatch) -> None:
    client = ArchiveClient([response(200, content=b"not a tar archive")])
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)

    with pytest.raises(GitHubAPIError):
        asyncio.run(GitHubClient().get_repository_snapshot(metadata()))


def test_binary_source_is_skipped_without_being_decoded(monkeypatch) -> None:
    client = ArchiveClient([response(200, content=make_archive({"src/main.py": b"\xff\xfe"}))])
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)

    snapshot = asyncio.run(GitHubClient().get_repository_snapshot(metadata()))

    assert snapshot.source_file_contents == {}
    assert snapshot.source_files_inspected == []
    assert any("binary source" in note for note in snapshot.source_limitation_notes)


def test_source_limit_and_ignored_directories_are_preserved(monkeypatch) -> None:
    files = {f"src/file-{index}.py": b"x" for index in range(26)}
    files.update({"node_modules/pkg/index.js": b"x", "build/generated.py": b"x", "assets/logo.png": b"x"})
    client = ArchiveClient([response(200, content=make_archive(files))])
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)

    snapshot = asyncio.run(GitHubClient().get_repository_snapshot(metadata()))

    assert len(snapshot.source_files_inspected) == 24
    assert all("build/" not in path for path in snapshot.source_files_inspected)
    assert all("assets/" not in path for path in snapshot.source_files_inspected)
    assert all("node_modules" not in path for path in snapshot.source_files_inspected)
    assert snapshot.source_content_truncated is True


def test_configuration_limit_and_exclusions_are_preserved(monkeypatch) -> None:
    files = {f"docs/README-{index}.md": b"name: example" for index in range(20)}
    files.update({"package-lock.json": b"{}", "src/main.py": b"x"})
    client = ArchiveClient([response(200, content=make_archive(files))])
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)

    snapshot = asyncio.run(GitHubClient().get_repository_snapshot(metadata()))

    assert len(snapshot.file_contents) == 12
    assert "package-lock.json" not in snapshot.file_contents
    assert any("request limit" in note for note in snapshot.limitations.notes)


def test_archive_rate_limit_preserves_safe_diagnostics() -> None:
    rate_limited = httpx.Response(
        403,
        headers={
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": "1700000000",
            "Authorization": "Bearer secret",
        },
        request=httpx.Request("GET", "https://codeload.github.com/octocat/Hello-World/tar.gz/abc"),
    )

    with pytest.raises(GitHubRateLimitError) as raised:
        _raise_for_github_response(rate_limited, "repository archive")

    assert raised.value.endpoint_category == "repository archive"
    assert raised.value.rate_limit_headers == {
        "x-ratelimit-remaining": "0",
        "x-ratelimit-reset": "1700000000",
    }
    assert "secret" not in str(raised.value.details)


def test_upstream_429_preserves_existing_safe_rate_limit_behavior(caplog) -> None:
    rate_limited = httpx.Response(
        429,
        headers={"X-RateLimit-Limit": "60", "Retry-After": "30", "Authorization": "Bearer secret-token"},
        request=httpx.Request("GET", "https://api.github.com/repos/octocat/Hello-World"),
    )

    with pytest.raises(GitHubRateLimitError) as raised:
        _raise_for_github_response(rate_limited, "repository metadata")

    assert raised.value.endpoint_category == "repository metadata"
    assert raised.value.rate_limit_headers == {
        "x-ratelimit-limit": "60",
        "retry-after": "30",
    }
    assert "secret-token" not in caplog.text
