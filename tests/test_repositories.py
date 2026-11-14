from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_repository_service
from app.main import app
from app.schemas.analysis import RepositorySnapshot
from app.schemas.report import ProjectReport
from app.schemas.repository import RepositoryMetadata
from app.services.repositories import (
    InspectionCache,
    RepositoryAnalysisError,
    RepositoryReference,
    RepositoryService,
)


client = TestClient(app)


def build_metadata() -> RepositoryMetadata:
    return RepositoryMetadata(
        owner="octocat",
        name="Hello-World",
        full_name="octocat/Hello-World",
        description="A sample repository",
        html_url="https://github.com/octocat/Hello-World",
        default_branch="main",
        language="Python",
        stargazers_count=10,
        forks_count=2,
        open_issues_count=1,
        private=False,
    )


class FakeRepositoryService:
    def __init__(self, result: RepositoryMetadata | Exception) -> None:
        self.result = result
        self.reference: RepositoryReference | None = None

    async def get_metadata(self, reference: RepositoryReference) -> RepositoryMetadata:
        self.reference = reference
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    async def inspect(self, reference: RepositoryReference) -> ProjectReport:
        self.reference = reference
        if isinstance(self.result, Exception):
            raise self.result
        return ProjectReport(
            repository={
                "owner": self.result.owner,
                "name": self.result.name,
                "full_name": self.result.full_name,
                "description": self.result.description,
                "html_url": str(self.result.html_url),
                "default_branch": self.result.default_branch,
                "stars": self.result.stargazers_count,
                "forks": self.result.forks_count,
                "primary_language": self.result.language,
            },
            overview={
                "classifications": ["Unknown"],
                "primary_classification": "Unknown",
                "classification_basis": [],
            },
            technologies={"languages": [], "frameworks": [], "package_managers": []},
            architecture={"observed_structure": [], "interpretations": []},
            api={"signals": []},
            authentication={"signals": []},
            data={"databases": []},
            project_structure={
                "important_directories": [],
                "important_files": [],
                "configuration_files": [],
                "has_tests": False,
                "has_docs": False,
                "has_ci": False,
                "has_docker": False,
                "has_environment_example": False,
            },
            evidence=[],
            limitations={},
        )


@pytest.fixture
def service_override() -> Callable[[RepositoryMetadata | Exception], FakeRepositoryService]:
    def override(result: RepositoryMetadata | Exception) -> FakeRepositoryService:
        service = FakeRepositoryService(result)
        app.dependency_overrides[get_repository_service] = lambda: service
        return service

    yield override
    app.dependency_overrides.clear()


def test_inspect_url_normalizes_trailing_slash_and_git_suffix(
    service_override: Callable[[RepositoryMetadata | Exception], FakeRepositoryService],
) -> None:
    service = service_override(build_metadata())

    response = client.post(
        "/api/v1/repositories/inspect",
        json={"url": "https://github.com/octocat/Hello-World.git/"},
    )

    assert response.status_code == 200
    assert response.json()["repository"]["full_name"] == "octocat/Hello-World"
    assert service.reference == RepositoryReference(owner="octocat", repo="Hello-World")


def test_inspect_rejects_non_github_url(
    service_override: Callable[[RepositoryMetadata | Exception], FakeRepositoryService],
) -> None:
    service = service_override(build_metadata())

    response = client.post(
        "/api/v1/repositories/inspect",
        json={"url": "https://example.com/octocat/Hello-World"},
    )

    assert response.status_code == 422
    assert service.reference is None


def test_owner_repository_endpoint_returns_metadata(
    service_override: Callable[[RepositoryMetadata | Exception], FakeRepositoryService],
) -> None:
    service = service_override(build_metadata())

    response = client.get("/api/v1/repositories/octocat/Hello-World.git")

    assert response.status_code == 200
    assert response.json()["owner"] == "octocat"
    assert service.reference == RepositoryReference(owner="octocat", repo="Hello-World")


@pytest.mark.parametrize(
    ("error_name", "expected_status", "expected_detail"),
    [
        ("GitHubRepositoryNotFoundError", 404, "Repository not found"),
        ("GitHubRateLimitError", 429, "GitHub API rate limit reached"),
        ("GitHubNetworkError", 503, "GitHub API unavailable"),
        ("GitHubAPIError", 502, "GitHub API returned an invalid response"),
    ],
)
def test_github_failures_map_to_safe_http_errors(
    service_override: Callable[[RepositoryMetadata | Exception], FakeRepositoryService],
    error_name: str,
    expected_status: int,
    expected_detail: str,
) -> None:
    from app.integrations import github

    service_override(getattr(github, error_name)())

    response = client.get("/api/v1/repositories/octocat/Hello-World")

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}


def test_analyzer_failure_returns_clean_error(
    service_override: Callable[[RepositoryMetadata | Exception], FakeRepositoryService],
) -> None:
    service_override(RepositoryAnalysisError())

    response = client.post(
        "/api/v1/repositories/inspect",
        json={"url": "https://github.com/octocat/Hello-World"},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Repository analysis failed"}


def test_repository_service_orchestrates_metadata_snapshot_and_analyzer() -> None:
    class FakeGitHubClient:
        async def get_repository(self, owner: str, repo: str) -> RepositoryMetadata:
            return build_metadata()

        async def get_repository_snapshot(
            self, metadata: RepositoryMetadata
        ) -> RepositorySnapshot:
            return RepositorySnapshot(
                metadata=metadata,
                files=["pubspec.yaml", "lib/main.dart"],
                directories=["lib"],
                file_contents={"pubspec.yaml": "dependencies:\n  flutter:\n    sdk: flutter\n"},
            )

    import asyncio

    report = asyncio.run(
        RepositoryService(FakeGitHubClient()).inspect(
            RepositoryReference(owner="octocat", repo="Hello-World")
        )
    )

    assert report.repository.full_name == "octocat/Hello-World"
    assert [signal.name for signal in report.technologies.frameworks] == ["Flutter"]
    assert report.limitations.tree_truncated is False


def test_inspection_cache_hit_avoids_repeated_repository_work(monkeypatch) -> None:
    import asyncio
    import app.services.repositories as repository_module

    class CountingGitHubClient:
        metadata_calls = 0
        snapshot_calls = 0

        async def get_repository(self, owner: str, repo: str) -> RepositoryMetadata:
            self.metadata_calls += 1
            return build_metadata()

        async def get_repository_snapshot(
            self, metadata: RepositoryMetadata
        ) -> RepositorySnapshot:
            self.snapshot_calls += 1
            return RepositorySnapshot(metadata=metadata)

    client = CountingGitHubClient()
    report = ProjectReport.model_construct()
    monkeypatch.setattr(repository_module, "analyze_repository", lambda snapshot: object())
    monkeypatch.setattr(repository_module, "build_project_report", lambda analysis: report)
    service = RepositoryService(client, cache=InspectionCache())
    reference = RepositoryReference(owner="octocat", repo="Hello-World")

    async def run() -> None:
        first = await service.inspect(reference)
        second = await service.inspect(reference)
        assert first is not second

    asyncio.run(run())
    assert client.metadata_calls == 1
    assert client.snapshot_calls == 1


def test_inspection_cache_expiration_triggers_fresh_work() -> None:
    import asyncio

    now = [0.0]
    cache = InspectionCache(ttl_seconds=10.0, clock=lambda: now[0])
    report = ProjectReport.model_construct()
    calls = 0

    async def factory() -> ProjectReport:
        nonlocal calls
        calls += 1
        return report

    async def run() -> None:
        await cache.get_or_create("octocat/Hello-World", factory)
        now[0] = 10.0
        await cache.get_or_create("octocat/Hello-World", factory)

    asyncio.run(run())
    assert calls == 2


def test_inspection_cache_is_bounded_and_keys_do_not_collide() -> None:
    import asyncio

    cache = InspectionCache(max_entries=2)
    report = ProjectReport.model_construct()
    calls = 0

    async def factory() -> ProjectReport:
        nonlocal calls
        calls += 1
        return report

    async def run() -> None:
        await cache.get_or_create("octocat/one", factory)
        await cache.get_or_create("octocat/two", factory)
        await cache.get_or_create("octocat/three", factory)

    asyncio.run(run())
    assert cache.entry_count == 2
    assert calls == 3


def test_concurrent_identical_inspections_are_deduplicated() -> None:
    import asyncio

    cache = InspectionCache()
    report = ProjectReport.model_construct()
    calls = 0

    async def factory() -> ProjectReport:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return report

    async def run() -> None:
        await asyncio.gather(
            cache.get_or_create("octocat/Hello-World", factory),
            cache.get_or_create("octocat/Hello-World", factory),
        )

    asyncio.run(run())
    assert calls == 1
