# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

**AthletIQ** is a SaaS platform for personalized and adaptive athletic training. It collects athlete data (profile, health, training structure, goals), evaluates data sufficiency, and generates training plans (generic or AI-adaptive).

**Status**: Active development. `core-service` is mature. `train-service` has CU-Train-01 through CU-Train-04 implemented and fully tested; 002-generic-ia-plan-generation is implemented on branch `CU-Train-04-generic-ia` (27/27 tests passing as of 2026-06-25).

---

## Architecture

Two Python microservices sharing one PostgreSQL instance (Supabase) with separate schemas:

```
athletIQ/
├── core-service/   # Django 5.2 + DRF — Auth, Plans, Forms, Sports (schema: core)
├── train-service/  # FastAPI 0.136 — Athlete Profiles, Plan Generation (schema: train)
├── docs/           # Use cases, API contracts (YAML = source of truth), ERM, SRS
└── venv/           # Shared virtual environment
```

**Inter-service communication**: Core issues JWT tokens + `X-User-Context` header (Base64 JSON with roles, features, forms, sports). Train-service validates the JWT, caches the context in Redis (`user_context:{user_id}`, TTL 30 min), and extracts roles/forms from it.

**Cross-schema FKs** do not exist at the DB level — referential integrity is enforced at the application layer via UUIDs.

---

## Development Commands

### core-service (Django, port 8000)
```bash
cd athletIQ/core-service
python manage.py runserver
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser

# Tests
python manage.py test              # all tests
python manage.py test users.tests  # single app
```

### train-service (FastAPI, port 8001)
```bash
cd athletIQ/train-service
# Windows: ..\venv\Scripts\Activate.ps1  |  Linux/Mac: source ../venv/bin/activate

uvicorn app.main:app --reload --port 8001

# Alembic migrations
alembic revision --autogenerate -m "description"
alembic upgrade head
alembic downgrade -1

# Interactive API docs
# http://localhost:8001/docs   (Swagger)
# http://localhost:8001/redoc
# http://localhost:8001/health/ready
```

---

## Key Architectural Patterns

### Authentication flow (train-service)
`context.py::get_user_context()`:
1. Decode JWT → extract `user_id`
2. Check Redis cache; if hit, return cached `UserContext`
3. On miss: decode `X-User-Context` header, store in Redis (30 min TTL)

Role enforcement via FastAPI dependency aliases:
```python
RequireAthlete = require_role("athlete")   # use as Depends(RequireAthlete)
RequireCoach   = require_role("coach")
RequireAdmin   = require_role("admin")
```

### Service layer
All business logic lives in `app/services/`, never in routers. Routers instantiate services and delegate:
```python
service = AthleteService(db, context.user_id)
result = await service.create_sport_profile(...)
```

### Soft state (`is_active`)
Records are never deleted — the active one is deactivated and a new one created. Applies to `AthleteTrainingStructure`, `AthleteGoal`, and `TrainingPlan`.

### Dynamic forms
Forms are defined in core-service admin and arrive in `UserContext.forms`. Train-service validates submitted data against form schemas in memory (`Form.validate_data()`), then persists values in `*_value` tables as strings (`field_id` + `value`). Lists/dicts are `json.dumps`-serialized. Access via `context.get_form(form_code)`.

### Settings singleton (train-service)
```python
from app.core.config import get_settings
settings = get_settings()   # NOT the module directly
```

---

## Code Standards

**Naming**
- Files, functions, variables, DB tables, cache keys, endpoint paths: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Endpoints and router prefixes: `kebab-case`

**Private methods** in service classes are prefixed with `_`.

**Type hints** are mandatory on all service methods and router functions. Import from `typing`: `Dict, Any, Optional, List, Tuple`.

**Logging** — use `logging`, never `print()`:
```python
logger = logging.getLogger(__name__)
```
Known debt: `print()` with emojis exists in `plan_generator.py`, `auth.py`, `session.py` — replace with `logger` when touching those files.

**Error handling (train-service)** — raise from `app/core/exceptions.py`:
```python
raise NotFoundError("AthleteProfile", str(self.user_id))
raise ValidationError("Form validation failed", details=errors)
```
Routers catch these and convert to `HTTPException`.

**Docstrings** — required on all public classes and methods, written in English.

---

## Adding New Endpoints

### train-service
1. Router in `app/routers/` or `app/api/v1/`
2. Pydantic schema in `app/schemas/`
3. Logic in `app/services/`
4. New model: extend `BaseModel` from `app/infra/db/models/base_model.py`, always add `__table_args__ = {"schema": "train"}`; generate Alembic migration
5. Register router in `app/main.py`
6. **Check API contract in `docs/product/Contract/Train-Service/` before implementing**

### core-service
1. Serializer in `<app>/serializers/`
2. Logic in `<app>/services/`
3. View in `<app>/views/`
4. Register URL in `<app>/urls.py` and `core/urls.py`
5. Model changes: `makemigrations` + `migrate`

---

## DB Models (train schema)

| Table | Purpose |
|---|---|
| `athlete_profile` | One per user — main profile anchor |
| `athlete_profile_value` / `athlete_sport_profile_value` / `athlete_health_profile_value` | Dynamic form values (string) |
| `athlete_training_structure` + `_value` | Days/week, schedule, equipment (soft state) |
| `athlete_goal` + `_value` | Active goal per sport (soft state) |
| `training_plan` | Generated plan (`plan_type`: generic/adaptive, `source`: ai/template/coach) |
| `training_plan_phase` | Mesocycles (week ranges) |
| `training_plan_session` | Phase ↔ session ↔ calendar day |
| `training_session` + `_block` | Individual sessions with exercise blocks |
| `test_template` | Evaluation session fixtures for initial assessment |

---

## Known Technical Debt

| Issue | Location | Priority |
|---|---|---|
| `SECRET_KEY` hardcoded | `core-service/core/settings.py` | High — move to `.env` |
| JWT `verify_signature: False` | `train-service/app/core/context.py` line ~228 | High — enable in all envs |
| `print()` statements | `auth.py`, `session.py` | Medium | (`plan_generator.py` is clean — verified 2026-06-22) |
| Tests are empty stubs | All `tests.py` in core-service | High |
| Raw SQL mixed with ORM | `onboarding.py`, `training_structure.py` | Low |
| `venv/` committed to repo | `.gitignore` | Medium |
| `ia_enabled=False` in all environments — IA code complete, no live API yet | `train-service/.env` — set `ia_enabled=True`, `ia_api_url`, `ia_api_key` to activate | Medium — code requires no changes; only `.env` configuration needed when IA provider is available |

---

## Pending Next Iteration

These items are scoped but not yet implemented. They inform what comes after CU-TRAIN-04.

**Adaptive plan recalculation**
When an athlete reports a health event or an anomalous training metric, `IAWorkoutGenerator` should recalculate the plan from that week forward rather than continuing with the pre-generated schedule. Trigger: new endpoint or flag on the `generate_next_week` call. Requires IA API integration to be active.

**`verify_signature=False` in `context.py`**
Pre-existing security debt (see Known Technical Debt). JWT signature verification is disabled. Must be resolved before any production deployment regardless of feature scope.

---

## Documentation

All formal documentation is in `docs/`. The **API contracts in `docs/product/Contract/` (YAML files) are the source of truth** — consult them before implementing any new endpoint.

<!-- SPECKIT START -->
CU-TRAIN-04 is complete. All 31 tasks done; 22/22 tests pass against real Supabase PostgreSQL. PR open into `tests` branch.
002-generic-ia-plan-generation is complete on branch `CU-Train-04-generic-ia`. All 13 tasks done; 27/27 tests passing (2026-06-25). Implementation plan at `specs/002-generic-ia-plan-generation/plan.md`. Activate by setting `ia_enabled=True`, `ia_api_url`, and `ia_api_key` in `train-service/.env` — no code changes required.
<!-- SPECKIT END -->
