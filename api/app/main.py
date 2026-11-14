from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.repositories import router as repositories_router
from app.core.config import settings

def create_app(app_settings=settings) -> FastAPI:
    application = FastAPI(title=app_settings.app_name)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(app_settings.cors_allowed_origins),
        allow_origin_regex=r"^https?://localhost:\d+$",
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )
    application.include_router(repositories_router)

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": app_settings.app_name}

    return application


app = create_app()
