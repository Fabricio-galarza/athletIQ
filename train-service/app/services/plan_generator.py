"""
Plan generation service for CU-TRAIN-04.
Handles both generic and adaptive plan generation.
"""

from datetime import date, timedelta
from typing import Dict, Any, List, Optional, Tuple
from uuid import uuid4
from sqlalchemy.orm import Session
from sqlalchemy import text

import logging

from app.core.context import UserContext
from app.core.exceptions import ValidationError

logger = logging.getLogger(__name__)
from app.infra.db.models.plan import TrainingPlan, TrainingPlanPhase, TrainingPlanSession
from app.infra.db.models.session import TrainingSession, TrainingSessionBlock
from app.infra.db.models.athlete import AthleteProfile
from app.infra.db.models.sport_profile import AthleteSportProfileValue
from app.infra.db.models.goal import AthleteGoalValue
from app.services.plan_matcher import PlanMatcher
from app.services.ia_workout_generator import IAWorkoutGenerator


class PlanGenerator:
    """
    Service for generating training plans.
    Supports generic (complete) and adaptive (week-by-week) generation.
    """
    
    def __init__(self, db: Session, user_id: str, sport_id: str, context: UserContext):
        self.db = db
        self.user_id = user_id
        self.sport_id = sport_id
        self.context = context
    
    def _get_athlete_profile_data(self) -> Dict[str, Any]:
        """
        Fetch and consolidate athlete profile data.
        
        Returns:
            Dictionary with all relevant athlete attributes
        """
        logger.info("=== ENTERING _get_athlete_profile_data ===")
        profile_data = {}

        logger.info("Fetching athlete profile data...")

        # Get athlete profile
        profile = self.db.query(AthleteProfile).filter_by(
            user_id=self.user_id
        ).first()

        if not profile:
            logger.warning(f"No athlete profile found for user {self.user_id}")
            raise ValidationError("Athlete profile not found")

        logger.info(f"Profile found: {profile.id}")
        # Get field name to value mapping from context
        field_name_map = self._get_field_name_map()
        logger.info(f"Field name map has {len(field_name_map)} entries")
        logger.info(f"field_name_map (field_id -> name): {field_name_map}")

        # Get sport profile values
        query = text("""
            SELECT aspv.field_id, aspv.value
            FROM train.athlete_sport_profile_value aspv
            JOIN train.athlete_sport_profile asp ON aspv.sport_profile_id = asp.id
            WHERE asp.profile_id = :profile_id
              AND asp.sport_id = :sport_id
        """)
        
        result = self.db.execute(query, {
            "profile_id": profile.id,
            "sport_id": self.sport_id
        }).fetchall()
        logger.info(f"Found {len(result)} sport profile values")
        logger.info(f"athlete_sport_profile_value raw rows: {[tuple(row) for row in result]}")
        for row in result:
            field_name = field_name_map.get(str(row[0]), str(row[0]))
            profile_data[field_name] = row[1]
        logger.info(f"profile_data after sport profile loop: {profile_data}")

        # Get active goal
        goal_values = self.db.query(AthleteGoalValue).join(
            AthleteGoalValue.goal
        ).filter(
            AthleteGoalValue.goal.has(
                profile_id=profile.id,
                sport_id=self.sport_id,
                is_active=True
            )
        ).all()

        logger.info(f"Found {len(goal_values)} goal values")

        for val in goal_values:
            field_name = field_name_map.get(str(val.field_id), str(val.field_id))
            profile_data[f"goal_{field_name}"] = val.value

        # Get active training structure values (for days_per_week)
        ts_form = self.context.get_form("athlete_training_structure")
        ts_field_map = {}
        if ts_form:
            for field in ts_form.fields:
                if field.id:
                    ts_field_map[str(field.id)] = field.name
        logger.info(f"ts_field_map (training structure field_id -> name): {ts_field_map}")

        ts_query = text("""
            SELECT atsv.field_id, atsv.value
            FROM train.athlete_training_structure_value atsv
            JOIN train.athlete_training_structure ats ON atsv.structure_id = ats.id
            WHERE ats.profile_id = :profile_id
              AND ats.sport_id = :sport_id
              AND ats.is_active = true
        """)

        ts_result = self.db.execute(ts_query, {
            "profile_id": profile.id,
            "sport_id": self.sport_id
        }).fetchall()

        logger.info(f"Found {len(ts_result)} training structure values")
        logger.info(f"athlete_training_structure_value raw rows: {[tuple(row) for row in ts_result]}")
        for row in ts_result:
            field_name = ts_field_map.get(str(row[0]), str(row[0]))
            if field_name == "days_per_week":
                profile_data["days_per_week"] = row[1]

        # Check required fields
        required_fields = ["level", "primary_goal", "days_per_week"]
        for field in required_fields:
            if field not in profile_data:
                logger.warning(f"Missing required field in profile: {field}")
        
        return profile_data
    
    def _get_field_name_map(self) -> Dict[str, str]:
        """
        Build mapping from field_id to field_name using context.
        
        Returns:
            Dictionary mapping field_id to field_name
        """
        field_map = {}

        # Get from athlete_goal form first (goal_ prefix)
        goal_form = self.context.get_form("athlete_goal")
        if goal_form:
            for field in goal_form.fields:
                if field.id:
                    field_map[str(field.id)] = f"goal_{field.name}"

        # Get from athlete_profile form (no prefix) — overwrites any shared field_ids
        form = self.context.get_form("athlete_profile")
        if form:
            for field in form.fields:
                if field.id:
                    field_map[str(field.id)] = field.name

        return field_map
    
    def _calculate_plan_duration(self, profile_data: Dict[str, Any]) -> int:
        """
        Calculate plan duration in weeks based on goal target date.
        
        Args:
            profile_data: Athlete profile data
        
        Returns:
            Number of weeks for the plan
        """
        # Default duration
        default_weeks = 4
        
        # Try to get target date from goal
        target_date_str = profile_data.get("goal_target_date")
        
        if target_date_str:
            try:
                target_date = date.fromisoformat(target_date_str)
                today = date.today()
                days_until = (target_date - today).days
                
                if days_until > 0:
                    # Convert days to weeks, minimum 1, maximum 52
                    weeks = max(1, min(52, days_until // 7))
                    return weeks
            except (ValueError, TypeError):
                pass
        
        return default_weeks
    
    def generate_generic_plan(self) -> Tuple[TrainingPlan, List[TrainingSession]]:
        """
        Generate a complete generic plan (all sessions upfront).

        Deactivates any existing active plan for the same athlete + sport before
        creating the new one (soft-state, FR-010).

        Returns:
            Tuple of (TrainingPlan, list of TrainingSession)
        """
        # Get athlete profile data
        profile_data = self._get_athlete_profile_data()

        # Check if profile is complete
        if not self._is_profile_complete(profile_data):
            raise ValidationError("Profile incomplete. Please complete your profile first.")

        profile_id = self._get_profile_id()

        # Deactivate existing active plan for this athlete + sport (soft state)
        self.db.query(TrainingPlan).filter_by(
            profile_id=profile_id,
            sport_id=self.sport_id,
            is_active=True,
        ).update({"is_active": False})

        # Generate profile hash for matching
        matcher = PlanMatcher(self.db, self.user_id, self.sport_id, self.context)
        profile_hash = matcher.generate_profile_hash(profile_data)

        # Calculate plan duration
        duration_weeks = self._calculate_plan_duration(profile_data)

        # Get days per week from profile
        days_per_week = int(profile_data.get("days_per_week", 4))

        # Calculate start date (today)
        start_date = date.today()

        # Create training plan
        plan = TrainingPlan(
            profile_id=profile_id,
            sport_id=self.sport_id,
            plan_type="generic",
            name=f"{self.sport_id} Training Plan - {start_date.isoformat()}",
            description=f"{duration_weeks} week plan based on your profile",
            is_active=True,
            start_date=start_date,
            end_date=start_date + timedelta(weeks=duration_weeks),
            duration_weeks=duration_weeks,
            source="ai",
            profile_hash=profile_hash
        )
        
        self.db.add(plan)
        self.db.flush()
        
        sessions = []
        ia_gen = IAWorkoutGenerator(self.db, self.user_id, self.sport_id)

        # Generate phases (weeks)
        for week in range(1, duration_weeks + 1):
            # Create phase for this week
            phase = TrainingPlanPhase(
                plan_id=plan.id,
                name=f"Week {week}",
                week_number=week,
                start_date=start_date + timedelta(weeks=week - 1),
                end_date=start_date + timedelta(weeks=week) - timedelta(days=1),
                focus=self._get_week_focus(week, duration_weeks)
            )
            self.db.add(phase)
            self.db.flush()

            # Generate workouts via IAWorkoutGenerator rule-based logic
            workouts = ia_gen._generate_rule_based_workouts(
                profile_data, days_per_week, week, duration_weeks, 1.0
            )

            # Create sessions for each workout
            for day, workout_data in enumerate(workouts, start=1):
                # Create training session
                session = TrainingSession(
                    profile_id=profile_id,
                    sport_id=self.sport_id,
                    status="planned",
                    source="ai",
                    planned_date=phase.start_date + timedelta(days=day - 1),
                    planned_duration_minutes=workout_data.get("duration_minutes", 45)
                )
                self.db.add(session)
                self.db.flush()

                # Create blocks for the session
                for block_order, block_data in enumerate(workout_data.get("blocks", []), start=1):
                    block = TrainingSessionBlock(
                        session_id=session.id,
                        order=block_order,
                        block_type=block_data.get("block_type"),
                        duration_minutes=block_data.get("duration_minutes"),
                        intensity=block_data.get("intensity"),
                        instructions=block_data.get("instructions")
                    )
                    self.db.add(block)

                # Link session to plan phase
                plan_session = TrainingPlanSession(
                    plan_id=plan.id,
                    phase_id=phase.id,
                    session_id=session.id,
                    week_number=week,
                    day_number=day,
                    scheduled_date=phase.start_date + timedelta(days=day - 1),
                    order=day
                )
                self.db.add(plan_session)

                sessions.append(session)
        
        self.db.commit()
        
        return plan, sessions
    
    def generate_adaptive_plan_structure(self) -> TrainingPlan:
        """
        Generate only the TrainingPlan header for an adaptive plan.

        Phases (weeks) are created on-demand by IAWorkoutGenerator.generate_next_week()
        as the athlete progresses. Deactivates any existing active plan for the same
        athlete + sport before creating the new one (soft-state, FR-010).

        Returns:
            Newly created TrainingPlan (no phases).
        """
        # Get athlete profile data
        profile_data = self._get_athlete_profile_data()

        # Check if profile is complete
        if not self._is_profile_complete(profile_data):
            raise ValidationError("Profile incomplete. Please complete your profile first.")

        profile_id = self._get_profile_id()

        # Deactivate existing active plan for this athlete + sport (soft state)
        self.db.query(TrainingPlan).filter_by(
            profile_id=profile_id,
            sport_id=self.sport_id,
            is_active=True,
        ).update({"is_active": False})

        # Calculate plan duration
        duration_weeks = self._calculate_plan_duration(profile_data)

        # Calculate start date (today)
        start_date = date.today()

        # Create plan header — phases are created week by week
        plan = TrainingPlan(
            profile_id=profile_id,
            sport_id=self.sport_id,
            plan_type="adaptive",
            name=f"Adaptive {self.sport_id} Plan - {start_date.isoformat()}",
            description=f"{duration_weeks} week adaptive plan that adjusts to your progress",
            is_active=True,
            start_date=start_date,
            end_date=start_date + timedelta(weeks=duration_weeks),
            duration_weeks=duration_weeks,
            source="ai"
        )

        self.db.add(plan)
        self.db.commit()

        return plan
    
    def _get_profile_id(self) -> str:
        """Get athlete profile ID."""
        profile = self.db.query(AthleteProfile).filter_by(
            user_id=self.user_id
        ).first()
        
        if not profile:
            raise ValidationError("Athlete profile not found")
        
        return str(profile.id)
    
    def _is_profile_complete(self, profile_data: Dict[str, Any]) -> bool:
        """
        Check if athlete has provided enough data for plan generation.
        
        Returns:
            True if profile has required fields, False otherwise
        """
        required_fields = ["level", "primary_goal", "days_per_week"]
        
        for field in required_fields:
            if not profile_data.get(field):
                logger.info(f"Profile incomplete: missing '{field}'")
                return False

        logger.info(f"Profile complete for user {self.user_id}")
        return True
    
    def _get_week_focus(self, week_number: int, total_weeks: int) -> str:
        """
        Determine training focus for a given week.
        
        Periodization pattern:
        - Weeks 1-70%: Build phase
        - Weeks 70-90%: Peak phase
        - Last 10%: Taper phase
        """
        progress = week_number / total_weeks
        
        if progress <= 0.7:
            return "build"
        elif progress <= 0.9:
            return "peak"
        else:
            return "taper"