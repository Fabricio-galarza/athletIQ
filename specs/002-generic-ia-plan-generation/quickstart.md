# Quickstart: Generic IA Plan Generation — Validation Guide

**Feature**: 002-generic-ia-plan-generation  
**Date**: 2026-06-24

This guide covers how to validate the feature end-to-end once implementation is complete. It is a run-and-observe guide, not implementation instructions.

---

## Prerequisites

- train-service running on port 8001 (`uvicorn app.main:app --reload --port 8001`)
- core-service running on port 8000 (for JWT issuance)
- Test user `dev@athleteiq.com` exists in core-service with:
  - Role: `athlete`
  - Feature: `generic_ia` (already created and propagated)
  - Sport: `Running` configured
  - Complete athlete profile (level, primary_goal, days_per_week, goal with target_date)
- A second test user `dev-norole@athleteiq.com` or any user WITHOUT `generic_ia`

---

## Scenario 1 — AI path (golden path)

**What it validates**: User Story 1 — complete AI-generated plan in a single request.

**Setup**: In `.env` for train-service, set:
```
IA_ENABLED=true
IA_API_URL=<real or mock IA endpoint that returns a valid weeks response>
IA_API_KEY=<key>
```

**Request**:
```bash
curl -X POST http://localhost:8001/api/v1/plans/generate \
  -H "Authorization: Bearer <jwt for dev@athleteiq.com>" \
  -H "X-User-Context: <base64 context with generic_ia feature>" \
  -H "Content-Type: application/json" \
  -d '{"sport_id": "Running", "plan_type": "generic", "force_regenerate": true}'
```

**Expected response (HTTP 201)**:
```json
{
  "success": true,
  "is_new_plan": true,
  "sessions_created": <duration_weeks × days_per_week>,
  "total_weeks": <duration_weeks>
}
```

**Verify in DB**:
```sql
SELECT id, source, profile_hash, duration_weeks, is_active
FROM train.training_plan
WHERE is_active = true
ORDER BY created_at DESC
LIMIT 1;
-- Expect: source = 'ai'
```

---

## Scenario 2 — AI fallback (IA unavailable)

**What it validates**: User Story 2 — transparent fallback when IA is down.

**Setup**: In `.env`, set:
```
IA_ENABLED=true
IA_API_URL=http://127.0.0.1:19999  # nothing listening here
```

**Request**: Same as Scenario 1 with `force_regenerate: true`.

**Expected response (HTTP 201)**: Response is structurally identical to Scenario 1 — `success=true`, `sessions_created > 0`.

**Verify in DB**:
```sql
SELECT source FROM train.training_plan WHERE is_active = true ORDER BY created_at DESC LIMIT 1;
-- Expect: source = 'template'  (fallback was used)
```

**Verify in logs**:
```
WARNING  app.services.ia_workout_generator: IA API error for generic plan generation: ...
```
No error should appear in the HTTP response.

---

## Scenario 3 — No `generic_ia` feature (backward compatibility)

**What it validates**: User Story 3 — rule-based plan unchanged for users without the feature.

**Setup**: Use any JWT for a user WITHOUT `generic_ia` in their context. Ensure `IA_ENABLED=true` (to confirm the flag alone does not enable AI).

**Request**: Same endpoint, same body, different JWT.

**Expected response (HTTP 201)**:
- `success=true`, `sessions_created > 0`
- In DB: `source = 'template'`
- No IA API call is made (no network traffic to `ia_api_url` for this request)

---

## Scenario 4 — Reuse takes precedence over IA

**What it validates**: Edge case — when a reusable plan exists, IA is never called.

**Setup**:
- A plan with matching `profile_hash` must exist in the DB (from a previous Scenario 1 run)
- `IA_ENABLED=true`, `IA_API_URL=<valid>`
- Use `force_regenerate: false` (default)

**Request**: Same as Scenario 1 but with `force_regenerate: false`.

**Expected response (HTTP 201)**:
- `is_new_plan: false`
- `reused_from_plan_id` is not null
- No IA API call (check logs — no WARNING or IA-related log lines)

**Verify in DB**:
```sql
SELECT source, original_plan_id FROM train.training_plan WHERE is_active = true ORDER BY created_at DESC LIMIT 1;
-- Expect: source = 'template'  (clone is derived, not independently AI-generated)
-- Expect: original_plan_id is not null
```

---

## Automated Test Run

All scenarios above are covered by the automated test suite. Run:

```bash
cd athletIQ/train-service
..\venv_314\Scripts\Activate.ps1   # or source ../venv_314/bin/activate

# Full suite (must stay at 22/22 + new tests passing)
python -m pytest tests/ -v

# New tests only
python -m pytest tests/test_plans_generic_ia.py -v
```

See [data-model.md](data-model.md) for field semantics and [contracts/ia-generate-plan.yaml](contracts/ia-generate-plan.yaml) for the IA API payload contract.
