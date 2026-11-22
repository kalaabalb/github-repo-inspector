import json
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter

from app.schemas.report import ProjectReport

router = APIRouter(prefix="/api/v1", tags=["sample"])

SAMPLE_PATH = Path(__file__).resolve().parent.parent / "data" / "sample_report.json"


@lru_cache(maxsize=1)
def load_sample_report() -> ProjectReport:
    return ProjectReport.model_validate(json.loads(SAMPLE_PATH.read_text(encoding="utf-8")))


@router.get("/sample-report", response_model=ProjectReport)
def sample_report() -> ProjectReport:
    """A bundled report, so demos and offline tools work without GitHub."""
    return load_sample_report()
