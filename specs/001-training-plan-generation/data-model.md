# Data Model: Training Plan Generation

**Phase**: 1 — Design & Contracts
**Date**: 2026-06-17
**Schema**: `train` (PostgreSQL via Supabase)

---

## Entity Overview

```
AthleteProfile (existing)
    │
    ├── TrainingPlan  ──────────────────── self-ref original_plan_id
    │       │
    │       ├── TrainingPlanPhase (week/mesocycle)
    │       │       │
    │       │       └── TrainingPlanSession (join)
    │       │               │
    │       └───────────────┘ (also direct FK plan_id)
    │
    └── TrainingSession (existing, FK via TrainingPlanSession)
            │
            └── TrainingSessionBlock (existing)
```

---

## Table: `train.training_plan`

Owns the root training plan for an athlete + sport combination. Only one record may have `is_active = true` per `(profile_id, sport_id)` pair at any time.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | uuid4() | PK, inherited from BaseModel |
| `created_at` | TIMESTAMPTZ | YES | now() | Inherited |
| `updated_at` | TIMESTAMPTZ | YES | — | Inherited, set on update |
| `profile_id` | UUID | NO | — | FK enforced at app layer to `train.athlete_profile.id` |
| `sport_id` | VARCHAR(50) | NO | — | Sport name string (e.g., "Running") |
| `goal_id` | UUID | YES | — | FK enforced at app layer to `train.athlete_goal.id` |
| `plan_type` | VARCHAR(20) | NO | `"generic"` | Enum: `generic`, `adaptive` |
| `name` | VARCHAR(200) | YES | — | Human-readable plan name |
| `description` | VARCHAR(500) | YES | — | Brief plan description |
| `is_active` | BOOLEAN | NO | `true` | Soft-state flag; only one active plan per profile+sport |
| `start_date` | DATE | YES | — | Plan start date (today on creation) |
| `end_date` | DATE | YES | — | Computed: start_date + duration_weeks |
| `duration_weeks` | INTEGER | NO | `4` | Total plan duration |
| `source` | VARCHAR(20) | NO | `"ai"` | Enum: `ai`, `template`, `coach` |
| `original_plan_id` | UUID | YES | — | Set when this plan is cloned from another; FK at app layer |
| `profile_hash` | VARCHAR(64) | YES | — | SHA-256 of normalized key profile attributes; used for exact reuse matching |

**Indexes**: `profile_id`, `sport_id`, `goal_id`, `original_plan_id`, `profile_hash`

**State transitions**:

```
[created] is_active=true
    │
    └── on clone/new plan for same sport:
        is_active = false   ← soft deactivation (never DELETE)
```

---

## Table: `train.training_plan_phase`

A mesocycle (week) within a training plan. Generic plans pre-create all phases; adaptive plans create one phase per `generate_next_week()` call.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | uuid4() | PK |
| `created_at` | TIMESTAMPTZ | YES | now() | Inherited |
| `updated_at` | TIMESTAMPTZ | YES | — | Inherited |
| `plan_id` | UUID | NO | — | FK → `train.training_plan.id` CASCADE DELETE |
| `name` | VARCHAR(100) | NO | — | e.g., "Week 1" |
| `week_number` | INTEGER | NO | — | 1-based week position in plan |
| `start_date` | DATE | YES | — | Phase start date |
| `end_date` | DATE | YES | — | Phase end date (start_date + 6 days) |
| `focus` | VARCHAR(50) | YES | — | Periodization focus: `build`, `peak`, `taper` |

**Indexes**: `plan_id`

**Periodization logic** (managed by PlanGenerator / IAWorkoutGenerator):
- weeks 1–70% of total: `build`
- weeks 71–90%: `peak`
- last 10%: `taper`

---

## Table: `train.training_plan_session`

Join record that positions a `TrainingSession` within a plan phase. Separates plan structure (schedule) from session content.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | uuid4() | PK |
| `created_at` | TIMESTAMPTZ | YES | now() | Inherited |
| `updated_at` | TIMESTAMPTZ | YES | — | Inherited |
| `plan_id` | UUID | NO | — | FK → `train.training_plan.id` CASCADE DELETE |
| `phase_id` | UUID | NO | — | FK → `train.training_plan_phase.id` CASCADE DELETE |
| `session_id` | UUID | NO | — | FK → `train.training_session.id` CASCADE DELETE |
| `week_number` | INTEGER | NO | — | Denormalized for faster schedule queries |
| `day_number` | INTEGER | NO | — | Day within the week (1-based) |
| `scheduled_date` | DATE | YES | — | Absolute calendar date for this session |
| `order` | INTEGER | NO | `0` | Display order within the phase |

**Indexes**: `plan_id`, `phase_id`, `session_id`

---

## Existing Entities (referenced, not modified)

### `train.athlete_profile`
- Identified by `profile_id` in TrainingPlan / TrainingPlanSession
- Used to look up the athlete for ownership checks and for populating `profile_id` on cloned sessions

### `train.training_session`
- Owns the actual workout content (status, planned_date, planned_duration_minutes, source)
- Each athlete gets their own session records — sessions are NOT shared across athletes in clone flows

### `train.training_session_block`
- Owns warmup / main / cooldown block content for a session
- Cloned 1:1 when cloning a plan (new block records for the new session)

---

## Service ↔ Model Interactions

```
PlanGenerator.generate_generic_plan()
  → TrainingPlan (1)
  → TrainingPlanPhase (N = duration_weeks)
  → TrainingSession (N * days_per_week)
  → TrainingSessionBlock (3 per session: warmup, main, cooldown)
  → TrainingPlanSession (N * days_per_week)

PlanGenerator.generate_adaptive_plan_structure()
  → TrainingPlan (1, no phases)

IAWorkoutGenerator.generate_next_week()
  → TrainingPlanPhase (1 per call)
  → TrainingSession (days_per_week per call)
  → TrainingSessionBlock (3 per session)
  → TrainingPlanSession (days_per_week per call)

PlanMatcher.clone_plan(source_plan, profile_id)
  → TrainingPlan (1, original_plan_id = source.id)
  → TrainingPlanPhase (N = len(source.phases))
  → TrainingSession (new, profile_id = target athlete)
  → TrainingSessionBlock (clone of source blocks)
  → TrainingPlanSession (N per phase)
  → deactivates: existing active TrainingPlan for same profile+sport

PlanMatcher.can_reuse_plan(profile_data)
  → reads: TrainingPlan (exact hash match or similarity scan)
  → reads: athlete_sport_profile_value (for similarity reconstruction)
```

---

## Profile Hash Inputs

The `profile_hash` column on `training_plan` is a SHA-256 of:

```python
match_data = {
    "sport":           profile_data.get("sport"),
    "level":           profile_data.get("level"),
    "primary_goal":    profile_data.get("primary_goal"),
    "days_per_week":   profile_data.get("days_per_week"),
    "weekly_frequency": profile_data.get("weekly_frequency"),
}
normalized = json.dumps(match_data, sort_keys=True)
hash = hashlib.sha256(normalized.encode()).hexdigest()
```

The hash is stored only on generic plans (adaptive plans set `profile_hash=None`).

---

## Soft-State Constraint

At most one `training_plan` row with `is_active = true` per `(profile_id, sport_id)` pair. This invariant is enforced at the application layer (not via DB unique constraint) because historical inactive records must coexist. `clone_plan()` and `generate_generic_plan()` both call an internal `_deactivate_current_plan()` step before persisting the new plan.
