import base64

import httpx

from app.integrations.github import GitHubClient
from app.schemas.repository import RepositoryMetadata


def metadata() -> RepositoryMetadata:
    return RepositoryMetadata(
        owner="octocat",
        name="Hello-World",
        full_name="octocat/Hello-World",
        description=None,
        html_url="https://github.com/octocat/Hello-World",
        default_branch="main",
        language=None,
        stargazers_count=0,
        forks_count=0,
        open_issues_count=0,
        private=False,
    )


def test_tree_ingestion_fetches_only_allowlisted_config_and_reports_truncation(
    monkeypatch,
) -> None:
    package_content = base64.b64encode(
        b'{"dependencies":{"react":"latest"}}'
    ).decode("ascii")
    requests: list[str] = []

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        async def get(self, url: str, **kwargs) -> httpx.Response:
            requests.append(url)
            request = httpx.Request("GET", url)
            if "/git/trees/" in url:
                return httpx.Response(
                    200,
                    json={
                        "truncated": True,
                        "tree": [
                            {"path": "package.json", "type": "blob"},
                            {"path": "src", "type": "tree"},
                            {"path": "src/App.jsx", "type": "blob"},
                        ],
                    },
                    request=request,
                )
            return httpx.Response(
                200,
                json={"encoding": "base64", "size": len(package_content), "content": package_content},
                request=request,
            )

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient())

    import asyncio

    snapshot = asyncio.run(GitHubClient().get_repository_snapshot(metadata()))

    assert snapshot.files == ["package.json", "src/App.jsx"]
    assert snapshot.directories == ["src"]
    assert snapshot.file_contents == {"package.json": '{"dependencies":{"react":"latest"}}'}
    assert snapshot.limitations.tree_truncated is True
    assert any("truncated" in note for note in snapshot.limitations.notes)
    assert len(requests) == 3
    assert any("src%2FApp.jsx" in url for url in requests)
    assert snapshot.source_files_inspected == ["src/App.jsx"]


def test_empty_repository_returns_an_empty_bounded_snapshot(monkeypatch) -> None:
    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        async def get(self, url: str, **kwargs) -> httpx.Response:
            request = httpx.Request("GET", url)
            if "/git/trees/" in url:
                return httpx.Response(
                    409,
                    json={"message": "Git Repository is empty."},
                    request=request,
                )
            raise AssertionError("metadata is fetched before snapshot in the service")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient())

    import asyncio

    snapshot = asyncio.run(GitHubClient().get_repository_snapshot(metadata()))

    assert snapshot.files == []
    assert snapshot.file_contents == {}
    assert any("no commit tree" in note for note in snapshot.limitations.notes)


def test_source_selection_uses_allowlist_and_ignores_generated_directories() -> None:
    from app.integrations.github import _select_source_files

    entries = [
        {"path": "src/main.py", "type": "blob", "size": 100},
        {"path": "node_modules/pkg/index.js", "type": "blob", "size": 100},
        {"path": "assets/logo.png", "type": "blob", "size": 100},
        {"path": "build/generated.dart", "type": "blob", "size": 100},
        {"path": "README.md", "type": "blob", "size": 100},
    ]

    selected = _select_source_files(entries)

    assert [path for path, _ in selected] == ["src/main.py"]


def test_source_file_limit_records_skipped_files(monkeypatch) -> None:
    from app.integrations.github import GitHubClient

    entries = [
        {"path": f"src/file_{index}.py", "type": "blob", "size": 10}
        for index in range(26)
    ]

    class FakeAsyncClient:
        async def get(self, url: str, **kwargs) -> httpx.Response:
            request = httpx.Request("GET", url)
            return httpx.Response(
                200,
                json={"encoding": "base64", "size": 1, "content": "eA=="},
                request=request,
            )

    import asyncio

    client = FakeAsyncClient()
    result = asyncio.run(GitHubClient()._get_source_contents(client, metadata(), entries))

    assert len(result[1]) == 24
    assert len(result[2]) == 2
    assert result[4] is True


def test_source_size_limits_skip_without_decoding_content() -> None:
    from app.integrations.github import GitHubClient, _select_source_files

    selected = _select_source_files([
        {"path": "src/huge.py", "type": "blob", "size": 16_385},
    ])

    assert selected == [("src/huge.py", 16_385)]

    class NeverCalledClient:
        async def get(self, url: str, **kwargs) -> httpx.Response:
            raise AssertionError("oversized source must be skipped before fetching")

    import asyncio

    result = asyncio.run(
        GitHubClient()._get_source_contents(
            NeverCalledClient(),
            metadata(),
            [{"path": "src/huge.py", "type": "blob", "size": 16_385}],
        )
    )

    assert result[1] == []
    assert result[3] == ["src/huge.py"]
    assert result[4] is True


def test_source_total_byte_limit_stops_additional_files() -> None:
    from app.integrations.github import GitHubClient

    content = base64.b64encode(b"x" * 10_000).decode("ascii")
    entries = [
        {"path": f"src/file_{index}.py", "type": "blob", "size": 10_000}
        for index in range(20)
    ]

    class FakeAsyncClient:
        async def get(self, url: str, **kwargs) -> httpx.Response:
            return httpx.Response(
                200,
                json={"encoding": "base64", "size": 10_000, "content": content},
                request=httpx.Request("GET", url),
            )

    import asyncio

    result = asyncio.run(
        GitHubClient()._get_source_contents(FakeAsyncClient(), metadata(), entries)
    )

    assert len(result[1]) == 13
    assert len(result[2]) == 7
    assert result[4] is True
