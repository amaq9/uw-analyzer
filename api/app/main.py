from fastapi import FastAPI
from pydantic import BaseModel

from app import __version__


class Health(BaseModel):
    status: str
    version: str


def create_app() -> FastAPI:
    app = FastAPI(title="UW Analyzer API", version=__version__)

    @app.get("/health", response_model=Health, tags=["ops"])
    def health() -> Health:
        """Liveness check. Reports service status only; no case or tenant data."""
        return Health(status="ok", version=__version__)

    return app


app = create_app()
