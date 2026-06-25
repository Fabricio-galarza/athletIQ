# Feature Specification: Training Plan Generation (Generic + Adaptive)

**Feature Branch**: `CU-Train-04`

**Created**: 2026-06-17

**Status**: Draft

**Input**: CU-TRAIN-04 — Generación de Plan de Entrenamiento (Genérico + Adaptativo)

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Generate a Generic Training Plan (Priority: P1)

An athlete with a complete profile requests a generic training plan for a sport. The system checks whether an identical or sufficiently similar plan already exists for another athlete; if so, it clones and assigns that plan instantly. Otherwise it generates a new complete plan with all sessions scheduled upfront. This is the core value delivery: the athlete immediately sees every session for the full plan duration.

**Why this priority**: This is the primary use case. Generic plans cover the majority of athletes and all sessions are generated upfront, making the plan immediately usable without further interaction.

**Independent Test**: Can be tested end-to-end by hitting `POST /plans/generate` with `plan_type=generic` and a complete athlete profile, then verifying a plan with phases and sessions exists in the database and that the response includes a valid `plan_id`, correct `sessions_created` count, and `total_weeks`.

**Acceptance Scenarios**:

1. **Given** an athlete with a complete profile (has `level`, `primary_goal`, `days_per_week`) and no prior plan for the requested sport, **When** they call `POST /plans/generate` with `plan_type=generic`, **Then** the system returns HTTP 201 with `success=true`, a valid `plan_id`, `is_new_plan=true`, `sessions_created > 0`, and the database contains a `training_plan`, `training_plan_phase`, and `training_plan_session` records all in the `train` schema.

2. **Given** an athlete with a complete profile and an existing generic plan with an identical profile hash already in the system, **When** they call `POST /plans/generate` with `plan_type=generic` and `force_regenerate=false`, **Then** the system returns HTTP 201 with `is_new_plan=false`, `reused_from_plan_id` set to the original plan's UUID, and `sessions_created` equal to the actual number of sessions cloned (not hardcoded to 0).

3. **Given** an athlete with a complete profile and an existing generic plan with ≥ 80% profile similarity (same level and primary_goal, close days_per_week), **When** they call `POST /plans/generate` with `plan_type=generic`, **Then** the system returns HTTP 201 with `is_new_plan=false` and `reused_from_plan_id` set to the similar plan's UUID.

4. **Given** an athlete with a complete profile and `force_regenerate=true`, **When** they call `POST /plans/generate`, **Then** the system bypasses the reuse check and always generates a fresh plan, returning `is_new_plan=true`.

5. **Given** an athlete with an incomplete profile (missing `level`, `primary_goal`, or `days_per_week`), **When** they call `POST /plans/generate`, **Then** the system returns HTTP 201 with `success=false` and a message describing the incomplete profile (no plan is created in the database).

---

### User Story 2 — Generate an Adaptive Training Plan (Priority: P2)

A premium athlete (with the `adaptive_training` feature) requests an adaptive plan. The system creates a plan header and generates only the first week's sessions using either an external AI service or rule-based fallback. Subsequent weeks are generated on demand as the athlete progresses.

**Why this priority**: Adaptive plans are the premium differentiator, but they depend on the generic plan infrastructure (P1) being correct first.

**Independent Test**: Can be tested by calling `POST /plans/generate` with `plan_type=adaptive` using a JWT with `adaptive_training` feature enabled. Verify response has `sessions_created` equal to the number of sessions in the first week (days_per_week value), the plan has exactly one phase, and no additional phases exist in the database.

**Acceptance Scenarios**:

1. **Given** a premium athlete (has `adaptive_training` feature), **When** they call `POST /plans/generate` with `plan_type=adaptive`, **Then** the system returns HTTP 201 with `success=true`, `is_new_plan=true`, `sessions_created` equal to the athlete's `days_per_week`, and the plan has exactly one phase (week 1) with the corresponding sessions.

2. **Given** a non-premium athlete (missing `adaptive_training` feature), **When** they call `POST /plans/generate` with `plan_type=adaptive`, **Then** the system returns HTTP 403 with a message indicating the feature is not available in their plan.

3. **Given** an adaptive plan exists for an athlete, **When** `generate_next_week` is called with empty `previous_metrics`, **Then** the system generates sessions using rule-based logic with default intensity (multiplier = 1.0) and creates a new phase record.

4. **Given** an adaptive plan and previous week metrics showing high completion (≥ 90%) and low difficulty (≤ 4), **When** `generate_next_week` is called, **Then** the generated sessions have increased intensity compared to the baseline.

---

### User Story 3 — Retrieve Active Plan and Schedule (Priority: P3)

An athlete retrieves their currently active plan for a sport, or the full schedule (phases and sessions) for a specific plan. These are read-only flows used by the frontend to display the training calendar.

**Why this priority**: Read operations depend on a plan having been generated (P1/P2) and are needed for the user to consume the plan, but can be independently tested with fixture data.

**Independent Test**: Can be tested by seeding a `training_plan` record, then calling `GET /plans/active?sport_id=X` and `GET /plans/{plan_id}/schedule` and verifying the response structure.

**Acceptance Scenarios**:

1. **Given** an athlete with an active plan for sport `Running`, **When** they call `GET /plans/active?sport_id=Running`, **Then** the system returns HTTP 200 with `has_active_plan=true` and a `plan` object containing `id`, `name`, `plan_type`, `start_date`, `end_date`, `duration_weeks`, `total_sessions`, and `source`.

2. **Given** an athlete with no active plan for sport `Running`, **When** they call `GET /plans/active?sport_id=Running`, **Then** the system returns HTTP 200 with `has_active_plan=false` and `plan=null`.

3. **Given** a valid `plan_id` belonging to the authenticated athlete, **When** they call `GET /plans/{plan_id}/schedule`, **Then** the system returns HTTP 200 with `plan_id`, `plan_name`, `plan_type`, `total_weeks`, and a `schedule` array where each entry contains `week_number`, `name`, `focus`, `start_date`, `end_date`, and a `sessions` array.

4. **Given** a `plan_id` that does not belong to the authenticated athlete (or does not exist), **When** they call `GET /plans/{plan_id}/schedule`, **Then** the system returns HTTP 404.

---

### Edge Cases

- What happens when a sport in the request is not in the athlete's configured sports? → HTTP 400 with a message identifying the sport.
- What happens when a non-athlete role (e.g., coach) calls the plan generation endpoint? → HTTP 403.
- What happens when a request arrives without a JWT? → HTTP 401.
- What happens when `generate_next_week` is called on a plan that already has all weeks generated? → `ValidationError` is raised (surfaced as HTTP 400).
- What happens when the external AI API is unavailable during adaptive plan generation? → Rule-based fallback is used transparently; no error is returned to the client.
- What happens when `clone_plan` is called for a sport where the athlete already has an active plan? → The existing active plan must be deactivated (soft state) before the clone is activated.
- What happens when the profile hash matches a plan belonging to the requesting athlete themselves? → The system should still reuse/clone it (creating a fresh assignment with today's start date).

---

## Requirements *(mandatory)*

### Functional Requirements

**Plan Generation (POST /plans/generate)**

- **FR-001**: The endpoint MUST require the `athlete` role; requests without a valid JWT return HTTP 401; requests with a non-athlete role return HTTP 403.
- **FR-002**: The system MUST validate that the requested `sport_id` is in the athlete's configured sports; invalid sport returns HTTP 400.
- **FR-003**: The `adaptive` plan type MUST require the `adaptive_training` feature in the athlete's context; absence returns HTTP 403.
- **FR-004**: Before generating, the system MUST check profile completeness using fields `level`, `primary_goal`, and `days_per_week`; if any are missing, return HTTP 201 with `success=false` and an explanatory message (no plan is persisted).
- **FR-005**: For `generic` plans with `force_regenerate=false`, the system MUST first attempt plan reuse via exact profile-hash match (`PlanMatcher.can_reuse_plan` → `find_exact_match`), then via weighted similarity scoring (`find_similar_plan`, threshold ≥ 0.80).
- **FR-006**: If a reusable plan is found, the system MUST clone it via `PlanMatcher.clone_plan`, deactivate any existing active plan for that sport (soft state: `is_active=False`), and return `is_new_plan=false` with `reused_from_plan_id` set and `sessions_created` equal to the **actual** session count created by clone (not hardcoded 0).
- **FR-007**: For generic plan generation (no reuse), the system MUST generate all sessions upfront for all weeks (duration determined by goal target date, default 4 weeks), each week as a `TrainingPlanPhase`, each session day as a `TrainingSession` + `TrainingSessionBlock` records + `TrainingPlanSession` join record.
- **FR-008**: For adaptive plan generation, the system MUST create only the `TrainingPlan` header (no phases), then immediately generate week 1's sessions via `IAWorkoutGenerator.generate_next_week`.
- **FR-009**: `IAWorkoutGenerator.generate_next_week` MUST attempt an external AI API call first (when `ia_enabled=True` and `ia_api_url` is set), with transparent rule-based fallback on any error or empty response.
- **FR-010**: Each new plan MUST enforce soft-state: any existing active plan for the same athlete + sport MUST be set `is_active=False` before the new plan is saved.
- **FR-011**: Generic plans MUST store a `profile_hash` (SHA-256 of sorted key profile attributes) on the `training_plan` record to enable future exact matching.
- **FR-012**: `PlanMatcher` MUST expose `can_reuse_plan(profile_data)` returning `(bool, Optional[TrainingPlan], reason_str)` and `clone_plan(source_plan, profile_id)` returning the cloned `TrainingPlan` with all phases and sessions duplicated.

**Active Plan (GET /plans/active)**

- **FR-013**: The endpoint MUST require the `athlete` role.
- **FR-014**: The system MUST return `has_active_plan=false` (no error) when no profile exists or no active plan exists for the requested sport.
- **FR-015**: The response MUST include `total_sessions` as the count of `training_plan_session` records linked to the plan.

**Plan Schedule (GET /plans/{plan_id}/schedule)**

- **FR-016**: The endpoint MUST require the `athlete` role.
- **FR-017**: The system MUST return HTTP 404 if the plan does not exist or does not belong to the authenticated athlete.
- **FR-018**: The response MUST include phases ordered by `week_number` and sessions within each phase ordered by `day_number`.

**Database / Migration**

- **FR-019**: An Alembic migration MUST create the `train.training_plan`, `train.training_plan_phase`, and `train.training_plan_session` tables with all columns, indexes, and FK constraints documented in the DB models.
- **FR-020**: All three tables MUST reside in the `train` schema; cross-schema FKs to `train.training_session` MUST use explicit schema-qualified names.

**API Contract**

- **FR-021**: OpenAPI contract YAML files for all three endpoints MUST be created under `docs/product/Contract/Train-Service/CU-TRAIN-04/` following the existing BearerAuth + UserContext security scheme convention and matching error shapes (400/401/403/404).

**Tests**

- **FR-022**: A pytest suite MUST cover the happy path, validation error, auth/role error, and at least one business-rule case for each of the three endpoints.
- **FR-023**: Tests MUST cover plan-reuse paths: exact-hash reuse (clone), similarity-based reuse (clone), no-reuse → generate new.
- **FR-024**: Tests MUST verify that generic plan generation creates all sessions upfront, adaptive plan creates only first-week sessions, and that one-active-plan-per-sport enforcement (deactivation) is applied on clone.
- **FR-025**: Tests MUST use the dedicated test schema in the same Supabase PostgreSQL instance (not SQLite, not mocks or testcontainers).

### Key Entities

- **TrainingPlan**: Root entity. One active plan per athlete+sport at a time. Carries `plan_type` (generic/adaptive), `source` (ai/template/coach), `profile_hash` (for exact reuse), `is_active` (soft state), `original_plan_id` (set when cloned), and duration metadata.
- **TrainingPlanPhase**: A mesocycle / week within a plan. Ordered by `week_number`. Has a `focus` (build/peak/taper). Generic plans pre-create all phases; adaptive plans create one phase per `generate_next_week` call.
- **TrainingPlanSession**: Join record linking a phase to a `TrainingSession` with positional data (`week_number`, `day_number`, `scheduled_date`).
- **TrainingSession** (existing): The actual workout record. Owns blocks (`TrainingSessionBlock`). Lives in the `train` schema; referenced via FK from `TrainingPlanSession`.
- **PlanMatcher**: Service class owning the reuse strategy — hash generation, exact match query, similarity scoring, and plan cloning.
- **PlanGenerator**: Service class owning plan creation — profile data retrieval, completeness check, generic full-generation, adaptive header creation.
- **IAWorkoutGenerator**: Service class owning week-by-week adaptive generation — AI API call with rule-based fallback, intensity adjustment from prior-week metrics.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Athletes can receive a ready-to-use generic training plan (with all sessions visible) within a single API call, with no additional requests required.
- **SC-002**: When an identical athlete profile already has a plan in the system, plan assignment completes via cloning without generating any new workout content, reducing generation time to under 500 ms.
- **SC-003**: Adaptive plan first-week sessions are available immediately after plan creation, using the rule-based fallback if the AI service is unavailable, with no error surfaced to the client.
- **SC-004**: All three endpoints are covered by automated tests that run against the real database (not mocks) and verify happy paths and at least one business-rule edge case each, with 100% passing rate before merge.
- **SC-005**: The `sessions_created` field in plan-reuse responses reflects the actual number of sessions in the cloned plan (no hardcoded zero).
- **SC-006**: A complete Alembic migration exists that can be applied to a fresh `train` schema and create all required tables without errors.
- **SC-007**: OpenAPI contract YAMLs for all three endpoints exist under the designated contract directory, with request/response examples and correct error shapes.

---

## Assumptions

- The athlete's `sport_id` is a plain string matching the sport name (e.g., `"Running"`), consistent with how it is stored and compared throughout the existing codebase.
- Profile completeness is determined solely by the presence of `level`, `primary_goal`, and `days_per_week`; other profile fields (health data, equipment) are optional for plan generation.
- The similarity threshold of 0.80 and the weight distribution (`level` 30%, `primary_goal` 30%, `days_per_week` 20%, `weekly_frequency` 20%) are the canonical values established in the existing `PlanMatcher` implementation and are not to be changed by this feature.
- The external AI API (configured via `ia_api_url` / `ia_api_key` settings) is optional; when not configured or unavailable, rule-based generation is the default and is always sufficient.
- Plan duration defaults to 4 weeks when no `goal_target_date` is present in the athlete's goal, with a maximum cap of 52 weeks.
- The test database is a dedicated schema within the same Supabase PostgreSQL instance already configured for development; no new infrastructure is required.
- `can_reuse_plan()` and `clone_plan()` are in scope for implementation as part of this feature (they are referenced by the router but not yet present in `plan_matcher.py`).
- The soft-state rule (deactivate existing active plan before creating/assigning new) is enforced inside `PlanGenerator` and `PlanMatcher.clone_plan`, not in the router.
- Only generic plans are eligible for reuse/cloning; adaptive plans are always generated fresh.
- The `TrainingPlanPhase` and `TrainingPlanSession` classes appear before `TrainingPlan` in `plan.py` due to SQLAlchemy relationship ordering; the Alembic migration must create tables in dependency order (`training_plan` → `training_plan_phase` → `training_plan_session`).
