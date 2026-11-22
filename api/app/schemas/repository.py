from typing import Literal

from pydantic import BaseModel, HttpUrl


class RepositoryInspectRequest(BaseModel):
    url: HttpUrl


class RepositoryMetadata(BaseModel):
    owner: str
    name: str
    full_name: str
    description: str | None = None
    # A plain string so local analyses can carry a path instead of a web link.
    html_url: str
    default_branch: str
    language: str | None = None
    stargazers_count: int
    forks_count: int
    open_issues_count: int
    private: bool
    source: Literal["github", "local"] = "github"
