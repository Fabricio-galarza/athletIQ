<!--
SYNC IMPACT REPORT
==================
Version change: [template] → 1.0.0 (initial ratification — all placeholders filled)

Added principles:
  I.   API Contract First
  II.  Service-Layer Architecture
  III. Soft State — No Hard Deletes
  IV.  Type Safety & Code Standards
  V.   Observability & Error Handling

Added sections:
  - Technology Stack & Schema Boundaries
  - Security & Authentication Requirements

Templates status:
  ✅ .specify/templates/plan-template.md — Constitution Check gates updated
  ✅ .specify/templates/spec-template.md — no changes required (structure already aligned)
  ✅ .specify/templates/tasks-template.md — no structural changes required;
       task categories (migration, logging, exception handling) already present
  ✅ .specify/templates/constitution-template.md — source template, not modified

Deferred items:
  - RATIFICATION_DATE set to 2026-06-17 (first observed date; no prior record found)
-->

# AthletIQ Constitution

## Core Principles

### I. API Contract First

Before implementing any endpoint, the API contract YAML file in
`docs/product/Contract/` MUST be consulted and followed exactly.
Contracts are the source of truth for request/response schemas,
HTTP status codes, path formats, and error shapes. Any deviation
requires updating the contract first, before touching implementation.

**Rationale**: Prevents drift between documentation and code; enables
parallel frontend/backend work; ensures inter-service consistency across
core-service and train-service.

### II. Service-Layer Architecture

All business logic MUST reside in `app/services/` (train-service) or
`<app>/services/` (core-service). Routers and views MUST only instantiate
services, delegate to them, and return the result — no domain logic is
permitted inside HTTP handlers.

```python
# CORRECT
service = AthleteService(db, context.user_id)
result = await service.create_sport_profile(data)

# WRONG — logic in router
if data.sport_id not in allowed_sports:   # belongs in service
    raise HTTPException(...)
```

**Rationale**: Keeps the domain testable in isolation from HTTP concerns,
and makes the codebase navigable as feature count grows.

### III. Soft State — No Hard Deletes

Records flagged with `is_active` (currently `AthleteTrainingStructure`,
`AthleteGoal`, and `TrainingPlan`) MUST NOT be deleted. The active record
MUST be set to `is_active = False` and a new record created in its place.
Future temporal entities MUST follow the same pattern.

**Rationale**: Athletic training data is inherently temporal — historical
plans and goals are required for progression analysis and AI adaptation.
Hard deletes permanently destroy traceability.

### IV. Type Safety & Code Standards

Type hints are MANDATORY on all service method signatures and router function
parameters. Import from `typing`: `Dict, Any, Optional, List, Tuple`.

Naming conventions are ENFORCED across the entire codebase:

| Scope | Convention |
|---|---|
| Files, functions, variables, DB tables, cache keys | `snake_case` |
| Classes | `PascalCase` |
| Constants | `UPPER_SNAKE_CASE` |
| Endpoint paths and router prefixes | `kebab-case` |

Private service methods MUST be prefixed with `_`. Docstrings are REQUIRED
on all public classes and methods (English only).

**Rationale**: Consistent style reduces cognitive load and makes the codebase
predictable for every contributor and AI assistant working on it.

### V. Observability & Error Handling

The `logging` module MUST be used exclusively — `print()` is forbidden in
production code. Every module that emits log output MUST declare:

```python
logger = logging.getLogger(__name__)
```

Domain errors in train-service MUST be raised as typed exceptions from
`app/core/exceptions.py` (`NotFoundError`, `ValidationError`, etc.).
Routers catch these and convert them to `HTTPException`. Log at service
boundaries, not inside every internal helper.

**Known debt** (`print()` still present): `plan_generator.py`, `auth.py`,
`session.py` — MUST be replaced with `logger` when those files are next
modified.

**Rationale**: `print()` is not captured by production log aggregators.
Centralized exception types ensure HTTP error responses match API contracts.

## Technology Stack & Schema Boundaries

The platform consists of two Python microservices sharing one PostgreSQL
instance (Supabase) with isolated schemas:

- **core-service** — Django 5.2 + DRF; schema `core`; owns Auth, Plans,
  Forms, Sports (port 8000)
- **train-service** — FastAPI 0.136; schema `train`; owns Athlete Profiles,
  Plan Generation (port 8001)

Cross-schema foreign keys MUST NOT exist at the database level. Referential
integrity between `core` and `train` schemas is enforced at the application
layer via UUIDs only.

Redis is used exclusively for `UserContext` caching with key pattern
`user_context:{user_id}` and a 30-minute TTL.

Settings in train-service MUST be accessed via `get_settings()` — never by
importing the config module directly:

```python
from app.core.config import get_settings
settings = get_settings()   # correct
```

Inter-service communication MUST use JWT tokens issued by core-service,
accompanied by the `X-User-Context` header (Base64-encoded JSON containing
roles, features, forms, sports). Train-service validates the JWT and caches
the context; it MUST NOT call core-service APIs directly during request
handling.

All new train-service DB models MUST extend `BaseModel` from
`app/infra/db/models/base_model.py` and MUST declare:

```python
__table_args__ = {"schema": "train"}
```

Every schema change MUST be accompanied by an Alembic migration generated
via `alembic revision --autogenerate`.

## Security & Authentication Requirements

JWT signature verification MUST be enabled in all environments. The current
`verify_signature: False` in `train-service/app/core/context.py` (~line 228)
is a **critical known debt** and MUST be resolved before any production
deployment.

Role enforcement in train-service MUST use the typed FastAPI dependency
aliases — raw string checks inside route handlers are prohibited:

```python
RequireAthlete = require_role("athlete")
RequireCoach   = require_role("coach")
RequireAdmin   = require_role("admin")
```

Secrets (Django `SECRET_KEY`, database credentials, JWT signing keys) MUST
be loaded from environment variables — hardcoded values are prohibited. The
hardcoded `SECRET_KEY` in `core-service/core/settings.py` is a **critical
known debt** and MUST be remediated before production deployment.

## Governance

This constitution supersedes all other local practices. Anything not covered
here defaults to the guidance in `CLAUDE.md`.

**Amendment procedure**: Amendments MUST increment the version number per
semantic versioning:
- **MAJOR** — principle removal or incompatible redefinition
- **MINOR** — new principle or section added
- **PATCH** — wording clarification, typo fix, non-semantic refinement

Updated constitutions MUST be propagated to `.specify/templates/` (plan,
spec, tasks) so that Constitution Check gates remain accurate.

**Compliance review**: All PRs touching `app/services/`, routers, or DB
models MUST verify compliance with Principles I–V before merge. Any
deviation from Principle II (service-layer) or III (soft state) MUST be
explicitly justified in the PR description with a complexity entry in the
plan's Complexity Tracking table.

**Guidance file**: `CLAUDE.md` is the authoritative runtime development guide
for day-to-day development commands, patterns, and onboarding.

**Version**: 1.0.0 | **Ratified**: 2026-06-17 | **Last Amended**: 2026-06-17
