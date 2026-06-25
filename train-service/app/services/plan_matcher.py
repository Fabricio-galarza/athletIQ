"""
Plan matching service for CU-TRAIN-04.
Evaluates if an existing plan can be reused for an athlete.
"""

import hashlib
import json
from datetime import date, timedelta
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.context import UserContext
from app.infra.db.models.plan import TrainingPlan, TrainingPlanPhase, TrainingPlanSession
from app.infra.db.models.session import TrainingSession, TrainingSessionBlock


class PlanMatcher:
    """
    Service to find reusable plans based on athlete profile.
    
    Strategy:
    1. Generate a profile hash from key attributes
    2. Look for existing plans with matching hash
    3. Calculate similarity score for fuzzy matching
    """
    
    # Key attributes for plan matching
    MATCH_ATTRIBUTES = [
        "sport",
        "level",
        "primary_goal",
        "days_per_week",
        "weekly_frequency"
    ]
    
    def __init__(self, db: Session, user_id: str, sport_id: str, context: UserContext):
        self.db = db
        self.user_id = user_id
        self.sport_id = sport_id
        self.context = context
    
    def generate_profile_hash(self, profile_data: Dict[str, Any]) -> str:
        """
        Generate a unique hash from athlete profile for exact matching.
        
        Args:
            profile_data: Dictionary with athlete profile attributes
        
        Returns:
            SHA256 hash of normalized profile data
        """
        # Extract only relevant attributes for matching
        match_data = {}
        for attr in self.MATCH_ATTRIBUTES:
            if attr in profile_data:
                match_data[attr] = profile_data[attr]
        
        # Normalize and sort for consistent hashing
        normalized = json.dumps(match_data, sort_keys=True)
        
        return hashlib.sha256(normalized.encode()).hexdigest()
    
    def find_exact_match(self, profile_hash: str) -> Optional[TrainingPlan]:
        """
        Find an existing plan with exact profile hash match.
        
        Args:
            profile_hash: Hash generated from athlete profile
        
        Returns:
            TrainingPlan if found, None otherwise
        """
        query = text("""
            SELECT id FROM train.training_plan
            WHERE profile_hash = :hash
              AND sport_id = :sport_id
              AND plan_type = :plan_type
              AND is_active = true
            LIMIT 1
        """)
        
        result = self.db.execute(query, {
            "hash": profile_hash,
            "sport_id": self.sport_id,
            "plan_type": "generic"  # Only generic plans can be reused
        }).first()
        
        if result:
            return self.db.query(TrainingPlan).filter_by(id=result[0]).first()
        
        return None
    
    def find_similar_plan(self, profile_data: Dict[str, Any], threshold: float = 0.8) -> Optional[TrainingPlan]:
        """
        Find a similar plan using weighted scoring when exact match fails.
        
        Args:
            profile_data: Athlete profile data
            threshold: Minimum similarity score (0.0 to 1.0)
        
        Returns:
            Best matching TrainingPlan if similarity >= threshold
        """
        # Weight configuration for each attribute
        weights = {
            "level": 0.30,
            "primary_goal": 0.30,
            "days_per_week": 0.20,
            "weekly_frequency": 0.20,
        }
        
        # Get all generic plans for this sport
        plans = self.db.query(TrainingPlan).filter_by(
            sport_id=self.sport_id,
            plan_type="generic",
            is_active=True
        ).all()
        
        if not plans:
            return None
        
        best_plan = None
        best_score = 0.0
        
        for plan in plans:
            score = self._calculate_similarity(profile_data, plan, weights)
            
            if score > best_score and score >= threshold:
                best_score = score
                best_plan = plan
        
        return best_plan
    
    def _get_plan_owner_profile(self, plan: TrainingPlan) -> Dict[str, Any]:
        """
        Reconstruct profile attributes of the athlete who owns the given plan.

        Uses field names from UserContext forms to map field_id values — avoids
        a cross-schema JOIN to core.field and stays consistent with how
        PlanGenerator resolves field names.

        Returns:
            Dict mapping field names to string values, or empty dict on failure.
        """
        try:
            # Build field_id → field_name map from context forms
            field_name_map: Dict[str, str] = {}
            form = self.context.get_form("athlete_profile")
            if form:
                for field in form.fields:
                    if field.id:
                        field_name_map[str(field.id)] = field.name

            result = self.db.execute(
                text("""
                    SELECT aspv.field_id::text, aspv.value
                    FROM train.athlete_sport_profile_value aspv
                    JOIN train.athlete_sport_profile asp
                        ON aspv.sport_profile_id = asp.id
                    WHERE asp.profile_id = :profile_id
                      AND asp.sport_id   = :sport_id
                """),
                {"profile_id": str(plan.profile_id), "sport_id": self.sport_id},
            ).fetchall()

            profile: Dict[str, Any] = {}
            for row in result:
                field_name = field_name_map.get(str(row[0]), str(row[0]))
                profile[field_name] = row[1]
            return profile
        except Exception:
            return {}

    def _calculate_similarity(self, profile_data: Dict[str, Any], plan: TrainingPlan, weights: Dict[str, float]) -> float:
        """
        Calcula el score de similitud entre el perfil actual y el plan existente.

        Estrategia:
        - Recupera el perfil del atleta original del plan desde la BD.
        - Compara atributo a atributo con pesos definidos.
        - Atributos categóricos: match exacto = peso completo, sino 0.
        - Atributos numéricos (days_per_week): score inverso a la diferencia relativa.

        Returns:
            Float entre 0.0 y 1.0
        """
        plan_profile = self._get_plan_owner_profile(plan)

        if not plan_profile:
            return 0.0

        score = 0.0

        # ── Atributos categóricos ─────────────────────────────────────────────
        categorical = ["level", "primary_goal"]
        for attr in categorical:
            weight = weights.get(attr, 0.0)
            current_val = str(profile_data.get(attr, "")).strip().lower()
            plan_val    = str(plan_profile.get(attr, "")).strip().lower()

            if current_val and plan_val and current_val == plan_val:
                score += weight

        # ── Atributos numéricos ───────────────────────────────────────────────
        # days_per_week: diferencia de 0 → 1.0, diferencia de ≥3 → 0.0
        for attr in ["days_per_week", "weekly_frequency"]:
            weight = weights.get(attr, 0.0)
            try:
                current_val = float(profile_data.get(attr, 0))
                plan_val    = float(plan_profile.get(attr, 0))

                if current_val > 0 and plan_val > 0:
                    diff = abs(current_val - plan_val)
                    # Tolerancia máxima: 3 días de diferencia → score 0
                    attr_score = max(0.0, 1.0 - diff / 3.0)
                    score += weight * attr_score
            except (TypeError, ValueError):
                pass

        return round(score, 4)

    def can_reuse_plan(self, profile_data: Dict[str, Any]) -> Tuple[bool, Optional[TrainingPlan], str]:
        """
        Determine whether an existing plan can be reused for the current athlete.

        Strategy:
        1. Generate a SHA-256 hash of the profile's key attributes.
        2. Look for an exact hash match in active generic plans.
        3. If no exact match, look for a plan with similarity ≥ 80%.

        Args:
            profile_data: Current athlete's profile attributes (field_name → value).

        Returns:
            Tuple of (can_reuse, matching_plan_or_None, reason_string).
        """
        profile_hash = self.generate_profile_hash(profile_data)

        exact_plan = self.find_exact_match(profile_hash)
        if exact_plan:
            return True, exact_plan, "Exact profile match found"

        similar_plan = self.find_similar_plan(profile_data, threshold=0.80)
        if similar_plan:
            return True, similar_plan, "Similar profile match found"

        return False, None, "No reusable plan found"

    def clone_plan(self, source_plan: TrainingPlan, profile_id: str) -> Tuple[TrainingPlan, int]:
        """
        Clone an existing plan for a target athlete.

        Creates a new TrainingPlan anchored to today with new TrainingSession and
        TrainingSessionBlock records owned by the target athlete. Any pre-existing
        active plan for (profile_id, sport_id) is deactivated first (soft-state).
        The cloned plan always receives source="template" regardless of the source
        plan's source — a clone is derived, not independently AI-generated.

        Args:
            source_plan: The plan whose structure will be cloned.
            profile_id: UUID string of the target athlete's AthleteProfile.

        Returns:
            Tuple of (new_plan, sessions_created_count).
        """
        import logging
        logger = logging.getLogger(__name__)

        # Deactivate any existing active plan for this athlete + sport (soft state)
        self.db.query(TrainingPlan).filter_by(
            profile_id=profile_id,
            sport_id=self.sport_id,
            is_active=True,
        ).update({"is_active": False})

        today = date.today()
        date_offset = (today - source_plan.start_date) if source_plan.start_date else timedelta(0)

        new_end = (
            today + timedelta(weeks=source_plan.duration_weeks)
            if source_plan.duration_weeks
            else None
        )

        new_plan = TrainingPlan(
            profile_id=profile_id,
            sport_id=self.sport_id,
            plan_type=source_plan.plan_type,
            name=source_plan.name,
            description=source_plan.description,
            is_active=True,
            start_date=today,
            end_date=new_end,
            duration_weeks=source_plan.duration_weeks,
            source="template",  # clone is derived, not independently AI-generated
            original_plan_id=source_plan.id,
            profile_hash=source_plan.profile_hash,
            goal_id=source_plan.goal_id,
        )
        self.db.add(new_plan)
        self.db.flush()

        sessions_created = 0

        source_phases = (
            self.db.query(TrainingPlanPhase)
            .filter_by(plan_id=source_plan.id)
            .order_by(TrainingPlanPhase.week_number)
            .all()
        )

        for source_phase in source_phases:
            new_start = source_phase.start_date + date_offset if source_phase.start_date else None
            new_end_phase = source_phase.end_date + date_offset if source_phase.end_date else None

            new_phase = TrainingPlanPhase(
                plan_id=new_plan.id,
                name=source_phase.name,
                week_number=source_phase.week_number,
                start_date=new_start,
                end_date=new_end_phase,
                focus=source_phase.focus,
            )
            self.db.add(new_phase)
            self.db.flush()

            source_plan_sessions = (
                self.db.query(TrainingPlanSession)
                .filter_by(phase_id=source_phase.id)
                .order_by(TrainingPlanSession.day_number)
                .all()
            )

            for source_ps in source_plan_sessions:
                source_session = (
                    self.db.query(TrainingSession)
                    .filter_by(id=source_ps.session_id)
                    .first()
                )
                if not source_session:
                    continue

                new_planned_date = (
                    source_session.planned_date + date_offset
                    if source_session.planned_date
                    else None
                )
                new_session = TrainingSession(
                    profile_id=profile_id,
                    sport_id=self.sport_id,
                    status="planned",
                    source=source_session.source,
                    planned_date=new_planned_date,
                    planned_duration_minutes=source_session.planned_duration_minutes,
                )
                self.db.add(new_session)
                self.db.flush()

                for source_block in self.db.query(TrainingSessionBlock).filter_by(
                    session_id=source_session.id
                ).all():
                    self.db.add(TrainingSessionBlock(
                        session_id=new_session.id,
                        order=source_block.order,
                        block_type=source_block.block_type,
                        duration_minutes=source_block.duration_minutes,
                        intensity=source_block.intensity,
                        instructions=source_block.instructions,
                    ))

                new_scheduled = (
                    source_ps.scheduled_date + date_offset
                    if source_ps.scheduled_date
                    else None
                )
                self.db.add(TrainingPlanSession(
                    plan_id=new_plan.id,
                    phase_id=new_phase.id,
                    session_id=new_session.id,
                    week_number=source_ps.week_number,
                    day_number=source_ps.day_number,
                    scheduled_date=new_scheduled,
                    order=source_ps.order,
                ))
                sessions_created += 1

        self.db.commit()
        logger.info(
            "Cloned plan %s → %s (%d sessions) for profile %s",
            source_plan.id, new_plan.id, sessions_created, profile_id,
        )
        return new_plan, sessions_created
