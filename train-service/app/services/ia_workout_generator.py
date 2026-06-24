"""
IA hybrid workout generator for CU-TRAIN-04.
Generates personalized workouts using rules + optional external IA.
"""

import json
import logging
import httpx
from typing import Dict, Any, List, Optional
from datetime import date, timedelta
from sqlalchemy.orm import Session

from app.core.config import get_settings

logger = logging.getLogger(__name__)
from app.core.exceptions import ValidationError
from app.infra.db.models.plan import TrainingPlan, TrainingPlanPhase, TrainingPlanSession
from app.infra.db.models.session import TrainingSession, TrainingSessionBlock

settings = get_settings()


class IAWorkoutGenerator:
    """
    Hybrid workout generator for adaptive plans.
    
    Strategy:
    1. Use rule-based generation for predictable patterns (low cost)
    2. Call external IA only when needed (complex adaptations)
    3. Cache IA-generated templates for reuse
    """
    
    def __init__(self, db: Session, user_id: str, sport_id: str):
        self.db = db
        self.user_id = user_id
        self.sport_id = sport_id
    
    async def generate_next_week(
        self,
        plan_id: str,
        profile_data: Dict[str, Any],
        previous_metrics: Optional[List[Dict[str, Any]]] = None
    ) -> List[TrainingSession]:
        """
        Generate the next week's workouts for an adaptive plan.
        
        Args:
            plan_id: ID of the adaptive plan
            profile_data: Athlete profile data
            previous_metrics: Metrics from previous week (for adaptation)
        
        Returns:
            List of created TrainingSession
        """
        # Get the plan
        plan = self.db.query(TrainingPlan).filter_by(id=plan_id).first()
        if not plan:
            raise ValidationError(f"Plan {plan_id} not found")
        
        # Determinar la siguiente semana a generar.
        # Solo contamos fases que YA tienen sesiones asignadas (semanas generadas),
        # no shells vacíos. Así evitamos el bug de planes adaptativos donde todas
        # las fases se pre-creaban sin sesiones.
        generated_week_numbers = (
            self.db.query(TrainingPlanPhase.week_number)
            .join(
                TrainingPlanSession,
                TrainingPlanSession.phase_id == TrainingPlanPhase.id
            )
            .filter(TrainingPlanPhase.plan_id == plan.id)
            .distinct()
            .all()
        )
        generated_count = len(generated_week_numbers)
        next_week_number = generated_count + 1

        if next_week_number > plan.duration_weeks:
            raise ValidationError("Plan already completed: all weeks have been generated")
        
        # Analyze previous week metrics to adjust intensity
        intensity_multiplier = self._calculate_intensity_adjustment(previous_metrics)
        
        # Generate workouts for each day of the week
        days_per_week = int(profile_data.get("days_per_week", 4))
        sessions = []
        
        # Try to use external IA first (if enabled)
        workouts = None
        if settings.ia_enabled:
            workouts = await self._call_ia_api(profile_data, previous_metrics, days_per_week)
        
        # Fallback to rule-based generation
        if not workouts or len(workouts) < days_per_week:
            workouts = self._generate_rule_based_workouts(
                profile_data, days_per_week, next_week_number, plan.duration_weeks, intensity_multiplier
            )
        
        # Calculate start date for the week
        start_date = plan.start_date + timedelta(weeks=next_week_number - 1)
        
        # Create phase for this week
        phase = TrainingPlanPhase(
            plan_id=plan.id,
            name=f"Week {next_week_number}",
            week_number=next_week_number,
            start_date=start_date,
            end_date=start_date + timedelta(days=6),
            focus=self._get_week_focus(next_week_number, plan.duration_weeks)
        )
        self.db.add(phase)
        self.db.flush()
        
        # Create sessions for each workout
        for day, workout_data in enumerate(workouts, start=1):
            session = TrainingSession(
                profile_id=self._get_profile_id(),
                sport_id=self.sport_id,
                status="planned",
                source="ai",
                planned_date=start_date + timedelta(days=day - 1),
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
                week_number=next_week_number,
                day_number=day,
                scheduled_date=start_date + timedelta(days=day - 1),
                order=day
            )
            self.db.add(plan_session)
            
            sessions.append(session)
        
        self.db.commit()
        
        return sessions
    
    def _calculate_intensity_adjustment(self, previous_metrics: Optional[List[Dict[str, Any]]]) -> float:
        """
        Calculate intensity adjustment based on previous week's performance.
        
        Returns:
            Multiplier (0.7 to 1.3)
        """
        if not previous_metrics or len(previous_metrics) == 0:
            return 1.0
        
        # Calculate average completion rate and perceived difficulty
        avg_completion = 0.0
        avg_difficulty = 0.0
        count = 0
        
        for metric in previous_metrics:
            completion = metric.get("completion_percentage", 100)
            difficulty = metric.get("difficulty", 5)
            avg_completion += completion
            avg_difficulty += difficulty
            count += 1
        
        if count > 0:
            avg_completion /= count
            avg_difficulty /= count
        
        # Adjust intensity based on performance
        if avg_completion >= 90 and avg_difficulty <= 4:
            # Good performance - increase intensity
            return min(1.3, 1.0 + (0.05 * (avg_completion - 90) / 10))
        elif avg_completion <= 70 or avg_difficulty >= 8:
            # Poor performance - decrease intensity
            return max(0.7, 1.0 - (0.05 * (80 - avg_completion) / 10))
        
        return 1.0
    
    async def _call_ia_api(self, profile_data: Dict[str, Any], previous_metrics: Optional[List], days_per_week: int) -> Optional[List[Dict]]:
        """
        Call external IA API for personalized workout generation.
        
        Returns:
            List of workout structures or None if API fails
        """
        if not settings.ia_api_url:
            return None
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{settings.ia_api_url}/generate-workouts",
                    json={
                        "profile": profile_data,
                        "previous_metrics": previous_metrics or [],
                        "days_per_week": days_per_week,
                        "sport": self.sport_id
                    },
                    headers={"Authorization": f"Bearer {settings.ia_api_key}"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("workouts", [])
        except Exception as e:
            # Log error but don't fail - fallback to rule-based
            logger.error(f"IA API error: {e}")
        
        return None
    
    def _generate_rule_based_workouts(
        self,
        profile_data: Dict[str, Any],
        days_per_week: int,
        week_number: int,
        total_weeks: int,
        intensity_multiplier: float
    ) -> List[Dict[str, Any]]:
        """
        Generate workouts using rule-based logic (fallback).
        
        Returns:
            List of workout structures
        """
        workouts = []
        
        # Get level for intensity
        level = profile_data.get("level", "intermediate")
        primary_goal = profile_data.get("primary_goal", "general_fitness")
        
        # Level base intensity mapping
        level_intensity = {
            "beginner": 0.6,
            "intermediate": 0.8,
            "advanced": 1.0,
            "elite": 1.2
        }.get(level, 0.8)
        
        # Week focus based on periodization
        progress = week_number / total_weeks
        week_focus = "build"
        if progress <= 0.7:
            week_focus = "build"
        elif progress <= 0.9:
            week_focus = "peak"
        else:
            week_focus = "taper"
        
        # Workout type patterns for different focuses
        patterns = {
            "build": ["endurance", "strength", "endurance", "strength", "endurance", "recovery", "long"],
            "peak": ["speed", "strength", "speed", "strength", "speed", "recovery", "long"],
            "taper": ["easy", "easy", "moderate", "easy", "easy", "recovery", "rest"]
        }
        
        pattern = patterns.get(week_focus, patterns["build"])
        
        for day in range(1, days_per_week + 1):
            workout_type = pattern[(day - 1) % len(pattern)]
            
            # Calculate duration based on workout type and intensity
            duration_map = {
                "endurance": 45,
                "strength": 40,
                "speed": 35,
                "long": 60,
                "recovery": 30,
                "easy": 30,
                "moderate": 40
            }
            
            base_duration = duration_map.get(workout_type, 45)
            duration = int(base_duration * level_intensity * intensity_multiplier)
            
            # Build workout structure
            workout = {
                "name": f"{workout_type.capitalize()} Training",
                "description": f"Week {week_number} - {workout_type} focus",
                "sport_id": self.sport_id,
                "duration_minutes": duration,
                "blocks": self._get_blocks_for_workout_type(workout_type, duration, intensity_multiplier)
            }
            
            workouts.append(workout)
        
        return workouts
    
    def _get_blocks_for_workout_type(self, workout_type: str, duration: int, intensity: float) -> List[Dict]:
        """
        Get block structure for a specific workout type.
        
        Returns:
            List of block dictionaries
        """
        # Common warmup and cooldown
        warmup = {
            "block_type": "warmup",
            "duration_minutes": max(5, int(10 * intensity)),
            "intensity": "easy",
            "instructions": "Dynamic stretching and light cardio"
        }
        
        cooldown = {
            "block_type": "cooldown",
            "duration_minutes": max(5, int(10 * intensity)),
            "intensity": "easy",
            "instructions": "Static stretching and breathing"
        }
        
        main_duration = duration - warmup["duration_minutes"] - cooldown["duration_minutes"]
        
        # Main block based on workout type
        main_blocks = {
            "endurance": {
                "block_type": "main",
                "duration_minutes": main_duration,
                "intensity": "moderate",
                "instructions": "Maintain steady pace throughout"
            },
            "strength": {
                "block_type": "main",
                "duration_minutes": main_duration,
                "intensity": "hard",
                "instructions": "Focus on proper form. Rest between sets."
            },
            "speed": {
                "block_type": "main",
                "duration_minutes": main_duration,
                "intensity": "max",
                "instructions": "High intensity intervals with recovery"
            },
            "long": {
                "block_type": "main",
                "duration_minutes": main_duration,
                "intensity": "easy",
                "instructions": "Long steady effort at conversation pace"
            },
            "recovery": {
                "block_type": "main",
                "duration_minutes": main_duration,
                "intensity": "easy",
                "instructions": "Very easy effort. Focus on recovery."
            }
        }
        
        main_block = main_blocks.get(workout_type, main_blocks["endurance"])
        
        return [warmup, main_block, cooldown]
    
    def _get_week_focus(self, week_number: int, total_weeks: int) -> str:
        """Determine training focus for a given week."""
        progress = week_number / total_weeks
        
        if progress <= 0.7:
            return "build"
        elif progress <= 0.9:
            return "peak"
        else:
            return "taper"

    def _get_profile_id(self) -> str:
        """Get athlete profile ID."""
        from app.infra.db.models.athlete import AthleteProfile

        profile = self.db.query(AthleteProfile).filter_by(
            user_id=self.user_id
        ).first()

        if not profile:
            raise ValidationError("Athlete profile not found")

        return str(profile.id)
