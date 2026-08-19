from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db import create_session_factory
from app.settings import Settings
from app.state_store import StateStore
from app.routers import approvers, config, decisions, ops, requests


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    session_factory, engine = create_session_factory(settings.database_url)
    app.state.settings = settings
    app.state.session_factory = session_factory
    app.state.engine = engine
    app.state.state_store = StateStore()
    yield
    engine.dispose()


app = FastAPI(title="Weir", lifespan=lifespan)
app.include_router(requests.router)
app.include_router(approvers.router)
app.include_router(decisions.router)
app.include_router(config.router)
app.include_router(ops.router)
app.mount("/", StaticFiles(directory="dashboard/static", html=True), name="dashboard")


def main():
    return app


if __name__ == "__main__":
    main()
