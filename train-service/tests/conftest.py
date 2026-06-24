"""
Pytest configuration for train-service plan tests.

Uses the real Supabase PostgreSQL instance. Per-test isolation is achieved via
an outer transaction that is rolled back after each test (no DDL changes needed).

JWT signature verification is disabled (verify_signature=False) — this is
pre-existing tech debt (Constitution Sec partial). Any well-formed JWT passes.
"""

import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.cache import cache
from app.core.context import UserContext, get_user_context
from app.infra.db.models.athlete import AthleteProfile
from app.infra.db.models.sport_profile import AthleteSportProfile, AthleteSportProfileValue
from app.infra.db.session import engine, get_db
from app.main import app

# ── Fixed UUIDs ────────────────────────────────────────────────────────────────
# Predictable across all tests; rolled back after each test so no collision risk.

ATHLETE_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
PREMIUM_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
ATHLETE_B_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000003")

# Field UUIDs used in the test UserContext forms and DB value rows.
# They do NOT exist in core.field — similarity matching now uses context forms.
LEVEL_FIELD_ID = uuid.UUID("10000000-0000-0000-0000-000000000001")
GOAL_FIELD_ID = uuid.UUID("10000000-0000-0000-0000-000000000002")
DAYS_FIELD_ID = uuid.UUID("10000000-0000-0000-0000-000000000003")
WEEKLY_FREQ_FIELD_ID = uuid.UUID("10000000-0000-0000-0000-000000000004")

_ATHLETE_PROFILE_FORM = {
    "id": "a0000000-0000-0000-0000-000000000001",
    "name": "Athlete Profile",
    "code": "athlete_profile",
    "module": None,
    "fields": [
        {
            "id": str(LEVEL_FIELD_ID),
            "name": "level",
            "label": "Level",
            "type": "select",
            "required": True,
            "order": 1,
            "options": [
                {"value": "beginner"},
                {"value": "intermediate"},
                {"value": "advanced"},
                {"value": "elite"},
            ],
            "UI-config": {},
        },
        {
            "id": str(GOAL_FIELD_ID),
            "name": "primary_goal",
            "label": "Primary Goal",
            "type": "select",
            "required": True,
            "order": 2,
            "options": [
                {"value": "improve_endurance"},
                {"value": "lose_weight"},
                {"value": "build_strength"},
            ],
            "UI-config": {},
        },
        {
            "id": str(DAYS_FIELD_ID),
            "name": "days_per_week",
            "label": "Days Per Week",
            "type": "number",
            "required": True,
            "order": 3,
            "options": [],
            "UI-config": {},
        },
        {
            "id": str(WEEKLY_FREQ_FIELD_ID),
            "name": "weekly_frequency",
            "label": "Weekly Frequency",
            "type": "number",
            "required": False,
            "order": 4,
            "options": [],
            "UI-config": {},
        },
    ],
}


def _build_context(
    user_id: uuid.UUID,
    features: list | None = None,
    sports: list | None = None,
) -> UserContext:
    """Build a UserContext suitable for test use."""
    return UserContext({
        "user_id": str(user_id),
        "email": f"test+{str(user_id)[-4:]}@example.com",
        "roles": ["athlete"],
        "features": features or [],
        "sports": sports or ["Running"],
        "plans": [],
        "forms": [_ATHLETE_PROFILE_FORM],
    })


# ── Cache lifecycle mock ────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def mock_cache_lifecycle():
    """Patch Redis connect/disconnect so tests don't require a live Redis server."""
    with patch.object(cache, "connect", new_callable=AsyncMock):
        with patch.object(cache, "disconnect", new_callable=AsyncMock):
            yield


# ── DB session with transaction rollback ───────────────────────────────────────

@pytest.fixture
def db_session():
    """
    Provide a per-test DB session with full rollback on teardown.

    Uses an outer connection transaction so all ORM commits (including those
    inside services) stay within the same connection and are undone after the test.
    SQLAlchemy 2.0 join_transaction_mode="create_savepoint" keeps the outer
    transaction open even when session.commit() is called inside the service.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    transaction.rollback()
    connection.close()


# ── Context fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def athlete_context() -> UserContext:
    return _build_context(ATHLETE_USER_ID)


@pytest.fixture
def premium_context() -> UserContext:
    return _build_context(PREMIUM_USER_ID, features=["adaptive_training"])


@pytest.fixture
def athlete_b_context() -> UserContext:
    return _build_context(ATHLETE_B_USER_ID)


# ── TestClient factories ───────────────────────────────────────────────────────

def _make_client(db_session: Session, context: UserContext) -> TestClient:
    """Create a TestClient with DB + auth overrides for the given context."""

    def _override_db():
        yield db_session

    def _override_ctx():
        return context

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_user_context] = _override_ctx
    return TestClient(app)


def _clear_overrides() -> None:
    app.dependency_overrides.clear()


@pytest.fixture
def test_client(db_session, athlete_context):
    """TestClient authenticated as the default test athlete."""
    client = _make_client(db_session, athlete_context)
    yield client
    _clear_overrides()


@pytest.fixture
def premium_client(db_session, premium_context):
    """TestClient authenticated as the premium test athlete."""
    client = _make_client(db_session, premium_context)
    yield client
    _clear_overrides()


@pytest.fixture
def athlete_b_client(db_session, athlete_b_context):
    """TestClient authenticated as athlete B (for cross-ownership tests)."""
    client = _make_client(db_session, athlete_b_context)
    yield client
    _clear_overrides()


@pytest.fixture
def raw_client(db_session):
    """TestClient with DB override only — no auth override (tests real 401/403)."""

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides.pop(get_user_context, None)
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    _clear_overrides()


# ── DB seeding helpers ─────────────────────────────────────────────────────────

@pytest.fixture
def athlete_profile(db_session) -> AthleteProfile:
    """Insert a minimal AthleteProfile for the default test athlete."""
    profile = AthleteProfile(user_id=ATHLETE_USER_ID)
    db_session.add(profile)
    db_session.flush()
    return profile


@pytest.fixture
def premium_profile(db_session) -> AthleteProfile:
    """Insert a minimal AthleteProfile for the premium test athlete."""
    profile = AthleteProfile(user_id=PREMIUM_USER_ID)
    db_session.add(profile)
    db_session.flush()
    return profile


@pytest.fixture
def athlete_b_profile(db_session) -> AthleteProfile:
    """Insert a minimal AthleteProfile for test athlete B."""
    profile = AthleteProfile(user_id=ATHLETE_B_USER_ID)
    db_session.add(profile)
    db_session.flush()
    return profile


def seed_sport_profile(
    db: Session,
    profile_id: uuid.UUID,
    *,
    sport_id: str = "Running",
    level: str = "intermediate",
    primary_goal: str = "improve_endurance",
    days_per_week: int = 4,
    weekly_frequency: int | None = None,
) -> AthleteSportProfile:
    """Seed AthleteSportProfile + value rows using the test field UUIDs."""
    sp = AthleteSportProfile(profile_id=profile_id, sport_id=sport_id)
    db.add(sp)
    db.flush()

    values = [
        (LEVEL_FIELD_ID, level),
        (GOAL_FIELD_ID, primary_goal),
        (DAYS_FIELD_ID, str(days_per_week)),
    ]
    if weekly_frequency is not None:
        values.append((WEEKLY_FREQ_FIELD_ID, str(weekly_frequency)))

    for field_id, value in values:
        db.add(AthleteSportProfileValue(
            sport_profile_id=sp.id,
            field_id=field_id,
            value=value,
        ))
    db.flush()
    return sp
