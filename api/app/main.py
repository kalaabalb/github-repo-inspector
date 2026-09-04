from fastapi import FastAPI

from app.api.repositories import router as repositories_router
from app.core.config import settings

app = FastAPI(title=settings.app_name)
app.include_router(repositories_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}
