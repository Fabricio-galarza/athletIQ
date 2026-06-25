"""
Test suite for 002-generic-ia-plan-generation.

Coverage:
  US1 (T003–T004): AI-powered generic plan generation and reuse precedence
  US2 (T007–T008): Fallback when AI is unavailable or returns an invalid response
  US3 (T010):      Unchanged rule-based behavior for athletes without generic_ia

All tests use the real Supabase PostgreSQL instance via db_session with
per-test transaction rollback. IA calls are never made against a live API —
IAWorkoutGenerator.generate_full_plan_via_ia is monkeypatched in every test
that exercises the AI path (ia_enabled=False in .env for all environments).
"""

import logging
from datetime import date, timedelta

import httpx
import app.services.ia_workout_generator as ia_module
from app.infra.db.models.plan import TrainingPlan, TrainingPlanPhase, TrainingPlanSession
from app.infra.db.models.session import TrainingSession
from app.services.ia_workout_generator import IAWorkoutGenerator
from app.services.plan_matcher import PlanMatcher
from tests.conftest import GENERIC_IA_USER_ID, _build_context, seed_sport_profile


# ── Shared fixture builder ─────────────────────────────────────────────────────

def _build_ia_fixture(duration_weeks: int, days_per_week: int) -> dict:
    """
    Build the hardcoded JSON dict that simulates a successful IA full-plan response.

    Shape matches contracts/ia-generate-plan.yaml and the format defined in
    tasks.md T003: weeks → sessions → blocks (block_type, duration_minutes,
    intensity, instructions).

    This is the shared contract between T003 (success-path assertions) and T005
    (generate_full_plan_via_ia parser) — both must handle this exact structure.

    The fixture contains exactly duration_weeks weeks and exactly days_per_week
    sessions per week, so sessions_created == duration_weeks * days_per_week.
    """
    weeks = []
    for week_num in range(1, duration_weeks + 1):
        sessions = []
        for day in range(1, days_per_week + 1):
            sessions.append({
                "day": day,
                "name": f"Week {week_num} Day {day}",
                "duration_minutes": 45,
                "blocks": [
                    {
                        "block_type": "warmup",
                        "duration_minutes": 10,
                        "intensity": "easy",
                        "instructions": "Dynamic stretching and light jog",
                    },
                    {
                        "block_type": "main",
                        "duration_minutes": 30,
                        "intensity": "moderate",
                        "instructions": "Steady aerobic pace",
                    },
                    {
                        "block_type": "cooldown",
                        "duration_minutes": 5,
                        "intensity": "easy",
                        "instructions": "Static stretching",
                    },
                ],
            })
        weeks.append({
            "week_number": week_num,
            "focus": "build",
            "sessions": sessions,
        })
    return {"weeks": weeks}


def _seed_reusable_plan(
    db,
    profile_id,
    *,
    sport_id: str = "Running",
    weeks: int = 4,
    days_per_week: int = 4,
    profile_hash: str | None = None,
) -> tuple[TrainingPlan, int]:
    """
    Seed a complete generic plan that PlanMatcher.can_reuse_plan() will find.

    source="ai" is intentional — T002 must ensure clone_plan() overrides it to
    "template" on the cloned record, regardless of what the source plan carries.
    """
    today = date.today()
    plan = TrainingPlan(
        profile_id=profile_id,
        sport_id=sport_id,
        plan_type="generic",
        name="Seed Plan",
        duration_weeks=weeks,
        start_date=today,
        end_date=today + timedelta(weeks=weeks),
        is_active=True,
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


# ═══════════════════════════════════════════════════════════════════════════════
# US1 — AI-Powered Generic Plan Generation (P1)
# ═══════════════════════════════════════════════════════════════════════════════


def test_generic_ia_generates_ai_plan(
    generic_ia_client, db_session, generic_ia_profile, monkeypatch
):
    """
    US1 SC-001: athlete with generic_ia feature receives a complete AI-generated plan.

    generate_full_plan_via_ia is stubbed to return a valid 4-week/4-day fixture.
    ia_enabled is patched to True so the feature gate opens, decoupled from the
    ia_enabled=False value in .env.

    Fails before T005/T006:
    - Before T006: feature gate absent → stub is never called → calls assertion fails.
    - Before T005: method absent → monkeypatch.setattr would raise AttributeError
      (raising=False suppresses this so the stub is injected, but calls remains empty).
    """
    seed_sport_profile(db_session, generic_ia_profile.id, days_per_week=4)
    # No goal seeded → _calculate_plan_duration defaults to 4 weeks
    duration_weeks = 4
    days_per_week = 4
    expected_sessions = duration_weeks * days_per_week  # 16

    calls = []

    def _fake_generate_full_plan_via_ia(self, profile, duration_weeks, days_per_week, sport):
        calls.append(True)
        return _build_ia_fixture(duration_weeks, days_per_week)

    # raising=False allows the patch even before generate_full_plan_via_ia exists
    monkeypatch.setattr(
        IAWorkoutGenerator,
        "generate_full_plan_via_ia",
        _fake_generate_full_plan_via_ia,
        raising=False,
    )
    # ia_module.settings is the lru_cache singleton — patches plan_generator.py too
    monkeypatch.setattr(ia_module.settings, "ia_enabled", True)
    monkeypatch.setattr(ia_module.settings, "ia_api_url", "http://mock-ia.example.com")

    resp = generic_ia_client.post(
        "/api/v1/plans/generate",
        json={"sport_id": "Running", "plan_type": "generic", "force_regenerate": True},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["is_new_plan"] is True
    assert body["sessions_created"] == expected_sessions

    # Key assertion that distinguishes the AI path from rule-based:
    # the stub must have been invoked exactly once by generate_generic_plan().
    assert len(calls) == 1, "generate_full_plan_via_ia must be called exactly once"

    plan = db_session.query(TrainingPlan).filter_by(
        profile_id=generic_ia_profile.id,
        sport_id="Running",
        is_active=True,
    ).first()
    assert plan is not None
    assert plan.source == "ai", f"expected source='ai', got '{plan.source}'"


def test_generic_ia_reuse_takes_precedence(
    generic_ia_client, db_session, generic_ia_profile, monkeypatch
):
    """
    US1 SC-004: reuse/clone path takes precedence over IA when a matching plan exists.

    The router calls can_reuse_plan() before reaching generate_generic_plan(), so
    the feature gate and IA path are never evaluated. No IA monkeypatch is set up —
    any accidental call to generate_full_plan_via_ia would surface as an AttributeError
    (pre-T005) or a gate-blocked no-op (post-T005, ia_enabled=False in .env).

    Also validates the T002 fix: the seeded source plan has source="ai", but the
    clone produced by clone_plan() must carry source="template".
    """
    seed_sport_profile(db_session, generic_ia_profile.id, days_per_week=4)

    # Compute the hash that matches this athlete's seeded profile attributes.
    # Values must be strings — this is what seed_sport_profile stores in the DB.
    ctx = _build_context(GENERIC_IA_USER_ID, features=["generic_ia"])
    matcher = PlanMatcher(db_session, str(GENERIC_IA_USER_ID), "Running", ctx)
    profile_hash = matcher.generate_profile_hash({
        "level": "intermediate",
        "primary_goal": "improve_endurance",
        "days_per_week": "4",
    })

    # Seed the reusable plan (self-reuse: same profile_id, same sport).
    # source="ai" is deliberate — clone must override it to "template" (T002).
    source_plan, _ = _seed_reusable_plan(
        db_session, generic_ia_profile.id, profile_hash=profile_hash
    )

    resp = generic_ia_client.post(
        "/api/v1/plans/generate",
        json={"sport_id": "Running", "plan_type": "generic", "force_regenerate": False},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["is_new_plan"] is False
    assert body["reused_from_plan_id"] == str(source_plan.id)
    assert body["sessions_created"] > 0

    # The active plan after cloning must be a new record, not the source plan.
    cloned = db_session.query(TrainingPlan).filter_by(
        profile_id=generic_ia_profile.id,
        sport_id="Running",
        is_active=True,
    ).first()
    assert cloned is not None
    assert cloned.id != source_plan.id
    # T002 fix: clone must carry "template" even though source_plan.source == "ai"
    assert cloned.source == "template", (
        f"clone source must be 'template', got '{cloned.source}'"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# US2 — Rule-Based Fallback When AI Is Unavailable (P2)
# ═══════════════════════════════════════════════════════════════════════════════


def test_generic_ia_fallback_connection_error(
    generic_ia_client, db_session, generic_ia_profile, monkeypatch, caplog
):
    """
    US2 SC-002: when the IA API is unreachable, the system falls back to rule-based
    generation, returns HTTP 201 with a valid plan, and logs a WARNING.

    generate_full_plan_via_ia is stubbed to raise httpx.ConnectError (simulates
    connection refused). generate_generic_plan() catches it, logs at WARNING, and
    proceeds with rule-based generation — the client sees no error.
    """
    seed_sport_profile(db_session, generic_ia_profile.id, days_per_week=4)

    def _fake_raise_connect_error(self, profile, duration_weeks, days_per_week, sport):
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr(
        IAWorkoutGenerator,
        "generate_full_plan_via_ia",
        _fake_raise_connect_error,
        raising=False,
    )
    monkeypatch.setattr(ia_module.settings, "ia_enabled", True)
    monkeypatch.setattr(ia_module.settings, "ia_api_url", "http://mock-ia.example.com")

    with caplog.at_level(logging.WARNING, logger="app.services.plan_generator"):
        resp = generic_ia_client.post(
            "/api/v1/plans/generate",
            json={"sport_id": "Running", "plan_type": "generic", "force_regenerate": True},
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["is_new_plan"] is True
    assert body["sessions_created"] > 0

    plan = db_session.query(TrainingPlan).filter_by(
        profile_id=generic_ia_profile.id,
        sport_id="Running",
        is_active=True,
    ).first()
    assert plan is not None
    assert plan.source == "template", f"expected source='template', got '{plan.source}'"

    assert any(
        "IA API error for generic plan generation" in r.message
        for r in caplog.records
        if r.levelno == logging.WARNING
    ), "expected a WARNING log entry referencing 'IA API error for generic plan generation'"


def test_generic_ia_fallback_invalid_response(
    generic_ia_client, db_session, generic_ia_profile, monkeypatch
):
    """
    US2 SC-003: when the IA API returns a malformed response (no 'weeks' key),
    the system silently falls back to rule-based generation and returns HTTP 201.

    generate_full_plan_via_ia is stubbed to return {"missing_key": True}.
    generate_generic_plan() receives this, weeks_list resolves to [], the length
    check fails (0 != duration_weeks), and source is set to "template" — no error
    is raised and the client receives a valid plan.
    """
    seed_sport_profile(db_session, generic_ia_profile.id, days_per_week=4)

    def _fake_invalid_response(self, profile, duration_weeks, days_per_week, sport):
        return {"missing_key": True}

    monkeypatch.setattr(
        IAWorkoutGenerator,
        "generate_full_plan_via_ia",
        _fake_invalid_response,
        raising=False,
    )
    monkeypatch.setattr(ia_module.settings, "ia_enabled", True)
    monkeypatch.setattr(ia_module.settings, "ia_api_url", "http://mock-ia.example.com")

    resp = generic_ia_client.post(
        "/api/v1/plans/generate",
        json={"sport_id": "Running", "plan_type": "generic", "force_regenerate": True},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["is_new_plan"] is True
    assert body["sessions_created"] > 0

    plan = db_session.query(TrainingPlan).filter_by(
        profile_id=generic_ia_profile.id,
        sport_id="Running",
        is_active=True,
    ).first()
    assert plan is not None
    assert plan.source == "template", f"expected source='template', got '{plan.source}'"


# ═══════════════════════════════════════════════════════════════════════════════
# US3 — Unchanged Rule-Based Behavior Without generic_ia Feature (P3)
# ═══════════════════════════════════════════════════════════════════════════════


def test_generic_plan_without_ia_feature(
    test_client, db_session, athlete_profile
):
    """
    US3 SC-001: athlete WITHOUT the generic_ia feature receives a valid rule-based
    plan with source='template' — identical to pre-002 behavior.

    No IA monkeypatch needed. context.has_feature("generic_ia") is False for
    test_client (ATHLETE_USER_ID, no features), so ia_ok is False and the IA
    call is never attempted regardless of ia_enabled or ia_api_url values.
    """
    seed_sport_profile(db_session, athlete_profile.id, days_per_week=4)

    resp = test_client.post(
        "/api/v1/plans/generate",
        json={"sport_id": "Running", "plan_type": "generic", "force_regenerate": True},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["is_new_plan"] is True
    assert body["sessions_created"] > 0

    plan = db_session.query(TrainingPlan).filter_by(
        profile_id=athlete_profile.id,
        sport_id="Running",
        is_active=True,
    ).first()
    assert plan is not None
    assert plan.source == "template", f"expected source='template', got '{plan.source}'"
