"""
Test suite for CU-TRAIN-04: Training Plan Generation (Generic + Adaptive).

Coverage:
  US1 (T007–T016): POST /api/v1/plans/generate — generic plan
  US2 (T017–T022): POST /api/v1/plans/generate — adaptive plan
  US3 (T023–T028): GET /api/v1/plans/active, GET /api/v1/plans/{id}/schedule

All tests use the real Supabase PostgreSQL instance via db_session with
per-test transaction rollback. No SQLite, no mocks for DB operations.
Service-level async tests use asyncio.run() to invoke async methods directly.
"""

import asyncio
import uuid
from datetime import date, timedelta

import pytest

import app.services.ia_workout_generator as ia_module
from app.core.exceptions import ValidationError
from app.infra.db.models.athlete import AthleteProfile
from app.infra.db.models.plan import TrainingPlan, TrainingPlanPhase, TrainingPlanSession
from app.infra.db.models.session import TrainingSession
from app.infra.db.models.sport_profile import AthleteSportProfile, AthleteSportProfileValue
from app.services.ia_workout_generator import IAWorkoutGenerator
from app.services.plan_matcher import PlanMatcher
from tests.conftest import (
    ATHLETE_B_USER_ID,
    ATHLETE_USER_ID,
    DAYS_FIELD_ID,
    GOAL_FIELD_ID,
    LEVEL_FIELD_ID,
    WEEKLY_FREQ_FIELD_ID,
    _build_context,
    seed_sport_profile,
)

# ── Shared seed helpers ────────────────────────────────────────────────────────


def _seed_plan(
    db,
    profile_id,
    *,
    sport_id: str = "Running",
    plan_type: str = "generic",
    weeks: int = 4,
    days_per_week: int = 4,
    profile_hash: str | None = None,
    is_active: bool = True,
) -> tuple[TrainingPlan, int]:
    """Seed a complete TrainingPlan with phases and sessions. Returns (plan, session_count)."""
    today = date.today()
    plan = TrainingPlan(
        profile_id=profile_id,
        sport_id=sport_id,
        plan_type=plan_type,
        name=f"Test Plan",
        duration_weeks=weeks,
        start_date=today,
        end_date=today + timedelta(weeks=weeks),
        is_active=is_active,
        source="ai",
        profile_hash=profile_hash,
    )
    db.add(plan)
    db.flush()

    count = 0
    for week in range(1, weeks + 1):
        phase_start = today + timedelta(weeks=week - 1)
        phase = TrainingPlanPhase(
            plan_id=plan.id,
            name=f"Week {week}",
            week_number=week,
            start_date=phase_start,
            end_date=phase_start + timedelta(days=6),
            focus="build",
        )
        db.add(phase)
        db.flush()

        for day in range(1, days_per_week + 1):
            session = TrainingSession(
                profile_id=profile_id,
                sport_id=sport_id,
                status="planned",
                source="ai",
                planned_date=phase_start + timedelta(days=day - 1),
                planned_duration_minutes=45,
            )
            db.add(session)
            db.flush()

            db.add(TrainingPlanSession(
                plan_id=plan.id,
                phase_id=phase.id,
                session_id=session.id,
                week_number=week,
                day_number=day,
                scheduled_date=phase_start + timedelta(days=day - 1),
                order=day,
            ))
            count += 1

    db.flush()
    return plan, count


def _setup_adaptive_plan(
    db,
    profile_id,
    *,
    weeks_generated: int = 1,
    total_weeks: int = 4,
    days_per_week: int = 4,
) -> TrainingPlan:
    """Seed an adaptive TrainingPlan with N weeks already generated."""
    today = date.today()
    plan = TrainingPlan(
        profile_id=profile_id,
        sport_id="Running",
        plan_type="adaptive",
        duration_weeks=total_weeks,
        start_date=today,
        end_date=today + timedelta(weeks=total_weeks),
        is_active=True,
        source="ai",
    )
    db.add(plan)
    db.flush()

    for week in range(1, weeks_generated + 1):
        phase_start = today + timedelta(weeks=week - 1)
        phase = TrainingPlanPhase(
            plan_id=plan.id,
            name=f"Week {week}",
            week_number=week,
            start_date=phase_start,
            end_date=phase_start + timedelta(days=6),
            focus="build",
        )
        db.add(phase)
        db.flush()

        for day in range(1, days_per_week + 1):
            s = TrainingSession(
                profile_id=profile_id,
                sport_id="Running",
                status="planned",
                source="ai",
                planned_date=phase_start + timedelta(days=day - 1),
                planned_duration_minutes=45,
            )
            db.add(s)
            db.flush()
            db.add(TrainingPlanSession(
                plan_id=plan.id,
                phase_id=phase.id,
                session_id=s.id,
                week_number=week,
                day_number=day,
                order=day,
            ))

    db.flush()
    return plan


def _profile_hash_for(db, user_id, sport_id="Running") -> str:
    """Compute the profile hash for a user's current sport profile data."""
    ctx = _build_context(uuid.UUID(str(user_id)) if isinstance(user_id, str) else user_id)
    matcher = PlanMatcher(db, str(user_id), sport_id, ctx)
    # Values must match what seed_sport_profile seeds (strings)
    profile_data = {
        "level": "intermediate",
        "primary_goal": "improve_endurance",
        "days_per_week": "4",
    }
    return matcher.generate_profile_hash(profile_data)


# ═══════════════════════════════════════════════════════════════════════════════
# US1 — Generate Generic Training Plan
# ═══════════════════════════════════════════════════════════════════════════════


def test_generate_generic_plan_new(test_client, db_session, athlete_profile):
    """POST /plans/generate creates a fresh generic plan when no match exists."""
    seed_sport_profile(db_session, athlete_profile.id, days_per_week=4)

    resp = test_client.post(
        "/api/v1/plans/generate",
        json={"sport_id": "Running", "plan_type": "generic", "force_regenerate": False},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["is_new_plan"] is True
    assert body["plan_id"] is not None
    assert body["sessions_created"] == 16  # 4 weeks × 4 days
    assert body["total_weeks"] == 4

    plan = db_session.query(TrainingPlan).filter_by(
        profile_id=athlete_profile.id, sport_id="Running", is_active=True
    ).first()
    assert plan is not None
    assert len(db_session.query(TrainingPlanPhase).filter_by(plan_id=plan.id).all()) == 4
    assert db_session.query(TrainingPlanSession).filter_by(plan_id=plan.id).count() == 16


def test_generate_generic_plan_exact_reuse(
    test_client, db_session, athlete_profile, athlete_b_profile
):
    """When an exact profile hash match exists, the plan is cloned (not regenerated)."""
    # Compute hash for the standard 4-day profile
    profile_hash = _profile_hash_for(db_session, ATHLETE_B_USER_ID)

    # Seed athlete B's plan with that hash (the template to clone from)
    _seed_plan(db_session, athlete_b_profile.id, profile_hash=profile_hash)

    # Seed athlete A with the same profile attributes → same hash
    seed_sport_profile(db_session, athlete_profile.id, days_per_week=4)

    resp = test_client.post(
        "/api/v1/plans/generate",
        json={"sport_id": "Running", "plan_type": "generic", "force_regenerate": False},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["is_new_plan"] is False
    assert body["reused_from_plan_id"] is not None
    # Bug fix verification: sessions_created must NOT be hardcoded 0
    assert body["sessions_created"] > 0


def test_generate_generic_plan_similarity_reuse(
    test_client, db_session, athlete_profile, athlete_b_profile
):
    """A plan with ≥80% profile similarity is cloned when no exact match exists."""
    # Athlete B: 4 days + 4 weekly_frequency → seeded as source template
    seed_sport_profile(
        db_session, athlete_b_profile.id,
        days_per_week=4, weekly_frequency=4,
    )
    # Seed a complete plan for athlete B (no profile_hash → won't match exact)
    _seed_plan(db_session, athlete_b_profile.id)

    # Athlete A: 5 days + 5 weekly_frequency → differs by 1 in both numerics
    # Similarity: 0.30 (level) + 0.30 (goal) + 0.133 (days) + 0.133 (freq) = 0.867 ≥ 0.80
    seed_sport_profile(
        db_session, athlete_profile.id,
        days_per_week=5, weekly_frequency=5,
    )

    resp = test_client.post(
        "/api/v1/plans/generate",
        json={"sport_id": "Running", "plan_type": "generic", "force_regenerate": False},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["is_new_plan"] is False
    assert body["sessions_created"] > 0


def test_generate_generic_plan_force_regenerate(
    test_client, db_session, athlete_profile, athlete_b_profile
):
    """force_regenerate=True skips reuse even when an exact hash match exists."""
    profile_hash = _profile_hash_for(db_session, ATHLETE_B_USER_ID)
    _seed_plan(db_session, athlete_b_profile.id, profile_hash=profile_hash)
    seed_sport_profile(db_session, athlete_profile.id, days_per_week=4)

    resp = test_client.post(
        "/api/v1/plans/generate",
        json={"sport_id": "Running", "plan_type": "generic", "force_regenerate": True},
    )

    assert resp.status_code == 201
    assert resp.json()["is_new_plan"] is True


def test_generate_plan_incomplete_profile(test_client, db_session, athlete_profile):
    """Missing required field short-circuits with success=False; no plan row created."""
    # Sport profile without 'level'
    sp = AthleteSportProfile(profile_id=athlete_profile.id, sport_id="Running")
    db_session.add(sp)
    db_session.flush()
    db_session.add(AthleteSportProfileValue(
        sport_profile_id=sp.id, field_id=GOAL_FIELD_ID, value="improve_endurance"
    ))
    db_session.add(AthleteSportProfileValue(
        sport_profile_id=sp.id, field_id=DAYS_FIELD_ID, value="4"
    ))
    db_session.flush()

    resp = test_client.post(
        "/api/v1/plans/generate",
        json={"sport_id": "Running", "plan_type": "generic"},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is False
    assert body["plan_id"] is None
    assert body["sessions_created"] == 0
    assert db_session.query(TrainingPlan).filter_by(profile_id=athlete_profile.id).count() == 0


def test_generate_plan_sport_not_configured(test_client, athlete_profile):
    """Requesting a sport not in the user context returns HTTP 400."""
    resp = test_client.post(
        "/api/v1/plans/generate",
        json={"sport_id": "Football", "plan_type": "generic"},
    )

    assert resp.status_code == 400


def test_generate_plan_no_auth(raw_client):
    """POST without Authorization header returns HTTP 401 or 403."""
    resp = raw_client.post(
        "/api/v1/plans/generate",
        json={"sport_id": "Running", "plan_type": "generic"},
    )

    assert resp.status_code in (401, 403)


def test_generate_plan_soft_state_enforcement(test_client, db_session, athlete_profile):
    """Two consecutive generations leave exactly 1 active and 1 inactive plan."""
    seed_sport_profile(db_session, athlete_profile.id, days_per_week=4)

    test_client.post(
        "/api/v1/plans/generate",
        json={"sport_id": "Running", "plan_type": "generic", "force_regenerate": True},
    )
    test_client.post(
        "/api/v1/plans/generate",
        json={"sport_id": "Running", "plan_type": "generic", "force_regenerate": True},
    )

    plans = db_session.query(TrainingPlan).filter_by(
        profile_id=athlete_profile.id, sport_id="Running"
    ).all()
    assert sum(1 for p in plans if p.is_active) == 1
    assert sum(1 for p in plans if not p.is_active) == 1


def test_generate_plan_clone_deactivates_existing_active_plan(
    test_client, db_session, athlete_profile, athlete_b_profile
):
    """clone_plan deactivates athlete A's pre-existing active plan (FR-006/FR-024)."""
    # Pre-existing active plan for athlete A (will be deactivated by clone)
    _seed_plan(db_session, athlete_profile.id, is_active=True)

    # Athlete A's profile (drives the hash that we store in athlete B's plan)
    seed_sport_profile(db_session, athlete_profile.id, days_per_week=4)
    profile_hash = _profile_hash_for(db_session, ATHLETE_USER_ID)

    # Athlete B's plan is the template — seeded with athlete A's hash
    _seed_plan(db_session, athlete_b_profile.id, profile_hash=profile_hash)

    resp = test_client.post(
        "/api/v1/plans/generate",
        json={"sport_id": "Running", "plan_type": "generic", "force_regenerate": False},
    )

    assert resp.status_code == 201
    assert resp.json()["is_new_plan"] is False  # clone path triggered

    plans_a = db_session.query(TrainingPlan).filter_by(
        profile_id=athlete_profile.id, sport_id="Running"
    ).all()
    assert sum(1 for p in plans_a if p.is_active) == 1      # new clone
    assert sum(1 for p in plans_a if not p.is_active) == 1  # deactivated pre-existing


def test_generate_plan_self_reuse(test_client, db_session, athlete_profile):
    """Self-reuse: athlete clones their own plan; new plan anchored to today."""
    seed_sport_profile(db_session, athlete_profile.id, days_per_week=4)
    profile_hash = _profile_hash_for(db_session, ATHLETE_USER_ID)

    # Athlete A already has a plan matching their own profile hash
    original_plan, _ = _seed_plan(
        db_session, athlete_profile.id,
        profile_hash=profile_hash,
        is_active=True,
    )
    original_start = original_plan.start_date

    resp = test_client.post(
        "/api/v1/plans/generate",
        json={"sport_id": "Running", "plan_type": "generic", "force_regenerate": False},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["is_new_plan"] is False
    assert body["reused_from_plan_id"] == str(original_plan.id)

    # The clone's start_date must be anchored to today, not the original's start_date
    new_plan = db_session.query(TrainingPlan).filter_by(
        profile_id=athlete_profile.id,
        sport_id="Running",
        is_active=True,
    ).first()
    assert new_plan is not None
    assert new_plan.id != original_plan.id
    assert new_plan.start_date == date.today()


# ═══════════════════════════════════════════════════════════════════════════════
# US2 — Generate Adaptive Training Plan
# ═══════════════════════════════════════════════════════════════════════════════


def test_generate_adaptive_plan_premium(premium_client, db_session, premium_profile):
    """Premium athlete gets adaptive plan: header + week 1 only."""
    seed_sport_profile(db_session, premium_profile.id, days_per_week=4)

    resp = premium_client.post(
        "/api/v1/plans/generate",
        json={"sport_id": "Running", "plan_type": "adaptive"},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["is_new_plan"] is True
    assert body["plan_type"] == "adaptive"
    assert body["sessions_created"] == 4  # days_per_week=4

    plan = db_session.query(TrainingPlan).filter_by(
        profile_id=premium_profile.id, sport_id="Running", is_active=True
    ).first()
    assert plan is not None
    assert plan.plan_type == "adaptive"

    phases = db_session.query(TrainingPlanPhase).filter_by(plan_id=plan.id).all()
    assert len(phases) == 1
    assert phases[0].week_number == 1

    assert db_session.query(TrainingPlanSession).filter_by(plan_id=plan.id).count() == 4


def test_generate_adaptive_plan_non_premium(test_client):
    """Non-premium athlete requesting adaptive plan gets HTTP 403."""
    resp = test_client.post(
        "/api/v1/plans/generate",
        json={"sport_id": "Running", "plan_type": "adaptive"},
    )

    assert resp.status_code == 403
    assert "Adaptive training feature not available" in resp.json()["detail"]


def test_generate_next_week_default_intensity(db_session, athlete_profile):
    """generate_next_week with no prior metrics produces week 2 sessions."""
    plan = _setup_adaptive_plan(db_session, athlete_profile.id, weeks_generated=1)

    generator = IAWorkoutGenerator(db_session, str(ATHLETE_USER_ID), "Running")
    profile_data = {
        "level": "intermediate",
        "primary_goal": "improve_endurance",
        "days_per_week": "4",
    }

    sessions = asyncio.run(
        generator.generate_next_week(str(plan.id), profile_data, previous_metrics=[])
    )

    assert len(sessions) == 4

    phases = db_session.query(TrainingPlanPhase).filter_by(plan_id=plan.id).all()
    assert len(phases) == 2
    week_numbers = sorted(p.week_number for p in phases)
    assert week_numbers == [1, 2]


def test_generate_next_week_high_completion_increases_intensity(db_session, athlete_profile):
    """High completion (≥90%, difficulty ≤4) yields intensity multiplier > 1.0."""
    generator = IAWorkoutGenerator(db_session, str(ATHLETE_USER_ID), "Running")

    high_metrics = [{"completion_percentage": 95, "difficulty": 3}]
    multiplier = generator._calculate_intensity_adjustment(high_metrics)
    assert multiplier > 1.0

    # Also verify the full generate_next_week flow runs without error
    plan = _setup_adaptive_plan(db_session, athlete_profile.id, weeks_generated=1)
    profile_data = {
        "level": "intermediate",
        "primary_goal": "improve_endurance",
        "days_per_week": "4",
    }

    sessions = asyncio.run(
        generator.generate_next_week(str(plan.id), profile_data, previous_metrics=high_metrics)
    )
    assert len(sessions) == 4


def test_generate_next_week_ai_failure_falls_back_to_rules(
    db_session, athlete_profile, monkeypatch
):
    """When IA API is unreachable, rule-based generation runs transparently (FR-009)."""
    monkeypatch.setattr(ia_module.settings, "ia_enabled", True)
    monkeypatch.setattr(ia_module.settings, "ia_api_url", "http://127.0.0.1:19999")

    plan = _setup_adaptive_plan(db_session, athlete_profile.id, weeks_generated=1)

    generator = IAWorkoutGenerator(db_session, str(ATHLETE_USER_ID), "Running")
    profile_data = {
        "level": "intermediate",
        "primary_goal": "improve_endurance",
        "days_per_week": "4",
    }

    # Must NOT raise — AI failure is silent, rule-based fallback kicks in
    sessions = asyncio.run(
        generator.generate_next_week(str(plan.id), profile_data, previous_metrics=[])
    )

    assert len(sessions) > 0

    week2_phase = db_session.query(TrainingPlanPhase).filter_by(
        plan_id=plan.id, week_number=2
    ).first()
    assert week2_phase is not None


def test_generate_next_week_exhausted_weeks_raises_validation_error(
    db_session, athlete_profile
):
    """generate_next_week past duration_weeks raises ValidationError (plan guard)."""
    plan = _setup_adaptive_plan(
        db_session, athlete_profile.id, weeks_generated=2, total_weeks=2
    )

    generator = IAWorkoutGenerator(db_session, str(ATHLETE_USER_ID), "Running")
    profile_data = {
        "level": "intermediate",
        "primary_goal": "improve_endurance",
        "days_per_week": "4",
    }

    with pytest.raises(ValidationError) as exc_info:
        asyncio.run(
            generator.generate_next_week(str(plan.id), profile_data, previous_metrics=[])
        )

    msg = str(exc_info.value).lower()
    assert "all weeks" in msg or "completed" in msg


# ═══════════════════════════════════════════════════════════════════════════════
# US3 — Retrieve Active Plan and Schedule
# ═══════════════════════════════════════════════════════════════════════════════


def test_get_active_plan_exists(test_client, db_session, athlete_profile):
    """GET /plans/active returns has_active_plan=true with correct plan metadata."""
    plan, total = _seed_plan(
        db_session, athlete_profile.id, weeks=2, days_per_week=3
    )

    resp = test_client.get("/api/v1/plans/active?sport_id=Running")

    assert resp.status_code == 200
    body = resp.json()
    assert body["has_active_plan"] is True
    plan_data = body["plan"]
    assert plan_data["id"] == str(plan.id)
    assert plan_data["total_sessions"] == total  # 2 × 3 = 6
    assert plan_data["plan_type"] == "generic"
    assert plan_data["duration_weeks"] == 2
    assert plan_data["source"] == "ai"


def test_get_active_plan_none_exists(test_client, db_session, athlete_profile):
    """GET /plans/active returns has_active_plan=false when athlete has no active plan."""
    resp = test_client.get("/api/v1/plans/active?sport_id=Running")

    assert resp.status_code == 200
    body = resp.json()
    assert body["has_active_plan"] is False
    assert body["plan"] is None


def test_get_plan_schedule_happy_path(test_client, db_session, athlete_profile):
    """GET /plans/{id}/schedule returns phases ordered by week_number, sessions by day_number."""
    plan, _ = _seed_plan(db_session, athlete_profile.id, weeks=2, days_per_week=3)

    resp = test_client.get(f"/api/v1/plans/{plan.id}/schedule")

    assert resp.status_code == 200
    body = resp.json()
    assert body["plan_id"] == str(plan.id)
    assert body["total_weeks"] == 2

    schedule = body["schedule"]
    assert len(schedule) == 2
    # Phases ordered ascending by week_number
    assert schedule[0]["week_number"] == 1
    assert schedule[1]["week_number"] == 2
    # Sessions within each phase ordered by day_number
    day_numbers = [s["day_number"] for s in schedule[0]["sessions"]]
    assert day_numbers == sorted(day_numbers)
    assert len(schedule[0]["sessions"]) == 3


def test_get_plan_schedule_not_found(test_client, athlete_profile):
    """GET /plans/{random_uuid}/schedule returns 404."""
    resp = test_client.get(f"/api/v1/plans/{uuid.uuid4()}/schedule")

    assert resp.status_code == 404


def test_get_plan_schedule_wrong_owner(
    test_client, db_session, athlete_profile, athlete_b_profile
):
    """Plan belonging to athlete B is not visible to athlete A (returns 404, not 403)."""
    plan_b, _ = _seed_plan(db_session, athlete_b_profile.id)

    resp = test_client.get(f"/api/v1/plans/{plan_b.id}/schedule")

    assert resp.status_code == 404


def test_get_active_plan_and_schedule_auth_errors(raw_client):
    """Both GET endpoints reject unauthenticated requests with 401 or 403."""
    resp1 = raw_client.get("/api/v1/plans/active?sport_id=Running")
    assert resp1.status_code in (401, 403)

    resp2 = raw_client.get(f"/api/v1/plans/{uuid.uuid4()}/schedule")
    assert resp2.status_code in (401, 403)
