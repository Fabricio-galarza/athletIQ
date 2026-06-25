---
description: "Task list for 002-generic-ia-plan-generation"
---

# Tasks: Generic Training Plan Generation with AI

**Input**: Design documents from `specs/002-generic-ia-plan-generation/`

**Prerequisites**: plan.md ✅ spec.md ✅ research.md ✅ data-model.md ✅ contracts/ ✅ quickstart.md ✅

**Tests**: Included — 5 tests explicitly defined in plan.md Test Coverage Plan, required by SC-006. All use monkeypatch (no live IA API required).

**Organization**: Tasks grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on in-progress tasks)
- **[Story]**: User story this task belongs to (US1, US2, US3)
- Exact file paths included in every task

---

## Phase 1: Setup

**Purpose**: Add the one new pytest fixture that all IA tests depend on.

- [ ] T001 Add `generic_ia_context` pytest fixture to `train-service/tests/conftest.py` — build a `UserContext` with `features=["generic_ia"]` using the existing `_build_context()` helper; name it `generic_ia_context` and scope it to `function`

**Checkpoint**: Fixture available — Phase 3 test tasks can begin.

---

## Phase 2: Foundational (Blocking Prerequisite)

**Purpose**: Correctness fix that all three user stories depend on — a clone must never carry `source="ai"` from its parent.

**⚠️ CRITICAL**: Must complete before any user story work begins.

- [ ] T002 Fix `PlanMatcher.clone_plan()` to hardcode `source="template"` on the cloned `TrainingPlan` record in `train-service/app/services/plan_matcher.py` — replace the current `source=source_plan.source` assignment with `source="template"`; update the method docstring to document this invariant

**Checkpoint**: Foundation ready — all user story phases can now begin.

---

## Phase 3: User Story 1 — AI-Powered Generic Plan Generation (Priority: P1) 🎯 MVP

**Goal**: When an athlete with `generic_ia` has no reusable plan, the system calls the external IA API and persists a complete plan with `source="ai"`.

**Independent Test**: Call `POST /api/v1/plans/generate` with `plan_type=generic` using `generic_ia_context` and no pre-existing plan in DB; assert HTTP 201, `is_new_plan=True`, `source="ai"` on the persisted `training_plan` record, and `sessions_created == duration_weeks × days_per_week`.

### Tests for User Story 1 ⚠️ Write first — confirm they FAIL before T005/T006

- [ ] T003 [US1] Write `test_generic_ia_generates_ai_plan` in `train-service/tests/test_plans_generic_ia.py` — use `generic_ia_context` fixture; monkeypatch `IAWorkoutGenerator.generate_full_plan_via_ia` to return a hardcoded fixture dict with `duration_weeks` valid week entries (each with non-empty `sessions`); monkeypatch `settings.ia_enabled=True` and `settings.ia_api_url="http://mock"`; assert HTTP 201, `is_new_plan=True`, `source="ai"` from DB, `sessions_created == duration_weeks × days_per_week`

  **Fixture format** (this is the exact dict shape `generate_full_plan_via_ia()` must return and that T005 must parse — both tasks share this contract):
  ```python
  {
      "weeks": [
          {
              "week_number": 1,          # int, 1-based
              "focus": "build",          # str, optional — T006 defaults to "build" if absent
              "sessions": [
                  {
                      "day": 1,                      # int, 1-based day-of-week
                      "name": "Endurance Run",       # str, optional
                      "duration_minutes": 45,        # int
                      "blocks": [
                          {
                              "block_type": "warmup",     # str: warmup|main|cooldown|interval|strength|recovery
                              "duration_minutes": 10,     # int
                              "intensity": "easy",        # str: easy|moderate|hard|max
                              "instructions": "..."       # str, optional
                          },
                          # ... additional blocks
                      ]
                  },
                  # ... additional sessions (one per days_per_week)
              ]
          },
          # ... one entry per duration_weeks
      ]
  }
  ```
  The fixture used in T003 must have exactly `duration_weeks` week entries and exactly `days_per_week` sessions per week so that `sessions_created == duration_weeks × days_per_week` holds. T008 uses a fixture that omits the `weeks` key entirely to trigger the invalid-response fallback.

- [ ] T004 [US1] Write `test_generic_ia_reuse_takes_precedence` in `train-service/tests/test_plans_generic_ia.py` — seed a `training_plan` with a matching `profile_hash` for the `generic_ia_context` user; call `POST /plans/generate` with `force_regenerate=false`; assert HTTP 201, `is_new_plan=False`, `reused_from_plan_id` is not null; confirm no IA call was made (monkeypatch not set up — any real IA call would raise)

### Implementation for User Story 1

- [ ] T005 [P] [US1] Implement `IAWorkoutGenerator.generate_full_plan_via_ia(self, profile: Dict[str, Any], duration_weeks: int, days_per_week: int, sport: str) -> Optional[Dict[str, Any]]` in `train-service/app/services/ia_workout_generator.py` — use `httpx.Client(timeout=60.0)` (sync); POST to `{settings.ia_api_url}/generate-plan` with `Authorization: Bearer {settings.ia_api_key}` header; return parsed JSON dict on HTTP 200; catch `httpx.ConnectError`, `httpx.TimeoutException`, `httpx.HTTPStatusError`, `ValueError`, `KeyError`, and any JSON parse error — log each at WARNING with `logger.warning("IA API error for generic plan generation: %s", e)` and return `None`; add full type hints and docstring

- [ ] T006 [US1] Modify `PlanGenerator.generate_generic_plan()` in `train-service/app/services/plan_generator.py` to add the feature gate, IA call, response validation, and dynamic `source` assignment:
  1. Resolve `settings = get_settings()` at the top of the method
  2. Evaluate gate: `ia_ok = context.has_feature("generic_ia") and settings.ia_enabled and bool(settings.ia_api_url)`
  3. When `ia_ok`: call `ia_gen.generate_full_plan_via_ia(profile, duration_weeks, days_per_week, sport)`; validate that `result` is not `None`, `len(result["weeks"]) == duration_weeks`, and every week has a non-empty `"sessions"` list; set `source = "ai"` on success
  4. On any gate failure or validation failure: set `source = "template"` and proceed with existing rule-based path
  5. Fix the `source="ai"` bug: replace all hardcoded `source="ai"` assignments in the method with the resolved `source` variable (applies to both `TrainingPlan` and all `TrainingSession` records in the loop)

**Checkpoint**: User Story 1 fully functional. T003 and T004 should now pass.

---

## Phase 4: User Story 2 — Rule-Based Fallback When AI Is Unavailable (Priority: P2)

**Goal**: When the IA API is unreachable or returns an invalid response, the system silently falls back to rule-based generation, returns HTTP 201, and logs a WARNING.

**Independent Test**: Monkeypatch `generate_full_plan_via_ia` to raise `httpx.ConnectError`; assert HTTP 201, `source="template"` on DB plan, and a WARNING log entry exists.

### Tests for User Story 2 ⚠️ Write first — confirm they FAIL before T009

- [ ] T007 [US2] Write `test_generic_ia_fallback_connection_error` in `train-service/tests/test_plans_generic_ia.py` — use `generic_ia_context`; monkeypatch `generate_full_plan_via_ia` to raise `httpx.ConnectError("connection refused")`; monkeypatch `settings.ia_enabled=True` and `settings.ia_api_url="http://mock"`; assert HTTP 201, `is_new_plan=True`, `source="template"` from DB, and `caplog` contains a WARNING-level entry with `"IA API error"`

- [ ] T008 [US2] Write `test_generic_ia_fallback_invalid_response` in `train-service/tests/test_plans_generic_ia.py` — use `generic_ia_context`; monkeypatch `generate_full_plan_via_ia` to return `{"result": "ok"}` (missing `weeks` key); monkeypatch `settings.ia_enabled=True`; assert HTTP 201, `is_new_plan=True`, `source="template"` from DB

### Implementation for User Story 2

- [ ] T009 [US2] Cross-check `generate_full_plan_via_ia()` in `train-service/app/services/ia_workout_generator.py` against the `x-trainservice-validation` fallback triggers in `specs/002-generic-ia-plan-generation/contracts/ia-generate-plan.yaml` — confirm each trigger is handled: connection error, timeout, HTTP status != 200, missing `weeks` key, `len(weeks) != duration_weeks`, empty sessions list, JSON parse error; add any missing exception catches so all seven triggers return `None` with a WARNING log

**Checkpoint**: User Story 2 fully functional. T007 and T008 should now pass.

---

## Phase 5: User Story 3 — Unchanged Behavior for Athletes Without generic_ia (Priority: P3)

**Goal**: Athletes without the `generic_ia` feature receive rule-based generic plans with `source="template"` — identical to pre-feature behavior.

**Independent Test**: Call `POST /plans/generate` with a context that has no `generic_ia` feature; assert HTTP 201, `source="template"` on DB plan, no IA call attempted.

### Tests for User Story 3 ⚠️ Write first — confirm test passes (feature gate already implemented in T006)

- [ ] T010 [US3] Write `test_generic_plan_without_ia_feature` in `train-service/tests/test_plans_generic_ia.py` — use the standard athlete context (no `generic_ia` feature); do NOT set up any monkeypatch for `generate_full_plan_via_ia` (any accidental IA call would cause an error); assert HTTP 201, `is_new_plan=True`, `source="template"` from DB, `sessions_created > 0`

### Implementation for User Story 3

- [ ] T011 [US3] Run the full pytest suite to confirm no regressions — execute `python -m pytest tests/ -v` from `train-service/`; all 22 pre-existing tests must still pass alongside the 5 new tests in `test_plans_generic_ia.py`; fix any failures before proceeding

**Checkpoint**: All three user stories independently functional. Full suite at 27/27.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation updates and manual validation.

- [ ] T012 [P] Update the `ia_enabled=False` entry in the **Known Technical Debt** table in `athletIQ/CLAUDE.md` — change the description to note that `generate_full_plan_via_ia()` is fully implemented and only `.env` configuration (`IA_ENABLED=true`, `IA_API_URL`, `IA_API_KEY`) is required to activate the AI path; remove from debt table or re-label as "pending configuration"

- [ ] T013 Run `quickstart.md` Scenarios 2, 3, and 4 against a local train-service to validate end-to-end fallback, no-feature, and reuse paths per `specs/002-generic-ia-plan-generation/quickstart.md`; Scenario 1 (AI golden path) is deferred until a real IA endpoint is available — note result in quickstart.md

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — blocks all user stories
- **US1 (Phase 3)**: Depends on Phase 2 — MVP increment
- **US2 (Phase 4)**: Depends on Phase 3 (error handling builds on `generate_full_plan_via_ia()` from T005)
- **US3 (Phase 5)**: Depends on Phase 3 (feature gate from T006 already handles the no-feature path)
- **Polish (Phase 6)**: Depends on Phase 5 (all tests passing)

### User Story Dependencies

- **US1 (P1)**: No dependency on US2/US3 — start immediately after Phase 2
- **US2 (P2)**: Depends on T005 (uses `generate_full_plan_via_ia()` already implemented)
- **US3 (P3)**: Depends on T006 (feature gate already handles no-feature path)

### Within Each User Story

- Tests MUST be written and FAIL before implementation (TDD)
- T005 and T003/T004 can overlap (different files): write tests while implementing the method
- T006 depends on T005 (calls the new method)
- T009 is a review/cross-check after T005 — no new code unless gaps found

### Parallel Opportunities

- T003 and T005: can run in parallel (different files: `test_plans_generic_ia.py` vs `ia_workout_generator.py`)
- T012 and T013: can run in parallel (different files)

---

## Parallel Example: User Story 1

```bash
# Write tests and implement the new method simultaneously (different files):
Task T003: test_generic_ia_generates_ai_plan in tests/test_plans_generic_ia.py
Task T005: generate_full_plan_via_ia() in app/services/ia_workout_generator.py

# Once T005 done, implement T006 (plan_generator.py)
# Then verify T003/T004 pass
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Add `generic_ia_context` fixture
2. Complete Phase 2: Fix `clone_plan()` source bug
3. Write T003, T004 (US1 tests) — verify they FAIL
4. Implement T005: `generate_full_plan_via_ia()`
5. Implement T006: feature gate + `source` fix in `generate_generic_plan()`
6. **STOP and VALIDATE**: T003 and T004 must now pass
7. Deploy/demo if ready

### Incremental Delivery

1. Phase 1 + Phase 2 → Foundation ready
2. Phase 3 (US1) → AI path working; monkeypatched tests passing (MVP)
3. Phase 4 (US2) → Fallback hardened; all 5 tests passing
4. Phase 5 (US3) → Backward compat confirmed; full suite at 27/27
5. Phase 6 → Polish complete

---

## Notes

- [P] tasks operate on different files — no merge conflicts
- [Story] label maps each task to a specific user story for traceability
- `ia_enabled=False` in `.env` means the AI path is never exercised in production — only monkeypatched tests reach it
- Tests use `caplog` (pytest) for WARNING log assertions — no separate logging setup needed
- No Alembic migration required — `source` column already exists in `train.training_plan` and `train.training_session`
- Reuse/clone path (T004) does not require IA setup — the clone exits before the feature gate
- Commit after T002 (foundational fix), after each user story phase passes, and after Phase 6
