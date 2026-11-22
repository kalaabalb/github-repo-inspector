import dataclasses
import io
import json
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import repositories as repositories_module
from app.cli import main as cli_main
from app.core.config import settings
from app.main import app
from app.services.local_source import LocalSourceError, snapshot_from_directory, snapshot_from_zip
from app.services.markdown_export import health_score, render_markdown
from app.services.repositories import build_report_from_snapshot

client = TestClient(app)

PROJECT = {
    "README.md": "# Demo\nA FastAPI service.\n",
    "api/requirements.txt": "fastapi>=0.110\npytest==8.0\n",
    "api/app/main.py": "from fastapi import FastAPI\napp = FastAPI()\n\n@app.get('/health')\ndef health():\n    return {}\n",
    "tests/test_main.py": "def test_ok():\n    assert True\n",
}


def make_zip(files: dict[str, str], prefix: str = "") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, text in files.items():
            archive.writestr(prefix + path, text)
    return buffer.getvalue()


def write_project(root: Path, files: dict[str, str]) -> None:
    for path, text in files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


# --- folder + ZIP analysis -----------------------------------------------------

def test_folder_analysis_runs_offline_and_matches_zip(tmp_path) -> None:
    write_project(tmp_path / "demo", PROJECT)
    folder_report = build_report_from_snapshot(snapshot_from_directory(tmp_path / "demo"))
    zip_report = build_report_from_snapshot(snapshot_from_zip(make_zip(PROJECT, "demo-main/"), "demo.zip"))

    assert folder_report.repository.source == "local"
    assert folder_report.repository.full_name == "local/demo"
    assert [s.name for s in folder_report.technologies.frameworks] == ["FastAPI"]
    assert {d.name for d in folder_report.dependencies} == {"fastapi", "pytest"}
    # The wrapper folder GitHub adds to archives is stripped.
    assert zip_report.repository.full_name == "local/demo"
    assert [s.name for s in zip_report.technologies.frameworks] == ["FastAPI"]
    assert zip_report.source_inspection.files_inspected == folder_report.source_inspection.files_inspected


def test_folder_skips_noise_and_symlinks(tmp_path) -> None:
    root = tmp_path / "p"
    write_project(root, {**PROJECT, "node_modules/x/index.js": "x", ".git/config": "x"})
    outside = tmp_path / "secret.txt"
    outside.write_text("TOP SECRET", encoding="utf-8")
    try:
        (root / "link.txt").symlink_to(outside)
    except OSError:
        pytest.skip("symlinks unavailable")
    snapshot = snapshot_from_directory(root)

    assert not any(p.startswith(("node_modules", ".git")) for p in snapshot.files)
    assert "link.txt" not in snapshot.files
    assert "TOP SECRET" not in json.dumps(snapshot.model_dump())


def test_zip_rejects_traversal_symlinks_encrypted_and_garbage() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("../evil.py", "x")
        archive.writestr("/abs.py", "x")
        archive.writestr("C:/win.py", "x")
        archive.writestr("ok/main.py", "print(1)")
        link = zipfile.ZipInfo("ok/link.py")
        link.external_attr = (0o120777 << 16)
        archive.writestr(link, "/etc/passwd")
    snapshot = snapshot_from_zip(buffer.getvalue(), "t.zip")

    assert snapshot.files == ["main.py"] or snapshot.files == ["ok/main.py"]
    with pytest.raises(LocalSourceError):
        snapshot_from_zip(b"definitely not a zip", "x.zip")


def test_zip_size_and_entry_limits(monkeypatch) -> None:
    from app.services import local_source

    monkeypatch.setattr(local_source, "settings", dataclasses.replace(settings, local_max_archive_bytes=100))
    with pytest.raises(LocalSourceError):
        snapshot_from_zip(make_zip(PROJECT))
    monkeypatch.setattr(local_source, "settings", dataclasses.replace(settings, local_max_archive_entries=2))
    with pytest.raises(LocalSourceError):
        snapshot_from_zip(make_zip(PROJECT))


def test_large_and_binary_files_are_skipped_not_fatal(tmp_path) -> None:
    root = tmp_path / "p"
    write_project(root, PROJECT)
    (root / "api/app/blob.py").write_bytes(b"\xff\xfe\x00\x00 not utf8")
    (root / "api/app/big.py").write_text("x = 1\n" * 10_000, encoding="utf-8")
    report = build_report_from_snapshot(snapshot_from_directory(root))

    assert report.source_inspection.files_inspected >= 1
    assert any("big.py" in n or "blob.py" in n for n in report.limitations.notes + report.source_inspection.notes)


# --- API: archive + sample --------------------------------------------------------

def test_inspect_archive_endpoint_returns_a_report() -> None:
    response = client.post(
        "/api/v1/repositories/inspect-archive?name=demo.zip",
        content=make_zip(PROJECT, "demo/"),
        headers={"Content-Type": "application/zip"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["repository"]["source"] == "local"
    assert body["technologies"]["frameworks"][0]["name"] == "FastAPI"


def test_inspect_archive_rejects_bad_and_oversized_uploads(monkeypatch) -> None:
    assert client.post("/api/v1/repositories/inspect-archive", content=b"nope").status_code == 422
    monkeypatch.setattr(repositories_module, "settings", dataclasses.replace(settings, local_max_archive_bytes=50))
    assert client.post("/api/v1/repositories/inspect-archive", content=make_zip(PROJECT)).status_code == 413


def test_sample_report_endpoint_serves_a_valid_bundled_report() -> None:
    response = client.get("/api/v1/sample-report")
    assert response.status_code == 200
    assert response.json()["repository"]["full_name"]


def test_docs_sample_matches_bundled_sample() -> None:
    bundled = Path("api/app/data/sample_report.json").read_text(encoding="utf-8")
    assert Path("docs/sample-report.json").read_text(encoding="utf-8") == bundled
    assert Path("client/assets/sample_report.json").read_text(encoding="utf-8") == bundled


# --- Markdown + CLI ------------------------------------------------------------------

def test_markdown_export_is_complete_and_deterministic(tmp_path) -> None:
    write_project(tmp_path / "demo", PROJECT)
    report = build_report_from_snapshot(snapshot_from_directory(tmp_path / "demo"))
    text = render_markdown(report)

    assert render_markdown(report) == text
    for heading in ("# Repository report: local/demo", "## Summary", "## Findings", "## Technology stack",
                    "## Dependencies", "## Evidence boundaries", "## Source inspection"):
        assert heading in text
    assert "| fastapi |" in text
    assert "local analysis" in text and "Stars / forks" not in text


def test_health_score_matches_client_formula() -> None:
    assert health_score({"high": 1}) == 82
    assert health_score({"high": 20}) == 0
    assert health_score({}) == 100


def test_cli_inspect_render_and_sample(tmp_path, capsys) -> None:
    write_project(tmp_path / "demo", PROJECT)
    out_json = tmp_path / "r.json"
    assert cli_main(["inspect", str(tmp_path / "demo"), "-f", "json", "-o", str(out_json)]) == 0
    assert json.loads(out_json.read_text())["repository"]["source"] == "local"

    assert cli_main(["render", str(out_json)]) == 0
    assert "# Repository report: local/demo" in capsys.readouterr().out

    zip_path = tmp_path / "demo.zip"
    zip_path.write_bytes(make_zip(PROJECT))
    assert cli_main(["inspect", str(zip_path)]) == 0
    assert "FastAPI" in capsys.readouterr().out

    assert cli_main(["sample"]) == 0
    assert cli_main(["inspect", str(tmp_path / "missing")]) == 2
