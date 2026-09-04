from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "github-repo-inspector-api")
    github_api_base_url: str = "https://api.github.com"
    github_timeout_seconds: float = 10.0
    github_max_tree_paths: int = 2000
    github_max_config_file_bytes: int = 32_768
    github_max_total_config_bytes: int = 131_072
    # Conservative defaults keep source inspection useful without turning the
    # inspector into a repository downloader.
    github_max_source_files: int = 24
    github_max_source_file_bytes: int = 16_384
    github_max_total_source_bytes: int = 131_072
    github_max_source_directories: int = 12
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY") or None
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    gemini_max_output_tokens: int = 1200


settings = Settings()
