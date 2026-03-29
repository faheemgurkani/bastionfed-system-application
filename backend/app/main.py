from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.bastionbot import bastionbot_engine, bastionbot_store
from app.config import settings
from app.store.memory import state


@asynccontextmanager
async def lifespan(_app: FastAPI):
    bastionbot_store.configure(settings.bastionbot_db_path)
    bastionbot_engine.initialize()
    state.reset()
    yield


app = FastAPI(title=settings.api_title, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routers import (  # noqa: E402
    alerts,
    audit,
    auth,
    bastionbot,
    dashboard,
    devices,
    events,
    fl,
    forensics,
    incidents,
)

app.include_router(alerts.router, prefix="/api")
app.include_router(incidents.router, prefix="/api")
app.include_router(fl.router, prefix="/api")
app.include_router(forensics.router, prefix="/api")
app.include_router(devices.router, prefix="/api")
app.include_router(audit.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(bastionbot.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(events.router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}
