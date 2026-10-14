from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from app import identity
from app.config import get_settings


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    get_settings()
    identity.get_directory()
    yield


app = FastAPI(
    title="Release Gate",
    lifespan=lifespan,
    dependencies=[Depends(identity.reject_suspended)],
)
app.include_router(identity.router)
app.include_router(identity.admin_router)


@app.get("/health")
def health() -> dict[str, str]:
    settings = get_settings()
    return {"status": "ok", "llm": "disabled" if settings.keyless else "enabled"}
