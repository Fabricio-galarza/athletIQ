# Implementation Plan: Training Plan Generation (Generic + Adaptive)

**Branch**: `CU-Train-04` | **Date**: 2026-06-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-training-plan-generation/spec.md`

---

## Summary

CU-TRAIN-04 completes the training plan generation feature for `train-service`. The core business flow is already implemented (PlanGenerator, IAWorkoutGenerator, models, router, schemas). Four pieces remain:

1. **Alembic migration** creating `train.training_plan`, `train.training_plan_phase`, and `train.training_plan_session` tables — confirmed absent from both existing migrations.
2. **`can_reuse_plan()` and `clone_plan()` methods** on `PlanMatcher` — referenced by the router but not yet present in `plan_matcher.py`.
3. **OpenAPI contract YAMLs** for all three endpoints under `docs/product/Contract/Train-Service/CU-TRAIN-04/` — created as Phase 1 output.
4. **Pytest test suite** covering all three endpoints and key service logic, using the real Supabase PostgreSQL instance with transaction rollback isolation.

One existing bug: `sessions_created` is hardcoded to `0` in the reuse-by-clone router branch; fixed by changing `clone_plan` return type to `Tuple[TrainingPlan, int]` and unpacking it in the router.

---

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: FastAPI 0.136, SQLAlchemy (ORM + raw SQL via `text()`), Alembic, Pydantic v2, pytest, httpx (async IA API calls), pydantic-settings

**Storage**: PostgreSQL (Supabase), schema `train`. Redis for `UserContext` caching (TTL 30 min) — not directly used by plan generation but governs auth flow.

**Testing**: pytest with `TestClient` (FastAPI) against the real Supabase PostgreSQL instance. Per-test transaction rollback via `db.begin_nested()` / `db.rollback()`. No mocks, no SQLite, no testcontainers.

**Target Platform**: Linux server (Supabase-hosted PostgreSQL + FastAPI process)

**Performance Goals**: Plan reuse via clone must complete in ≤ 500 ms. Generic plan generation (4 weeks × 4 sessions = 16 sessions) must complete in ≤ 2 s.

**Constraints**:
- No cross-schema FK at DB level — `core` schema references enforced at app layer via UUIDs only.
- `verify_signature=False` is a known tech debt in `context.py` — out of scope for this CU.
- `IA_ENABLED` defaults to `False`; the external AI API is optional and rule-based fallback must always be sufficient.

**Scale/Scope**: Single train-service instance. 4 new items (2 methods + 1 migration + test file) plus 3 YAML contracts. No new DB models, no new routers, no new schemas.

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Gate Question | Status |
|---|---|---|---|
| I | API Contract First | Is the YAML contract in `docs/product/Contract/` consulted and does this plan match it? | ⚠ |
| II | Service-Layer Architecture | Is all business logic placed in `app/services/` (or `<app>/services/`)? No domain logic in routers/views? | ✅ |
| III | Soft State — No Hard Deletes | Do temporal entities use `is_active` deactivation instead of DELETE? | ✅ |
| IV | Type Safety & Code Standards | Are type hints, naming conventions, and docstrings applied to all new public APIs? | ✅ |
| V | Observability & Error Handling | Is `logging` used (no `print()`)? Are domain errors raised from `app/core/exceptions.py`? | ✅ |
| Sec | Security | Is JWT `verify_signature` enabled? Are secrets loaded from env vars? | ⚠ |

**I — Partial**: CU-TRAIN-04 contracts do not exist prior to this feature; they are created as Phase 1 output. The plan is shaped by existing router behavior which is the ground truth. All future endpoint changes must consult these newly created YAMLs first.

**Sec — Partial**: `verify_signature=False` in `train-service/app/core/context.py` (~line 228) is pre-existing critical tech debt. It is NOT addressed in this CU — out of scope. JWT secrets are loaded from env vars (`jwt_secret_key` in Settings). No new hardcoded secrets introduced.

---

## Project Structure

### Documentation (this feature)

```text
specs/001-training-plan-generation/
├── plan.md          ← this file
├── spec.md          ← feature specification
├── research.md      ← Phase 0 decisions (audit + method designs)
├── data-model.md    ← Phase 1 entity model
├── quickstart.md    ← Phase 1 validation guide
├── contracts/       ← Phase 1 planning reference (mirrors docs/product/Contract/)
└── checklists/
    └── requirements.md
```

### Source Code (repository root)

```text
train-service/
├── app/
│   ├── routers/
│   │   └── plans.py                        # EXISTS — minor bug fix (sessions_created)
│   ├── schemas/
│   │   └── plan.py                         # EXISTS — no changes needed
│   ├── services/
│   │   ├── plan_generator.py               # EXISTS — no changes needed
│   │   ├── plan_matcher.py                 # EXISTS — ADD can_reuse_plan() + clone_plan()
│   │   └── ia_workout_generator.py         # EXISTS — no changes needed
│   └── infra/
│       └── db/
│           └── models/
│               └── plan.py                 # EXISTS — no changes needed
├── migrations/
│   └── versions/
│       └── XXXX_add_training_plan_tables.py   # MISSING — create this
└── tests/
    └── test_plans.py                          # MISSING — create this

docs/
└── product/
    └── Contract/
        └── Train-Service/
            └── CU-TRAIN-04/                   # MISSING dir — created in Phase 1
                ├── API CONTRACT – CU-TRAIN-04 – Generate Plan.yaml     # CREATED
                ├── API CONTRACT – CU-TRAIN-04 – Get Active Plan.yaml   # CREATED
                └── API CONTRACT – CU-TRAIN-04 – Get Plan Schedule.yaml # CREATED
```

**Structure Decision**: Single-service backend modification. No new files except the migration, the test module, and the method additions to `plan_matcher.py`. No frontend, no mobile, no new packages.

---

## Implementation Order

Work must be done in this dependency order to avoid broken imports or missing tables:

1. **Migration** — tables must exist for any DB-touching code to work
2. **`can_reuse_plan` + `clone_plan` on PlanMatcher** — router calls these
3. **Router bug fix** — unpack `(plan, sessions_created)` from clone_plan
4. **Tests** — written against the now-complete implementation

---

## Complexity Tracking

> Constitution I (partial): CU-TRAIN-04 contracts are authored here rather than consumed from a pre-existing document. This is acceptable because this is the feature that introduces these endpoints — the contract cannot pre-date its own implementation. All future changes to these endpoints must update the contracts first (Principle I applies from this point forward).

> Constitution Sec (partial): `verify_signature=False` is pre-existing critical debt recorded in CLAUDE.md. Fixing it is a security hardening task separate from this functional CU. The implementation here does not worsen the existing security posture.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| Principle I partial (contracts written here, not consulted) | This CU introduces the endpoints; no prior contract exists to consult | Cannot consult a document that does not yet exist; contract creation is part of this CU's scope |
| Principle Sec partial (verify_signature=False remains) | Out of scope for this CU; dedicated security hardening task needed | Enabling signature verification requires env-var changes across all environments; must be coordinated separately |
