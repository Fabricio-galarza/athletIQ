# Quickstart: Validating Training Plan Generation

**Phase**: 1 — Design & Contracts
**Date**: 2026-06-17
**Feature**: CU-TRAIN-04

---

## Prerequisites

1. `train-service` running on port 8001 (`uvicorn app.main:app --reload --port 8001`)
2. `core-service` running on port 8000 (issues JWTs and X-User-Context)
3. Alembic migration applied: `alembic upgrade head` (plan tables must exist in `train` schema)
4. Athlete with complete profile: has `level`, `primary_goal`, and `days_per_week` in their sport profile
5. `.env` has `IA_ENABLED=false` (use rule-based generation; avoids external API dependency in validation)

---

## Scenario 1: Generate a Generic Plan (Happy Path)

**Validates**: FR-001, FR-002, FR-004, FR-007, SC-001

```bash
# Get JWT and X-User-Context from core-service login (adjust to your test athlete credentials)
TOKEN="<athlete_jwt>"
CONTEXT="<base64_x_user_context>"

curl -X POST http://localhost:8001/api/v1/plans/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-User-Context: $CONTEXT" \
  -H "Content-Type: application/json" \
  -d '{"sport_id": "Running", "plan_type": "generic", "force_regenerate": false}'
```

**Expected response** (HTTP 201):
```json
{
  "success": true,
  "plan_id": "<uuid>",
  "plan_type": "generic",
  "is_new_plan": true,
  "reused_from_plan_id": null,
  "message": "Generic plan generated for Running",
  "sessions_created": 16,
  "total_weeks": 4
}
```

**Verify in DB**:
- `SELECT COUNT(*) FROM train.training_plan WHERE is_active = true` → 1 row
- `SELECT COUNT(*) FROM train.training_plan_phase WHERE plan_id = '<uuid>'` → equals `total_weeks`
- `SELECT COUNT(*) FROM train.training_plan_session WHERE plan_id = '<uuid>'` → equals `sessions_created`

---

## Scenario 2: Plan Reuse (Exact Match Clone)

**Validates**: FR-005, FR-006, SC-002, bug fix (sessions_created ≠ 0)

Create a second athlete with an identical profile to the first and generate a plan:

```bash
TOKEN2="<second_athlete_jwt>"
CONTEXT2="<second_athlete_x_user_context>"

curl -X POST http://localhost:8001/api/v1/plans/generate \
  -H "Authorization: Bearer $TOKEN2" \
  -H "X-User-Context: $CONTEXT2" \
  -H "Content-Type: application/json" \
  -d '{"sport_id": "Running", "plan_type": "generic", "force_regenerate": false}'
```

**Expected response** (HTTP 201):
```json
{
  "success": true,
  "plan_id": "<new_uuid>",
  "plan_type": "generic",
  "is_new_plan": false,
  "reused_from_plan_id": "<original_plan_uuid>",
  "message": "Plan reused from existing template. Exact profile match found",
  "sessions_created": 16,
  "total_weeks": 4
}
```

**Critical check**: `sessions_created` must be `> 0` (not hardcoded to 0). Verify:
- `SELECT COUNT(*) FROM train.training_plan_session WHERE plan_id = '<new_uuid>'` → 16

---

## Scenario 3: Adaptive Plan (Premium Feature)

**Validates**: FR-003, FR-008, FR-009 (fallback), SC-003

Requires JWT with `adaptive_training` feature in X-User-Context.

```bash
curl -X POST http://localhost:8001/api/v1/plans/generate \
  -H "Authorization: Bearer $TOKEN_PREMIUM" \
  -H "X-User-Context: $CONTEXT_PREMIUM" \
  -H "Content-Type: application/json" \
  -d '{"sport_id": "Running", "plan_type": "adaptive"}'
```

**Expected response** (HTTP 201):
```json
{
  "success": true,
  "plan_id": "<uuid>",
  "plan_type": "adaptive",
  "is_new_plan": true,
  "reused_from_plan_id": null,
  "message": "Adaptive plan structure created. First week generated.",
  "sessions_created": 4,
  "total_weeks": 8
}
```

**Verify in DB**:
- `SELECT COUNT(*) FROM train.training_plan_phase WHERE plan_id = '<uuid>'` → 1 (only week 1)
- `SELECT COUNT(*) FROM train.training_plan_session WHERE plan_id = '<uuid>'` → equals athlete's days_per_week

---

## Scenario 4: Incomplete Profile Short-Circuit

**Validates**: FR-004

Remove `level` from the athlete's sport profile, then call generate:

```bash
curl -X POST http://localhost:8001/api/v1/plans/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-User-Context: $CONTEXT" \
  -H "Content-Type: application/json" \
  -d '{"sport_id": "Running", "plan_type": "generic"}'
```

**Expected response** (HTTP 201, but `success=false`):
```json
{
  "success": false,
  "plan_id": null,
  "plan_type": "generic",
  "is_new_plan": false,
  "reused_from_plan_id": null,
  "message": "Profile incomplete. Please complete your profile before generating a plan.",
  "sessions_created": 0,
  "total_weeks": 0
}
```

**Verify in DB**: No new `training_plan` row was created.

---

## Scenario 5: Adaptive Plan — Feature Not Available

**Validates**: FR-003

Non-premium athlete requests adaptive plan:

```bash
curl -X POST http://localhost:8001/api/v1/plans/generate \
  -H "Authorization: Bearer $TOKEN_BASIC" \
  -H "X-User-Context: $CONTEXT_BASIC" \
  -H "Content-Type: application/json" \
  -d '{"sport_id": "Running", "plan_type": "adaptive"}'
```

**Expected**: HTTP 403 with `detail: "Adaptive training feature not available in your plan"`

---

## Scenario 6: Get Active Plan

**Validates**: FR-013, FR-014, FR-015, SC-001 (readability)

```bash
curl -X GET "http://localhost:8001/api/v1/plans/active?sport_id=Running" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-User-Context: $CONTEXT"
```

**Expected** (HTTP 200):
```json
{
  "has_active_plan": true,
  "plan": {
    "id": "<uuid>",
    "name": "Running Training Plan - 2026-06-17",
    "plan_type": "generic",
    "start_date": "2026-06-17",
    "end_date": "2026-07-15",
    "duration_weeks": 4,
    "total_sessions": 16,
    "source": "ai"
  }
}
```

---

## Scenario 7: Get Plan Schedule

**Validates**: FR-016, FR-017, FR-018

```bash
curl -X GET "http://localhost:8001/api/v1/plans/<plan_id>/schedule" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-User-Context: $CONTEXT"
```

**Expected** (HTTP 200): Response has `schedule` array with `total_weeks` entries, each entry has `sessions` array ordered by `day_number`.

**Verify ordering**:
- Phases must appear in ascending `week_number` order
- Sessions within each phase must appear in ascending `day_number` order

---

## Scenario 8: Soft-State Enforcement

**Validates**: FR-010, Principle III

Generate two plans for the same athlete+sport:

```bash
# First plan
curl -X POST http://localhost:8001/api/v1/plans/generate ... -d '{"sport_id": "Running", "plan_type": "generic", "force_regenerate": true}'
# Second plan (force new)
curl -X POST http://localhost:8001/api/v1/plans/generate ... -d '{"sport_id": "Running", "plan_type": "generic", "force_regenerate": true}'
```

**Verify in DB**:
```sql
SELECT is_active, COUNT(*)
FROM train.training_plan
WHERE profile_id = '<profile_id>' AND sport_id = 'Running'
GROUP BY is_active;
-- Expected: is_active=true → 1 row, is_active=false → 1 row
```

---

## Running the Test Suite

```bash
cd athletIQ/train-service
# Activate venv
..\venv\Scripts\Activate.ps1

# Run plan tests only
pytest tests/test_plans.py -v

# Run with log output
pytest tests/test_plans.py -v -s --log-cli-level=DEBUG
```

**Expected**: All tests pass. See `tests/test_plans.py` for test coverage scope.

---

## Reference

- API contracts: `docs/product/Contract/Train-Service/CU-TRAIN-04/`
- Data model: `specs/001-training-plan-generation/data-model.md`
- Research decisions: `specs/001-training-plan-generation/research.md`
