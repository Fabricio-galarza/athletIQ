# Implementation Plan: Generic Training Plan Generation with AI

**Branch**: `CU-Train-04-generic-ia` | **Date**: 2026-06-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-generic-ia-plan-generation/spec.md`

---

## Summary

When an athlete with the `generic_ia` commercial feature requests a generic plan and no reusable plan is found, train-service calls an external IA API to generate the complete plan — all weeks, sessions, and blocks — in a single synchronous HTTP request. If the IA API is unreachable, returns an incomplete payload, or fails for any reason, the system falls back to rule-based generation transparently (HTTP 201, no client error). Athletes without `generic_ia` continue to receive rule-based plans unchanged. A `source` bug is also corrected: rule-based plans currently write `source="ai"` — this is fixed to `source="template"`.

**Current environment note**: No real IA API is available yet. `ia_enabled=False` is set in `.env` for all environments (local, staging, production). `generate_full_plan_via_ia()` is implemented with the correct HTTP client structure and error handling, but the feature gate (`settings.ia_enabled`) always short-circuits to rule-based generation in the current environment. When a real IA API becomes available, only `.env` configuration changes are needed — no code changes.

---

## Technical Context

**Language/Version**: Python 3.14 (venv_314), FastAPI 0.136, SQLAlchemy 2.x (sync session)

**Primary Dependencies**: FastAPI, SQLAlchemy (sync ORM), httpx (sync `Client` for new IA call), pydantic-settings

**Storage**: PostgreSQL via Supabase (schema: `train`). No new tables or columns required.

**Testing**: pytest with real Supabase PostgreSQL, per-test transaction rollback (`join_transaction_mode="create_savepoint"`), monkeypatch for IA settings and method stubs

**Target Platform**: Linux server (Supabase-hosted)

**Performance Goals**: Generic plan generation must complete within 60 s (IA API timeout). Fallback to rule-based must complete within existing latency budget (~200 ms).

**Constraints**: No new endpoints, tables, or response schemas (FR-015). The `generate_generic_plan()` method remains synchronous — the new IA call uses `httpx.Client` (sync), not `AsyncClient`.

**Scale/Scope**: Single endpoint (`POST /plans/generate`), two modified services (`PlanGenerator`, `IAWorkoutGenerator`), one corrected service (`PlanMatcher.clone_plan`), one new test file (~5 tests).

---

## Constitution Check

| # | Principle | Gate Question | Status |
|---|---|---|---|
| I | API Contract First | Existing CU-TRAIN-04 Generate Plan YAML consulted. No new endpoint or response schema. New IA sub-contract created in `contracts/` as a reference for the external service. | ✅ |
| II | Service-Layer Architecture | Feature-gate logic in `PlanGenerator.generate_generic_plan()`. IA call in `IAWorkoutGenerator.generate_full_plan_via_ia()`. No domain logic added to `plans.py` router. | ✅ |
| III | Soft State — No Hard Deletes | Soft-state deactivation in `generate_generic_plan()` is unchanged. `clone_plan()` unchanged. | ✅ |
| IV | Type Safety & Code Standards | All new methods carry type hints and docstrings. Naming follows `snake_case` / `PascalCase` conventions. | ✅ |
| V | Observability & Error Handling | AI failure logged at `WARNING` with error detail. No `print()`. Exceptions from IA path caught and swallowed at service boundary, never surfaced to client. | ✅ |
| Sec | Security | JWT `verify_signature=False` is pre-existing debt (Constitution Sec partial, not introduced here). IA API key read from `settings.ia_api_key` env var — never hardcoded. | ⚠ (pre-existing) |

**Sec partial justification**: The `verify_signature=False` debt exists in `context.py` and is unrelated to this feature. It is tracked in Known Technical Debt and must be resolved before production deployment.

---

## Project Structure

### Documentation (this feature)

```text
specs/002-generic-ia-plan-generation/
├── plan.md              ← this file
├── research.md          ← Phase 0 findings
├── data-model.md        ← entity changes and source-field semantics
├── quickstart.md        ← manual validation scenarios
├── contracts/
│   └── ia-generate-plan.yaml   ← external IA API contract (full-plan endpoint)
└── tasks.md             ← Phase 2 output (/speckit-tasks command)
```

### Source Code (affected files only)

```text
train-service/
├── app/
│   └── services/
│       ├── ia_workout_generator.py   ← ADD generate_full_plan_via_ia() (sync httpx)
│       ├── plan_generator.py         ← MODIFY generate_generic_plan() — feature gate + IA + source fix
│       └── plan_matcher.py           ← MODIFY clone_plan() — fix clone source to "template"
└── tests/
    └── test_plans_generic_ia.py      ← NEW — 5 tests covering AI path, fallback, no-feature path
```

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| Sync httpx call inside a sync service method | `generate_generic_plan()` is sync (router does not await it). Using `asyncio.run()` inside a sync method called from an async FastAPI handler would cause a nested event-loop error. | Making `generate_generic_plan()` async would require updating the router, all callers, and test invocations — high blast radius for a change not scoped to this feature. |

---

## Implementation Design

### Decision 1 — Where the IA call lives

`IAWorkoutGenerator.generate_full_plan_via_ia()` (new sync method). Rationale: keeps all external IA HTTP logic in one class, consistent with `_call_ia_api()` for adaptive plans. `PlanGenerator` stays orchestration-only.

### Decision 2 — Sync vs async httpx

New method uses `httpx.Client` (sync) with a 60-second timeout. The existing `_call_ia_api()` remains `async` (called from async `generate_next_week()`). The two methods are independent.

### Decision 3 — Feature gate location

Gate is evaluated inside `PlanGenerator.generate_generic_plan()`, not in the router. Three conditions must ALL be true:
1. `self.context.has_feature("generic_ia")`
2. `settings.ia_enabled is True`
3. `settings.ia_api_url` is non-empty

If any is false → rule-based path, `source="template"`.

> **Current environment**: `ia_enabled=False` in `.env` for all environments. Condition 2 always fails, so rule-based generation is always used. The IA code path in `generate_full_plan_via_ia()` is implemented and tested via monkeypatch but never executed against a live API.

### Decision 4 — IA response validation

A valid full-plan IA response must:
- Contain a `"weeks"` list with exactly `duration_weeks` entries
- Each week entry must have a non-empty `"sessions"` list

Any deviation (empty list, wrong count, missing key, HTTP error, connection error, timeout) → WARNING log + fall back to rule-based. No hybrid plans — the full plan uses one source.

### Decision 5 — `source` field correction

Current bug: `generate_generic_plan()` always writes `source="ai"` even for rule-based plans.

Fix:
- `source = "ai"` when IA generation succeeds
- `source = "template"` in all other cases (rule-based fallback, no feature, AI disabled)

Applied to both `TrainingPlan` and `TrainingSession` records.

### Decision 6 — Clone source

`PlanMatcher.clone_plan()` currently copies `source_plan.source` onto the clone. Per spec assumption, a clone is derived — not independently AI-generated. Fix: hardcode `source="template"` on the cloned `TrainingPlan`. Session source on clones remains copied from session source (unchanged, as sessions are direct copies).

### IA API Endpoint

External service endpoint: `POST {ia_api_url}/generate-plan`

Request payload:
```json
{
  "profile": { "level": "intermediate", "primary_goal": "improve_endurance", ... },
  "duration_weeks": 12,
  "days_per_week": 4,
  "sport": "Running"
}
```

Response payload (see `contracts/ia-generate-plan.yaml` for full schema):
```json
{
  "weeks": [
    {
      "week_number": 1,
      "focus": "build",
      "sessions": [
        {
          "day": 1,
          "name": "Endurance Training",
          "duration_minutes": 45,
          "blocks": [
            { "block_type": "warmup", "duration_minutes": 10, "intensity": "easy", "instructions": "..." },
            { "block_type": "main", "duration_minutes": 30, "intensity": "moderate", "instructions": "..." },
            { "block_type": "cooldown", "duration_minutes": 5, "intensity": "easy", "instructions": "..." }
          ]
        }
      ]
    }
  ]
}
```

### Test Coverage Plan

Tests follow the same monkeypatch pattern as T021 in CU-TRAIN-04: `generate_full_plan_via_ia()` is never called against a live API. Each test either stubs the method to return a hardcoded JSON fixture (success path) or raises `httpx.ConnectError` (failure path). `ia_enabled` is also patched to `True` where needed so the feature gate is exercised, decoupled from the `.env` value.

| Test | Scenario | Monkeypatch / Setup | Key Assertions |
|------|----------|---------------------|----------------|
| `test_generic_ia_generates_ai_plan` | `generic_ia` feature + IA returns valid weeks | `monkeypatch` stubs `generate_full_plan_via_ia` to return a hardcoded JSON fixture with `duration_weeks` valid week entries; `ia_enabled=True` patched | HTTP 201, `source="ai"` on DB plan, `sessions_created == duration_weeks × days_per_week` |
| `test_generic_ia_fallback_connection_error` | `generic_ia` feature + IA unreachable | `monkeypatch` stubs `generate_full_plan_via_ia` to raise `httpx.ConnectError` (simulates connection refused); `ia_enabled=True` patched | HTTP 201, `source="template"` on DB plan, WARNING logged |
| `test_generic_ia_fallback_invalid_response` | `generic_ia` feature + IA returns malformed JSON | `monkeypatch` stubs `generate_full_plan_via_ia` to return a fixture missing the `weeks` key; `ia_enabled=True` patched | HTTP 201, `source="template"` on DB plan |
| `test_generic_plan_without_ia_feature` | No `generic_ia` in context | No IA stub needed — feature gate blocks before any IA call | HTTP 201, `source="template"` on DB plan — no IA call made |
| `test_generic_ia_reuse_takes_precedence` | `generic_ia` + reusable plan exists | No IA stub needed — clone path exits before feature gate | `is_new_plan=False` (clone path), IA not called |

> **Why monkeypatch instead of a real IA call**: `ia_enabled=False` in all current environments means the feature gate never reaches `generate_full_plan_via_ia()`. Monkeypatching the method directly (rather than the HTTP layer) lets tests verify the full orchestration path — feature gate, IA call, response validation, fallback — without requiring a live API or network access. When a real API is available, integration tests can be added alongside without changing existing tests.
