# Research: Generic Training Plan Generation with AI

**Feature**: 002-generic-ia-plan-generation  
**Date**: 2026-06-24

---

## 1. Current `generate_generic_plan()` never calls the IA API

**Finding**: `PlanGenerator.generate_generic_plan()` calls `ia_gen._generate_rule_based_workouts()` directly. The external IA API (`_call_ia_api()`) is only invoked inside `IAWorkoutGenerator.generate_next_week()`, which is the adaptive per-week path. The generic path never reaches the AI.

**Decision**: Add `IAWorkoutGenerator.generate_full_plan_via_ia()` — a new, independent sync method that calls `{ia_api_url}/generate-plan` for the full plan. Keep `_call_ia_api()` (async) untouched for the adaptive path.

---

## 2. `source="ai"` bug on rule-based generic plans

**Finding**: `generate_generic_plan()` always writes `source="ai"` on both `TrainingPlan` (line 233) and `TrainingSession` (line 269), even though it currently always uses rule-based generation. This is incorrect per FR-007 and FR-008.

**Decision**: Fix the `source` field to be set dynamically:
- `"ai"` → when `generate_full_plan_via_ia()` returns a valid response
- `"template"` → for all other cases (rule-based, AI disabled, no feature, fallback)

---

## 3. Sync vs async httpx for the new IA call

**Finding**: `generate_generic_plan()` is a synchronous method. The router calls it without `await` (line 121 of `plans.py`). Calling `asyncio.run()` inside a sync method from an async FastAPI handler raises a "cannot run nested event loop" error. The existing `_call_ia_api()` is async because it's always called from the async `generate_next_week()`.

**Decision**: New `generate_full_plan_via_ia()` uses `httpx.Client` (sync) with `timeout=60.0`. This is the standard pattern for sync httpx usage and is consistent with the httpx library version already in the project.

**Alternatives rejected**:
- Making `generate_generic_plan()` async: would require updating the router, all test callers, and breaks the existing method signature — too much blast radius for this feature.
- `asyncio.get_event_loop().run_until_complete()`: deprecated in Python 3.10+ and raises RuntimeError in a running event loop.

---

## 4. IA response validation rules (FR-011)

**Finding**: The spec treats a partial AI response (fewer weeks than expected) as invalid and requires full fallback — no hybrid plan (edge case in spec). The adaptive path has a simpler validation: check `len(workouts) < days_per_week`.

**Decision**: A valid full-plan response requires:
1. JSON body with `"weeks"` key
2. `len(weeks) == duration_weeks`
3. Each week has a non-empty `"sessions"` list

Any deviation triggers WARNING log + rule-based fallback. This is stricter than the adaptive path by design — a partial generic plan would create inconsistent phase coverage.

---

## 5. Clone `source` field

**Finding**: `PlanMatcher.clone_plan()` currently copies `source_plan.source` to the new `TrainingPlan`. If the original was `source="ai"`, the clone also gets `"ai"`. This contradicts the spec assumption ("clone is derived, not independently AI-generated") and would incorrectly label clones as AI-generated.

**Decision**: Hardcode `source="template"` in `clone_plan()` for the new `TrainingPlan` record. Session source within the clone is preserved (sessions are direct structural copies — this is acceptable since session-level source isn't queried in business logic).

**Impact on existing tests**: `test_generate_generic_plan_exact_reuse`, `test_generate_generic_plan_similarity_reuse`, `test_generate_generic_plan_force_regenerate` — none of these assert on `source` of the cloned plan, so no regressions.

---

## 6. Feature gate conditions

**Finding**: The spec defines "active AI configuration" as `ia_enabled=True` AND `ia_api_url` is non-empty. Settings (`config.py`) already has both: `ia_enabled: bool = False` and `ia_api_url: Optional[str] = None`.

**Decision**: The gate in `generate_generic_plan()` evaluates:
```python
context.has_feature("generic_ia") and settings.ia_enabled and bool(settings.ia_api_url)
```
All three must be true; otherwise rule-based path with `source="template"`.

---

## 7. Test strategy for IA method

**Finding**: The existing test for adaptive AI fallback (`test_generate_next_week_ai_failure_falls_back_to_rules`) uses `monkeypatch.setattr(ia_module.settings, ...)` to set `ia_enabled=True` and `ia_api_url` to a closed port. The real network connection is attempted and fails, triggering the fallback.

**Decision**: Use the same monkeypatch approach for the new fallback tests. For the happy-path AI test, monkeypatch `IAWorkoutGenerator.generate_full_plan_via_ia` directly to return a synthetic weeks list — this avoids needing a real IA server in CI and is consistent with how the adaptive path is tested (the method boundary is the mock point).

**New context fixture needed**: `generic_ia_context` — a `UserContext` with `features=["generic_ia"]`. Reuse existing `_build_context()` helper from `conftest.py`.

---

## 8. No new DB schema changes required

**Finding**: `TrainingPlan.source` already exists as `Column(String(20))`. `profile_hash`, `original_plan_id` fields are unchanged. No new tables, columns, or Alembic migrations are needed for this feature.

**Decision**: No migration file. Alembic is not touched.

---

## 9. API contract impact

**Finding**: The CU-TRAIN-04 Generate Plan YAML contract does not expose `source` in the `PlanGenerationResponse`. The `source` field is returned by `GET /plans/active` but the response schema there is `dict` (untyped). No response schema changes are needed.

**Decision**: The existing CU-TRAIN-04 contracts are not modified. A new `contracts/ia-generate-plan.yaml` is created as a reference contract for the external IA service — it defines what train-service sends to and expects from the AI provider.
