# Research: Training Plan Generation (Generic + Adaptive)

**Phase**: 0 — Outline & Research
**Date**: 2026-06-17
**Feature**: CU-TRAIN-04

---

## 1. Codebase Audit

### What exists and is correct

| File | Status | Notes |
|---|---|---|
| `train-service/app/infra/db/models/plan.py` | ✅ Complete | TrainingPlan, TrainingPlanPhase, TrainingPlanSession defined; schema inherited from BaseModel |
| `train-service/app/schemas/plan.py` | ✅ Complete | PlanGenerationRequest, PlanGenerationResponse correct |
| `train-service/app/services/plan_generator.py` | ✅ Complete | generate_generic_plan(), generate_adaptive_plan_structure(), all private helpers |
| `train-service/app/services/ia_workout_generator.py` | ✅ Complete | generate_next_week(), rule-based fallback, intensity adjustment |
| `train-service/app/routers/plans.py` | ⚠ Bug | sessions_created=0 hardcoded in reuse-by-clone branch (line ~113) |
| `train-service/app/services/plan_matcher.py` | 🚫 Incomplete | generate_profile_hash(), find_exact_match(), find_similar_plan(), _calculate_similarity() exist; **can_reuse_plan() and clone_plan() are absent** |
| `train-service/app/main.py` | ✅ Complete | plans router registered at /api/v1 |
| `train-service/app/infra/db/models/__init__.py` | ✅ Complete | All plan models exported |
| Alembic migrations | 🚫 Missing | Neither `5b19c8827569` nor `edb8199edb11` creates plan tables |
| OpenAPI contracts (CU-TRAIN-04) | 🚫 Missing | Directory does not exist |
| Test suite | 🚫 Missing | No test file for plans |

### Known tech debt in touched files (Constitution V)

`plan_generator.py` previously had `print()` statements — confirmed replaced with `logger` calls in the current branch state. `auth.py` and `session.py` still carry `print()` debt but are out of scope for this CU.

---

## 2. Decision: `can_reuse_plan` Signature & Behavior

**Decision**: `can_reuse_plan(profile_data: Dict[str, Any]) -> Tuple[bool, Optional[TrainingPlan], str]`

**Rationale**: The router unpacks a 3-tuple `(can_reuse, existing_plan, reason)` — the signature must match the existing call site in `plans.py` line ~95. Returning the reason string in position 3 lets the router surface it in the response `message` field without coupling to internal state.

**Logic**:
1. Generate `profile_hash = generate_profile_hash(profile_data)`
2. Try `find_exact_match(profile_hash)` → if not None, return `(True, plan, "Exact profile match found")`
3. Try `find_similar_plan(profile_data, threshold=0.80)` → if not None, return `(True, plan, "Similar plan found (≥80% match)")`
4. Return `(False, None, "No reusable plan found")`

---

## 3. Decision: `clone_plan` Signature & Behavior

**Decision**: `clone_plan(source_plan: TrainingPlan, profile_id: str) -> Tuple[TrainingPlan, int]`

**Rationale**: The router currently calls `plan = plan_matcher.clone_plan(existing_plan, profile_id)` and then hardcodes `sessions_created=0`. Changing the return type to `(TrainingPlan, int)` fixes the bug minimally — the router unpacks `plan, sessions_created = plan_matcher.clone_plan(...)` and passes the count through.

**Logic**:
1. Deactivate any existing active plan for `(profile_id, sport_id)` — soft state, set `is_active=False`.
2. Calculate new start/end dates anchored to `date.today()`.
3. Create a new `TrainingPlan` with the cloned athlete's `profile_id`, `original_plan_id = source_plan.id`, same `sport_id`, `plan_type`, `duration_weeks`, `profile_hash`, `source="ai"`.
4. For each `TrainingPlanPhase` on the source plan:
   a. Create a new `TrainingPlanPhase` with updated dates offset by the same delta as the plan start shift.
   b. For each `TrainingPlanSession` in that phase:
      - Fetch the original `TrainingSession` record.
      - Create a new `TrainingSession` with `profile_id` = the new athlete's profile_id and the same workout content (sport_id, status="planned", source="ai", planned_duration_minutes).
      - Clone all `TrainingSessionBlock` records for that session.
      - Create a new `TrainingPlanSession` linking the new plan → new phase → new session.
5. `db.commit()` once at the end.
6. Return `(new_plan, total_sessions_created)`.

**Why new sessions instead of reusing existing**: `TrainingSession.profile_id` identifies which athlete it belongs to. The athlete's completion tracking (status, executed_at) is per-session record. Sharing session records across athletes would corrupt individual tracking.

---

## 4. Decision: Alembic Migration Table Order

**Decision**: Single migration creates tables in dependency order:
1. `training_plan` (no FK to other new tables)
2. `training_plan_phase` (FK → `training_plan`)
3. `training_plan_session` (FK → `training_plan`, `training_plan_phase`, `training_session`)

**Rationale**: Alembic requires tables to exist before FK references are created. `training_session` already exists in migration `5b19c8827569`.

**Key indexes to create**:
- `ix_train_training_plan_profile_id` on training_plan(profile_id)
- `ix_train_training_plan_sport_id` on training_plan(sport_id)
- `ix_train_training_plan_goal_id` on training_plan(goal_id)
- `ix_train_training_plan_original_plan_id` on training_plan(original_plan_id)
- `ix_train_training_plan_profile_hash` on training_plan(profile_hash)
- `ix_train_training_plan_phase_plan_id` on training_plan_phase(plan_id)
- `ix_train_training_plan_session_plan_id` on training_plan_session(plan_id)
- `ix_train_training_plan_session_phase_id` on training_plan_session(phase_id)
- `ix_train_training_plan_session_session_id` on training_plan_session(session_id)

---

## 5. Decision: Router Bug Fix Approach

**Decision**: Change the router's reuse-by-clone branch to unpack the tuple returned by the updated `clone_plan`:

```python
# Before (bug)
plan = plan_matcher.clone_plan(existing_plan, profile_id)
sessions_created = 0

# After (fix)
plan, sessions_created = plan_matcher.clone_plan(existing_plan, profile_id)
```

No other changes to the router are needed.

---

## 6. Decision: Test Database Strategy

**Decision**: Use the Supabase PostgreSQL instance with a dedicated `test_train` schema (or use the existing `train` schema isolated via transaction rollback per test).

**Rationale**: The spec mandates real-DB tests. The safest approach is per-test transaction rollback (SQLAlchemy `Session.begin_nested()` + rollback) so tests are isolated without needing a separate schema. This mirrors the pattern already established in the project.

**Test structure**:
- `train-service/tests/test_plans.py` — pytest file with TestClient + real DB session
- Fixtures: `test_athlete_profile`, `test_context`, `mock_jwt_headers`, `db_session`
- Each test wraps DB operations in a transaction that rolls back after the test

---

## 7. Decision: OpenAPI Contract Files Location and Naming

**Decision**: Create 3 YAML files under `docs/product/Contract/Train-Service/CU-TRAIN-04/` following the existing `API CONTRACT – CU-TRAIN-XX – Verb Noun.yaml` naming pattern:

- `API CONTRACT – CU-TRAIN-04 – Generate Plan.yaml`
- `API CONTRACT – CU-TRAIN-04 – Get Active Plan.yaml`
- `API CONTRACT – CU-TRAIN-04 – Get Plan Schedule.yaml`

All use the BearerAuth + UserContext dual-security scheme convention established in CU-TRAIN-01/02/03.

---

## 8. Decision: plan.py File Structure Issue

**Observation**: In `plan.py`, `TrainingPlanPhase` is defined before the module docstring and `TrainingPlan` class. This works because SQLAlchemy resolves relationships lazily via string references (`"TrainingPlan"`, `"TrainingPlanSession"`), but it is non-standard Python. The file structure is accepted as-is since it is already committed and working.

---

## Summary of Decisions

| Topic | Decision | Why |
|---|---|---|
| can_reuse_plan return type | `Tuple[bool, Optional[TrainingPlan], str]` | Matches existing router call site |
| clone_plan return type | `Tuple[TrainingPlan, int]` | Enables bug fix with minimal router change |
| clone_plan session strategy | Create new sessions per-athlete | profile_id ownership + per-athlete tracking |
| Alembic migration | Single migration, dependency order | Clean lineage, no FK conflicts |
| Bug fix approach | Unpack tuple in router | Minimal change, no logic moved |
| Test DB | Real Supabase PostgreSQL, transaction rollback | Spec requirement, no mocks |
| Contract location | `docs/product/Contract/Train-Service/CU-TRAIN-04/` | Existing project convention |
