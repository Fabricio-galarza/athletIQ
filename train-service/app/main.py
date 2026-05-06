from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.config import get_settings
from app.infra.db.session import check_db_connection
from app.core.cache import cache
from app.api.v1 import athlete

from app.routers import evaluation, workout, onboarding, training_structure

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles startup and shutdown events."""
    # Startup
    print("Starting Train Service...")
    await cache.connect()
    yield
    # Shutdown
    print("Shutting down Train Service...")
    await cache.disconnect()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan  # 🔥 Add lifespan
)

# Register router
app.include_router(athlete.router, prefix="/api/v1")

app.include_router(workout.router, prefix="/api/v1")

app.include_router(evaluation.router, prefix="/api/v1")
app.include_router(onboarding.router, prefix="/api/v1")

app.include_router(training_structure.router, prefix="/api/v1")


@app.get("/health/live")
def liveness():
    return {"status": "alive"}


@app.get("/health/ready")
def readiness():
    db_ok = check_db_connection()
    if not db_ok:
        return {"status": "not_ready", "db": "down"}
    return {"status": "ready", "db": "up"}