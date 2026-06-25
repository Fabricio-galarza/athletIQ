# Tasks: Training Plan Generation (Generic + Adaptive)

**Input**: Design documents from `specs/001-training-plan-generation/`

**Prerequisites**: plan.md ✅ | spec.md ✅ | research.md ✅ | data-model.md ✅ | contracts/ ✅ | quickstart.md ✅

**Tests**: REQUIRED — explicitly mandated by FR-022 through FR-025 in spec.md. All test tasks use the real Supabase PostgreSQL instance with per-test transaction rollback (no SQLite, no mocks, no testcontainers).

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to ([US1], [US2], [US3])
- Exact file paths included in every task description

---

## Phase 1: Foundational (Blocking Prerequisites)

**Purpose**: Infrastructure that MUST be complete before any user story can be implemented or tested. The Alembic migration creates the tables; `can_reuse_plan` and `clone_plan` are called by the already-wired router. The bug fix corrects the return-type mismatch that would crash the router on reuse.

**⚠️ CRITICAL**: No user story work — including tests — can begin until T001–T005 are complete.

- [x] T001 Create Alembic migration `XXXX_add_training_plan_tables.py` via `alembic revision --autogenerate -m "add_training_plan_tables"` in `train-service/`; verify it creates `train.training_plan`, `train.training_plan_phase`, `train.training_plan_session` tables in that dependency order with all columns, indexes, and FK constraints matching the models in `train-service/app/infra/db/models/plan.py`

- [x] T002 Apply migration with `alembic upgrade head` in `train-service/` and verify the three plan tables exist in the `train` schema on Supabase (run `SELECT table_name FROM information_schema.tables WHERE table_schema='train' AND table_name LIKE 'training_plan%'`)

- [x] T003 Implement `PlanMatcher.can_reuse_plan(self, profile_data: Dict[str, Any]) -> Tuple[bool, Optional[TrainingPlan], str]` in `train-service/app/services/plan_matcher.py`: generate hash → call `find_exact_match()` → on miss call `find_similar_plan(threshold=0.80)` → return `(True, plan, reason_str)` or `(False, None, "No reusable plan found")`; add English docstring and all type hints

- [x] T004 Implement `PlanMatcher.clone_plan(self, source_plan: TrainingPlan, profile_id: str) -> Tuple[TrainingPlan, int]` in `train-service/app/services/plan_matcher.py`: (1) deactivate existing active plan for `(profile_id, sport_id)` via `is_active=False`; (2) create new `TrainingPlan` with `original_plan_id=source_plan.id`, new profile_id, start/end dates anchored to today; (3) for each phase in source plan create new `TrainingPlanPhase` with date offset; (4) for each `TrainingPlanSession` in that phase fetch original `TrainingSession`, create new `TrainingSession` + `TrainingSessionBlock` records with `profile_id` of target athlete, create new `TrainingPlanSession`; (5) `db.commit()` once; (6) return `(new_plan, total_sessions_created)`; add English docstring and all type hints

- [x] T005 Fix `sessions_created` bug in `train-service/app/routers/plans.py` reuse-by-clone branch (~line 100): change `plan = plan_matcher.clone_plan(existing_plan, profile_id)` and hardcoded `sessions_created=0` to `plan, sessions_created = plan_matcher.clone_plan(existing_plan, profile_id)` and pass `sessions_created` to `PlanGenerationResponse`

**Checkpoint**: Migration applied ✅ | `can_reuse_plan` implemented ✅ | `clone_plan` returns tuple ✅ | bug fixed ✅ → user story work can begin

---

## Phase 2: User Story 1 — Generate Generic Training Plan (Priority: P1) 🎯 MVP

**Goal**: Athlete requests a generic plan and receives either a cloned existing plan (exact hash match or ≥80% similarity) or a freshly generated complete plan with all sessions upfront. Incomplete profiles are gracefully short-circuited. Clone deactivates any pre-existing active plan for the same sport. Self-reuse (athlete cloning their own prior plan) produces a fresh plan anchored to today.

**Independent Test**: `POST /api/v1/plans/generate` with `plan_type=generic` returns HTTP 201 with a valid `plan_id`, correct `sessions_created`, and the DB has the expected number of `training_plan_phase` and `training_plan_session` rows.

**Spec coverage**: US1 acceptance scenarios 1–5, edge case "clone deactivates existing active plan", edge case "self-reuse", FR-001–FR-012, FR-019, FR-021, SC-001–SC-002, SC-005

### Test Setup for All User Stories

- [x] T006 [US1] Create `train-service/tests/conftest.py` with: real Supabase DB engine from `get_settings()`; `db_session` fixture using outer transaction + `session.rollback()` after each test; `override_get_db` fixture that injects the test session into FastAPI; `test_client` fixture using `TestClient(app)` with dependency override; `athlete_profile_fixture` that inserts a minimal `AthleteProfile` row; `athlete_context_fixture` that returns a `UserContext` with `user_id`, `sports=["Running"]`, and no features; `premium_context_fixture` with `features=["adaptive_training"]`; `mock_auth_headers(context)` helper that produces a valid-format JWT header and Base64 X-User-Context header (JWT signature verification is currently disabled per known tech debt so any well-formed JWT passes)

### Tests for User Story 1

- [x] T007 [P] [US1] Write `test_generate_generic_plan_new` in `train-service/tests/test_plans.py`: seed athlete profile with complete sport values (`level=intermediate`, `primary_goal=improve_endurance`, `days_per_week=4`); POST /api/v1/plans/generate with `plan_type=generic`; assert HTTP 201, `success=true`, `is_new_plan=true`, `sessions_created==16` (4 weeks × 4 days), `total_weeks==4`; assert DB has 1 active `training_plan`, 4 `training_plan_phase` rows, 16 `training_plan_session` rows

- [x] T008 [P] [US1] Write `test_generate_generic_plan_exact_reuse` in `train-service/tests/test_plans.py`: seed a pre-existing `TrainingPlan` with matching `profile_hash` and a second athlete with the same profile; POST /api/v1/plans/generate for second athlete; assert `is_new_plan=false`, `reused_from_plan_id` equals source plan UUID, `sessions_created > 0` (not zero — validates the bug fix)

- [x] T009 [P] [US1] Write `test_generate_generic_plan_similarity_reuse` in `train-service/tests/test_plans.py`: seed a `TrainingPlan` with `level=intermediate`, `primary_goal=improve_endurance`, `days_per_week=4`; request with athlete having same level and goal but `days_per_week=5` (difference within 3 → similarity ≥80%); assert `is_new_plan=false`, `sessions_created > 0`

- [x] T010 [P] [US1] Write `test_generate_generic_plan_force_regenerate` in `train-service/tests/test_plans.py`: seed a reusable plan (exact hash match); POST with `force_regenerate=true`; assert `is_new_plan=true` (reuse skipped)

- [x] T011 [P] [US1] Write `test_generate_plan_incomplete_profile` in `train-service/tests/test_plans.py`: seed athlete with sport profile missing `level`; POST /api/v1/plans/generate; assert HTTP 201, `success=false`, `plan_id=null`, `sessions_created==0`; assert no `training_plan` row created for this athlete

- [x] T012 [P] [US1] Write `test_generate_plan_sport_not_configured` in `train-service/tests/test_plans.py`: POST with `sport_id="Football"` when context only has `sports=["Running"]`; assert HTTP 400

- [x] T013 [P] [US1] Write `test_generate_plan_no_auth` in `train-service/tests/test_plans.py`: POST without Authorization header; assert HTTP 401 or HTTP 403

- [x] T014 [P] [US1] Write `test_generate_plan_soft_state_enforcement` in `train-service/tests/test_plans.py`: generate two plans for the same athlete + sport (second with `force_regenerate=true`); assert DB has exactly 1 row with `is_active=true` and 1 row with `is_active=false` for that athlete + sport

- [x] T015 [P] [US1] Write `test_generate_plan_clone_deactivates_existing_active_plan` in `train-service/tests/test_plans.py`: seed athlete A who already has an active `TrainingPlan` for sport "Running" (set `is_active=True`); seed a second `TrainingPlan` template with a matching `profile_hash` owned by a different athlete; trigger `POST /api/v1/plans/generate` for athlete A (matching hash → clone path); assert HTTP 201, `is_new_plan=false`; assert DB for athlete A has exactly 1 row with `is_active=true` (the new clone) and exactly 1 row with `is_active=false` (the pre-existing plan that was deactivated) — covers FR-006/FR-024 "deactivate existing active plan on clone", which T014 does not cover (T014 only deactivates via fresh generation, not via clone)

- [x] T016 [P] [US1] Write `test_generate_plan_self_reuse` in `train-service/tests/test_plans.py`: seed a `TrainingPlan` belonging to athlete A with a `profile_hash` matching athlete A's current profile; POST /api/v1/plans/generate as athlete A (same hash as their own plan); assert the system proceeds through `can_reuse_plan`/`clone_plan` (returns `is_new_plan=false`, `reused_from_plan_id` set), and the resulting plan has a `start_date` equal to `date.today()` (not the original plan's start_date) — covers the spec edge case "self-reuse produces a fresh plan anchored to today, not a reference to the existing plan"

**Checkpoint**: `POST /plans/generate` (generic) fully covered — all acceptance scenarios 1–5 pass, reuse paths verified, bug fix confirmed, soft-state on clone validated, self-reuse edge case validated (10 test cases for US1)

---

## Phase 3: User Story 2 — Generate Adaptive Training Plan (Priority: P2)

**Goal**: Premium athlete gets an adaptive plan: only the first week's sessions are created immediately; the plan header exists with full `duration_weeks` set. Non-premium athletes receive HTTP 403. External AI failure falls back to rule-based generation transparently. Calling `generate_next_week` past the plan's `duration_weeks` cap raises a surfaced error.

**Independent Test**: `POST /api/v1/plans/generate` with `plan_type=adaptive` and `adaptive_training` feature returns HTTP 201 with `sessions_created == days_per_week` and exactly 1 `training_plan_phase` row in the DB. Works regardless of US1 test state.

**Spec coverage**: US2 acceptance scenarios 1–4, spec edge case "AI unavailable → rule-based fallback", spec edge case "all weeks generated → ValidationError", FR-003, FR-008, FR-009, SC-003

### Tests for User Story 2

- [x] T017 [P] [US2] Write `test_generate_adaptive_plan_premium` in `train-service/tests/test_plans.py`: use `premium_context_fixture` (`adaptive_training` feature); seed complete profile with `days_per_week=4`; POST with `plan_type=adaptive`; assert HTTP 201, `success=true`, `is_new_plan=true`, `sessions_created==4`; assert DB has 1 `training_plan` (adaptive), exactly 1 `training_plan_phase` (week 1 only), 4 `training_plan_session` rows

- [x] T018 [P] [US2] Write `test_generate_adaptive_plan_non_premium` in `train-service/tests/test_plans.py`: use `athlete_context_fixture` (no features); POST with `plan_type=adaptive`; assert HTTP 403 with message containing "Adaptive training feature not available"

- [x] T019 [P] [US2] Write `test_generate_next_week_default_intensity` in `train-service/tests/test_plans.py`: create an adaptive `TrainingPlan` + first phase directly in the DB; call `IAWorkoutGenerator.generate_next_week(plan_id, profile_data, previous_metrics=[])` directly; assert it returns sessions with default intensity (no error), creates week 2 phase, and returns `len(sessions) == days_per_week`

- [x] T020 [P] [US2] Write `test_generate_next_week_high_completion_increases_intensity` in `train-service/tests/test_plans.py`: call `generate_next_week` with `previous_metrics=[{"completion_percentage": 95, "difficulty": 3}]`; assert returned sessions have `planned_duration_minutes` greater than default (intensity multiplier > 1.0 applied)

- [x] T021 [P] [US2] Write `test_generate_next_week_ai_failure_falls_back_to_rules` in `train-service/tests/test_plans.py`: temporarily set `settings.ia_enabled=True` and `settings.ia_api_url="http://127.0.0.1:19999"` (unreachable port) via monkeypatch; create an adaptive plan with week 1 already generated; call `IAWorkoutGenerator.generate_next_week(plan_id, profile_data, previous_metrics=[])` for week 2; assert no exception is raised, the method returns a non-empty list of `TrainingSession` objects generated by rule-based logic, and a new `training_plan_phase` row with `week_number=2` exists in the DB — covers FR-009 and SC-003 ("AI unavailable → transparent fallback, no error surfaced")

- [x] T022 [P] [US2] Write `test_generate_next_week_exhausted_weeks_raises_validation_error` in `train-service/tests/test_plans.py`: create an adaptive `TrainingPlan` with `duration_weeks=2`; seed two `TrainingPlanPhase` rows each linked to at least one `TrainingPlanSession` (so both weeks are counted as generated); call `IAWorkoutGenerator.generate_next_week(plan_id, profile_data, previous_metrics=[])` for a third time; assert a `ValidationError` is raised with a message containing "all weeks" or "completed" — covers the spec edge case "generate_next_week past duration_weeks cap"; **Note**: HTTP-level coverage of this exhaustion guard will apply once a future "advance to next week" endpoint exists; `POST /plans/generate` cannot trigger this path because it only ever creates new plans and invokes `generate_next_week` exactly once for week 1, which is never already exhausted

**Checkpoint**: `POST /plans/generate` (adaptive) fully covered — premium gate, first-week-only structure, intensity adjustment, AI fallback, and exhaustion guard validated (6 test cases for US2)

---

## Phase 4: User Story 3 — Retrieve Active Plan and Schedule (Priority: P3)

**Goal**: Athlete can query their active plan summary and the full session schedule for any plan they own. Non-existent plans or wrong-owner plans return 404.

**Independent Test**: `GET /api/v1/plans/active?sport_id=Running` returns `has_active_plan=true` with a plan object; `GET /api/v1/plans/{plan_id}/schedule` returns a schedule with phases ordered by `week_number` and sessions ordered by `day_number`. Works with seeded data independent of generation flows.

**Spec coverage**: US3 acceptance scenarios 1–4, FR-013–FR-018, SC-001 (readability)

### Tests for User Story 3

- [x] T023 [P] [US3] Write `test_get_active_plan_exists` in `train-service/tests/test_plans.py`: seed a `TrainingPlan` with `is_active=true` and 3 linked `TrainingPlanSession` rows; GET /api/v1/plans/active?sport_id=Running; assert HTTP 200, `has_active_plan=true`, `plan.total_sessions==3`, `plan.plan_type`, `plan.duration_weeks`, `plan.source` all correct

- [x] T024 [P] [US3] Write `test_get_active_plan_none_exists` in `train-service/tests/test_plans.py`: no plan for the athlete; GET /api/v1/plans/active?sport_id=Running; assert HTTP 200, `has_active_plan=false`, `plan=null`

- [x] T025 [P] [US3] Write `test_get_plan_schedule_happy_path` in `train-service/tests/test_plans.py`: seed a `TrainingPlan` with 2 phases and 3 sessions each (week 2 before week 1 in insertion order); GET /api/v1/plans/{plan_id}/schedule; assert HTTP 200, `total_weeks==2`, `schedule[0].week_number==1` (ordered), `schedule[0].sessions` ordered by `day_number`

- [x] T026 [P] [US3] Write `test_get_plan_schedule_not_found` in `train-service/tests/test_plans.py`: GET /api/v1/plans/{random_uuid}/schedule; assert HTTP 404

- [x] T027 [P] [US3] Write `test_get_plan_schedule_wrong_owner` in `train-service/tests/test_plans.py`: seed a plan belonging to athlete A; authenticate as athlete B; GET /api/v1/plans/{plan_a_id}/schedule; assert HTTP 404 (ownership verified, not exposed as 403)

- [x] T028 [P] [US3] Write `test_get_active_plan_and_schedule_auth_errors` in `train-service/tests/test_plans.py`: call both GET /plans/active and GET /plans/{plan_id}/schedule without auth headers; assert HTTP 401 or 403 on each

**Checkpoint**: All three endpoints fully covered across all three user stories — 22 test cases total (T007–T028, excluding conftest T006)

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Full-suite validation, Constitution V compliance check, and documentation sync. Manual validations previously listed as T026/T027 have been promoted to automated tests T015 and T016 respectively.

- [x] T029 Run the full test suite (`pytest train-service/tests/test_plans.py -v`) and confirm 0 failures; fix any assertion mismatches or fixture isolation leaks discovered

- [x] T030 [P] Confirm `print()` statements are absent from `train-service/app/services/plan_generator.py` (known tech debt, Constitution V); replace any remaining `print()` with `logger.info/debug` calls if found

- [x] T031 Sync the spec contracts directory pointer: verify `specs/001-training-plan-generation/contracts/README.md` references match the three YAML files created under `docs/product/Contract/Train-Service/CU-TRAIN-04/`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 1)**: No dependencies — start immediately
- **US1 (Phase 2)**: Depends on T001–T005 complete
- **US2 (Phase 3)**: Depends on T001–T005 + T006 (conftest) complete
- **US3 (Phase 4)**: Depends on T001–T002 + T006 (conftest); does NOT depend on US1 or US2
- **Polish (Phase 5)**: Depends on all prior phases complete

### User Story Dependencies

- **US1 (P1)**: Requires migration + can_reuse_plan + clone_plan + bug fix (all Phase 1)
- **US2 (P2)**: Requires migration + generate_adaptive_plan_structure (already implemented); independent of US1 tests
- **US3 (P3)**: Requires only migration and conftest; can be developed in parallel with US1/US2

### Critical Path

```
T001 → T002 → T003 → T004 → T005 → T006 → T007..T016 (US1)
                                         ↘ T017..T022 (US2)
                                         ↘ T023..T028 (US3)
                                                         ↘ T029..T031 (Polish)
```

### Within Each Phase

- Tests that are `[P]` (T007–T028) can be written in any order within their phase
- T006 (conftest) must complete before any test task
- T003 and T004 can be written simultaneously (different methods in the same file)
- T005 is a 2-line change; can be done alongside T003/T004

---

## Parallel Opportunities

### Phase 1 Parallelism

```
# T003 and T004 are in the same file but different methods:
Task: "Implement can_reuse_plan() in plan_matcher.py"
Task: "Implement clone_plan() in plan_matcher.py"
# Write them together in one session — method order in file matters for readability only
```

### Phase 2 Parallelism (after T006)

```
# All US1 tests can be written simultaneously (different test functions):
Task: "test_generate_generic_plan_new"
Task: "test_generate_generic_plan_exact_reuse"
Task: "test_generate_generic_plan_similarity_reuse"
Task: "test_generate_generic_plan_force_regenerate"
Task: "test_generate_plan_incomplete_profile"
Task: "test_generate_plan_sport_not_configured"
Task: "test_generate_plan_no_auth"
Task: "test_generate_plan_soft_state_enforcement"
Task: "test_generate_plan_clone_deactivates_existing_active_plan"
Task: "test_generate_plan_self_reuse"
```

### Cross-Story Parallelism (after Phase 1 + T006)

```
# US2 and US3 tests can be written in parallel (independent logic):
Developer A: T017–T022 (adaptive plan tests)
Developer B: T023–T028 (active plan + schedule tests)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (T001–T005) — foundational, CRITICAL
2. Create conftest.py (T006)
3. Write US1 tests (T007–T016) and verify they fail without implementations
4. Confirm implementations in Phase 1 already make T007–T016 pass
5. **STOP and VALIDATE**: Run `pytest train-service/tests/test_plans.py -k "test_generate_generic or test_generate_plan"` — should all pass
6. CU-TRAIN-04 is functionally shippable at this point for generic plans

### Incremental Delivery

1. Foundation (T001–T005) + conftest (T006) → all infrastructure ready
2. US1 tests (T007–T016) → generic plan fully validated
3. US2 tests (T017–T022) → adaptive plan validated
4. US3 tests (T023–T028) → read endpoints validated
5. Polish (T029–T031) → full-suite run + cleanup → CU-TRAIN-04 complete

---

## Summary

| Phase | Tasks | Story | Description |
|---|---|---|---|
| Foundational | T001–T005 | — | Migration, can_reuse_plan, clone_plan, bug fix |
| US1 | T006–T016 | US1 | Conftest + 10 generic plan tests (incl. clone-deactivates and self-reuse) |
| US2 | T017–T022 | US2 | 6 adaptive plan tests (incl. AI fallback and exhaustion guard) |
| US3 | T023–T028 | US3 | Active plan + schedule retrieval tests |
| Polish | T029–T031 | — | Full-suite run, print() cleanup, contract sync |

**Total**: 31 tasks | **Test tasks**: 23 (T006–T028) | **Implementation tasks**: 5 (T001–T005) | **Polish tasks**: 3 (T029–T031)

---

## Notes

- `[P]` tasks = different functions/test cases; can be written simultaneously
- `[Story]` label maps each task to its user story for traceability
- All tests use the real Supabase PostgreSQL DB with transaction rollback (no mocks)
- JWT signature verification is currently disabled (`verify_signature=False`) — any well-formed JWT will authenticate in tests; this is a known pre-existing tech debt (Constitution Sec, partial violation)
- `IA_ENABLED=false` in `.env` by default during tests — T021 overrides this via monkeypatch for the AI fallback scenario only
- Commit after T002 (migration applied), after T005 (all implementations), and after each test phase checkpoint
- T015 and T016 replace the former manual Polish tasks T026/T027 — those edge cases are now enforced by the test suite rather than manual verification
