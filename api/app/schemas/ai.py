from pydantic import BaseModel, Field

from app.schemas.report import ProjectReport


class AIProjectExplanation(BaseModel):
    summary: str = ""
    how_it_works: list[str] = Field(default_factory=list)
    architecture_explanation: list[str] = Field(default_factory=list)
    technology_explanations: list[str] = Field(default_factory=list)
    api_explanation: str | None = None
    authentication_explanation: str | None = None
    data_explanation: str | None = None
    learning_roadmap: list[str] = Field(default_factory=list)
    interview_questions: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)


class AIExplanationResponse(BaseModel):
    available: bool
    provider: str = "gemini"
    model: str | None = None
    explanation: AIProjectExplanation | None = None
    reason: str | None = None


class ExplainRequest(BaseModel):
    report: ProjectReport
