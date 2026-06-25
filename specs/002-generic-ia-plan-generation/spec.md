# Feature Specification: Generic Training Plan Generation with AI

**Feature Branch**: `CU-Train-04-generic-ia`

**Created**: 2026-06-24

**Status**: Draft

**Input**: Generic Training Plan Generation with AI (generic_ia feature gate)

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — AI-Powered Generic Plan Generation (Priority: P1)

An athlete whose commercial subscription includes the `generic_ia` feature requests a new generic training plan. No reusable plan exists for their profile. The system calls the AI service to generate the complete plan — every week, every session, and every workout block — upfront and ready to use in a single response. The athlete sees a full, personalized schedule from day one.

**Why this priority**: This is the core value of the feature. Without a complete AI-generated plan, the capability does not exist. It is the reason the feature flag exists and the primary differentiator over rule-based generation.

**Independent Test**: Can be tested end-to-end by calling `POST /plans/generate` with `plan_type=generic` using a JWT that includes the `generic_ia` feature, with no matching plan in the database. Verify the response contains a valid `plan_id`, `is_new_plan=true`, and `sessions_created` matching the expected total across all weeks. Verify `source="ai"` on the persisted plan record.

**Acceptance Scenarios**:

1. **Given** an athlete with a complete profile, the `generic_ia` feature in their context, and no existing reusable plan, **When** they call `POST /plans/generate` with `plan_type=generic`, **Then** the system returns HTTP 201 with `success=true`, `is_new_plan=true`, `sessions_created` equal to the total sessions generated across all weeks, and the persisted `training_plan` record has `source="ai"`.

2. **Given** the same athlete with a goal `target_date` 12 weeks away, **When** they generate a generic plan, **Then** the plan contains 12 weeks of phases and sessions, all created in the same request with no additional calls required.

3. **Given** an athlete with the `generic_ia` feature and a complete profile, and an existing active plan for the same sport, **When** they generate a new plan, **Then** the previous plan is deactivated (`is_active=False`) before the new AI-generated plan is activated.

4. **Given** an athlete with the `generic_ia` feature who generates a plan, **When** a second athlete with an identical profile later requests a generic plan, **Then** the second athlete receives a clone of the AI-generated plan (reuse path), not a new AI call.

---

### User Story 2 — Rule-Based Fallback When AI Is Unavailable (Priority: P2)

An athlete with the `generic_ia` feature requests a generic plan, but the AI service is unreachable, times out, or returns an error. The system automatically falls back to rule-based generation and delivers a complete plan to the athlete. The athlete sees no error; the plan is indistinguishable in structure from a normal successful response.

**Why this priority**: Resilience is essential. The AI service is an external dependency and will fail. Athletes must never receive an error because of a third-party outage.

**Independent Test**: Can be tested by configuring an invalid AI endpoint and calling `POST /plans/generate` with `generic_ia` feature. Verify HTTP 201 is returned, the plan exists in the database, and the application log contains a WARNING-level entry referencing the AI failure.

**Acceptance Scenarios**:

1. **Given** an athlete with the `generic_ia` feature and no reusable plan, and the AI service is unavailable (connection refused or timeout), **When** they generate a generic plan, **Then** the system returns HTTP 201 with a valid plan and `sessions_created > 0`, no error is surfaced to the client, and a WARNING log entry records the AI failure.

2. **Given** the AI service returns an unexpected response (malformed payload or empty workouts list), **When** the system processes the response, **Then** it falls back to rule-based generation and completes the plan successfully.

---

### User Story 3 — Unchanged Behavior for Athletes Without generic_ia (Priority: P3)

An athlete whose subscription does not include the `generic_ia` feature requests a generic plan. No reusable plan is found. The system generates the plan using rule-based logic, exactly as it did before this feature was introduced. Nothing changes for these athletes.

**Why this priority**: Backward compatibility must be preserved. The vast majority of athletes may not have this feature initially, and any regression in their experience would be a critical bug.

**Independent Test**: Can be tested by calling `POST /plans/generate` with `plan_type=generic` using a JWT that does NOT include `generic_ia`. Verify the response is identical in structure to the pre-feature behavior, `sessions_created > 0`, and `source="template"` on the persisted plan record.

**Acceptance Scenarios**:

1. **Given** an athlete without the `generic_ia` feature and no reusable plan, **When** they call `POST /plans/generate` with `plan_type=generic`, **Then** the system returns HTTP 201 with a valid plan, `sessions_created > 0`, and the persisted `training_plan` record has `source="template"`.

2. **Given** an athlete without the `generic_ia` feature, **When** a reusable plan is found (exact or similar profile hash), **Then** the plan is cloned and returned as `is_new_plan=false` — the reuse path is unaffected by the absence of the feature flag.

---

### Edge Cases

- What happens when the athlete has `generic_ia` but `force_regenerate=false` and a reusable plan exists? → The reuse/clone path takes precedence; the AI is never called. Feature flag only activates the AI path when no reuse is possible.
- What happens when the AI call succeeds but returns fewer weeks than the plan duration requires? → System treats this as a partial/invalid response and falls back to rule-based generation for the entire plan (no hybrid plan).
- What happens when the goal has no `target_date`? → Plan duration defaults to 4 weeks (existing `_calculate_plan_duration` behavior), regardless of whether AI or rule-based generation is used.
- What happens when a new plan is AI-generated and then cloned by a second athlete? → The clone carries `original_plan_id` referencing the AI-generated plan; `source` on the clone is `"template"` (it was derived, not independently generated by AI).
- What happens when `ia_enabled=False` in settings even though the athlete has `generic_ia`? → System falls back to rule-based generation. The feature flag enables the attempt; the settings gate determines whether the attempt is made.

---

## Requirements *(mandatory)*

### Functional Requirements

**Plan Generation Decision Tree**

- **FR-001**: The system MUST check for a reusable plan (exact profile-hash match or ≥ 80% similarity) as the first step in every generic plan generation request, regardless of whether the athlete has the `generic_ia` feature. This behavior is unchanged from CU-TRAIN-04.
- **FR-002**: If a reusable plan is found, the system MUST clone it and return `is_new_plan=false`. The `generic_ia` feature does not affect this path.
- **FR-003**: If no reusable plan is found AND the athlete has the `generic_ia` feature AND AI generation is active in the system configuration, the system MUST attempt to generate the complete plan using the external AI service.
- **FR-004**: If no reusable plan is found AND the athlete does NOT have the `generic_ia` feature, the system MUST generate the plan using the rule-based engine. This behavior is unchanged from CU-TRAIN-04.

**AI-Generated Plan Content**

- **FR-005**: The AI-generated plan MUST cover all weeks for the full goal duration (determined by the athlete's goal `target_date`, defaulting to 4 weeks if absent), with all sessions and workout blocks generated in a single request flow.
- **FR-006**: The AI-generated plan MUST be persisted to the database with the same record structure as a rule-based plan: one `training_plan`, one `training_plan_phase` per week, one `training_session` + `training_session_block` records + `training_plan_session` join record per session day.
- **FR-007**: AI-generated `training_plan` records MUST store `source="ai"`.
- **FR-008**: Rule-based `training_plan` records MUST store `source="template"`. (This corrects the existing assignment in the current implementation.)
- **FR-009**: AI-generated plans MUST store a `profile_hash` on the `training_plan` record, making them eligible for future cloning by athletes with matching profiles.
- **FR-010**: The soft-state rule MUST be enforced for AI-generated plans: any existing active plan for the same athlete and sport MUST be set to inactive before the new AI-generated plan is activated.

**AI Failure Handling**

- **FR-011**: If the AI service call fails for any reason (connection error, timeout, HTTP error, malformed response, or empty workouts list), the system MUST transparently fall back to rule-based plan generation.
- **FR-012**: AI failures MUST be logged at WARNING level with sufficient detail to diagnose the root cause (error type and message).
- **FR-013**: AI failures MUST NOT surface as errors to the client. The response MUST be HTTP 201 with a valid plan regardless of whether AI or rule-based generation was used.

**Scope Boundaries**

- **FR-014**: The adaptive plan flow (`plan_type=adaptive`, `adaptive_training` feature) MUST NOT be modified by this feature.
- **FR-015**: No new API endpoints, database tables, or response schemas are introduced by this feature.

### Key Entities

- **TrainingPlan** (extended): The `source` field gains clearer semantics — `"ai"` for AI-generated plans, `"template"` for rule-based plans, `"coach"` for manually created plans (unchanged). The `profile_hash` and `original_plan_id` fields are unchanged in structure.
- **generic_ia feature flag**: A commercial plan feature, defined in core-service admin and propagated via the athlete's context. Its presence determines whether the AI generation path is attempted when no reuse is possible.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Athletes with the `generic_ia` feature receive a complete AI-generated training plan — all weeks, sessions, and blocks — in a single plan generation request, with no additional interactions required.
- **SC-002**: When the AI service is unavailable, athletes with `generic_ia` receive a rule-based plan with a successful HTTP 201 response; zero AI-related errors are surfaced to clients across all failure scenarios.
- **SC-003**: Athletes without the `generic_ia` feature receive rule-based generic plans with identical behavior and response structure to the pre-feature baseline; zero regressions in this path.
- **SC-004**: AI-generated plans are cloneable by subsequent athletes with matching profiles, reducing redundant AI calls to zero for profiles that already have an AI-generated plan in the system.
- **SC-005**: The `source` field on `training_plan` records accurately reflects the generation method (`"ai"` or `"template"`) for 100% of generated plans after this feature is deployed.
- **SC-006**: All new and existing automated tests pass at 100% against the real database, covering the AI path, the fallback path, the rule-based path, and the reuse path.

---

## Assumptions

- The `generic_ia` feature flag has already been created in core-service admin and is already propagated via `X-User-Context` for the test user `dev@athleteiq.com`. End-to-end testing can proceed against that user without any prerequisite setup in core-service.
- The AI service used for generic plan generation is reachable via the same `ia_api_url` and `ia_api_key` settings already present in train-service configuration.
- The AI API endpoint for generic full-plan generation is distinct from the per-week adaptive endpoint. The exact payload contract will be defined during planning, not in this specification.
- An "active AI configuration" means both `ia_enabled=True` in settings and `ia_api_url` is non-empty. If either is absent, AI generation is skipped regardless of the athlete's feature flag.
- The reuse/cloning logic (`PlanMatcher`) is unaffected by this feature. Similarity thresholds, hash generation, and clone behavior carry forward from CU-TRAIN-04.
- A clone of an AI-generated plan stores `source="template"` (it was derived, not independently AI-generated) to distinguish it from the original.
- Plan duration (total weeks) is determined by `_calculate_plan_duration()` using the athlete's goal `target_date`, with a 4-week default and 52-week cap. This logic is unchanged.
- Tests will run against the same real Supabase PostgreSQL test schema used in CU-TRAIN-04. No new infrastructure is required.
- The adaptive plan flow is completely isolated from this change. No shared code paths between generic-IA generation and adaptive week-by-week generation will be modified.
