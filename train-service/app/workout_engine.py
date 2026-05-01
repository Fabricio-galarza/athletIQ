"""
Workout generation engine with rule-based logic.
Supports multiple sports (Running, CrossFit, Functional, etc.)
Fase 1: Simulates IA without external API calls.
"""

import random
import logging
import uuid
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


# ============================================
# MULTISPORT EXERCISES DATABASE
# ============================================

SPORT_EXERCISES = {
    "running": {
        "cardio": [
            {"id": "run_easy", "name": "Easy Run", "difficulty": 2, "type": "endurance"},
            {"id": "run_long", "name": "Long Run", "difficulty": 3, "type": "endurance"},
            {"id": "run_tempo", "name": "Tempo Run", "difficulty": 3, "type": "speed"},
            {"id": "run_intervals", "name": "Intervalos", "difficulty": 4, "type": "speed"},
            {"id": "run_fartlek", "name": "Fartlek", "difficulty": 3, "type": "speed"},
            {"id": "run_hill", "name": "Hill Training", "difficulty": 4, "type": "strength"},
            {"id": "run_progressive", "name": "Progresivo", "difficulty": 3, "type": "speed"},
            {"id": "run_recovery", "name": "Recovery Run", "difficulty": 1, "type": "recovery"},
        ],
        "strength": [
            {"id": "str_squats", "name": "Sentadillas", "difficulty": 3, "type": "strength"},
            {"id": "str_lunges", "name": "Zancadas", "difficulty": 2, "type": "strength"},
            {"id": "str_deadlifts", "name": "Peso Muerto", "difficulty": 4, "type": "strength"},
            {"id": "str_planks", "name": "Plancha", "difficulty": 2, "type": "core"},
            {"id": "str_glute_bridge", "name": "Puente de Glúteos", "difficulty": 2, "type": "strength"},
        ],
        "mobility": [
            {"id": "mob_dynamic", "name": "Movilidad Dinámica", "difficulty": 1, "type": "mobility"},
            {"id": "mob_stretching", "name": "Estiramientos", "difficulty": 1, "type": "mobility"},
            {"id": "mob_foam_roller", "name": "Foam Rolling", "difficulty": 1, "type": "recovery"},
        ]
    },
    
    "crossfit": {
        "wod": [
            {"id": "cf_amrap", "name": "AMRAP", "difficulty": 4, "type": "conditioning"},
            {"id": "cf_emom", "name": "EMOM", "difficulty": 3, "type": "conditioning"},
            {"id": "cf_for_time", "name": "For Time", "difficulty": 4, "type": "conditioning"},
            {"id": "cf_tabata", "name": "Tabata", "difficulty": 4, "type": "hiit"},
            {"id": "cf_chipper", "name": "Chipper", "difficulty": 5, "type": "endurance"},
            {"id": "cf_metcon", "name": "MetCon", "difficulty": 4, "type": "conditioning"},
        ],
        "strength": [
            {"id": "str_snatch", "name": "Snatch", "difficulty": 5, "type": "oly_lifting"},
            {"id": "str_cj", "name": "Clean & Jerk", "difficulty": 5, "type": "oly_lifting"},
            {"id": "str_squat", "name": "Back Squat", "difficulty": 3, "type": "strength"},
            {"id": "str_deadlift", "name": "Deadlift", "difficulty": 3, "type": "strength"},
        ],
        "gymnastics": [
            {"id": "gym_pullups", "name": "Pull-ups", "difficulty": 4, "type": "gymnastics"},
            {"id": "gym_muscle_up", "name": "Muscle-up", "difficulty": 5, "type": "gymnastics"},
            {"id": "gym_hspu", "name": "Handstand Push-up", "difficulty": 5, "type": "gymnastics"},
            {"id": "gym_rope", "name": "Rope Climb", "difficulty": 4, "type": "gymnastics"},
        ]
    },
    
    "functional": {
        "circuits": [
            {"id": "func_circuit", "name": "Circuito Funcional", "difficulty": 3, "type": "circuit"},
            {"id": "func_hirt", "name": "HIIT", "difficulty": 4, "type": "hiit"},
            {"id": "func_interval", "name": "Intervalos", "difficulty": 3, "type": "interval"},
        ],
        "strength": [
            {"id": "func_kettlebell", "name": "Kettlebell Swings", "difficulty": 3, "type": "strength"},
            {"id": "func_medball", "name": "Medicine Ball", "difficulty": 2, "type": "strength"},
            {"id": "func_bands", "name": "Band Work", "difficulty": 2, "type": "strength"},
        ],
        "mobility": [
            {"id": "func_yoga", "name": "Yoga Flow", "difficulty": 2, "type": "mobility"},
            {"id": "func_balance", "name": "Balance", "difficulty": 2, "type": "mobility"},
        ]
    },
    
    "swimming": {
        "cardio": [
            {"id": "swim_freestyle", "name": "Libre Continuo", "difficulty": 3, "type": "endurance"},
            {"id": "swim_intervals", "name": "Intervalos", "difficulty": 4, "type": "speed"},
            {"id": "swim_drills", "name": "Técnica", "difficulty": 2, "type": "technique"},
        ],
        "drills": [
            {"id": "swim_kick", "name": "Patada con Tabla", "difficulty": 2, "type": "drill"},
            {"id": "swim_pull", "name": "Pull Buoy", "difficulty": 2, "type": "drill"},
        ]
    },
    
    "cycling": {
        "cardio": [
            {"id": "bike_endurance", "name": "Endurance Ride", "difficulty": 3, "type": "endurance"},
            {"id": "bike_intervals", "name": "Intervalos", "difficulty": 4, "type": "speed"},
            {"id": "bike_climb", "name": "Subidas", "difficulty": 4, "type": "strength"},
        ]
    }
}


# Level configurations for intensity and volume
LEVEL_CONFIG = {
    "beginner": {"volume_multiplier": 0.6, "intensity": "low", "max_duration": 30},
    "intermediate": {"volume_multiplier": 0.8, "intensity": "moderate", "max_duration": 45},
    "advanced": {"volume_multiplier": 1.0, "intensity": "high", "max_duration": 60},
    "elite": {"volume_multiplier": 1.2, "intensity": "very_high", "max_duration": 90},
}

# Goal configurations per sport
SPORT_GOAL_MAPPING = {
    "running": {
        "increase_speed": {"focus": "speed", "ratio": {"speed": 0.6, "endurance": 0.3, "recovery": 0.1}},
        "improve_endurance": {"focus": "endurance", "ratio": {"speed": 0.2, "endurance": 0.7, "recovery": 0.1}},
        "weight_loss": {"focus": "cardio", "ratio": {"speed": 0.3, "endurance": 0.5, "recovery": 0.2}},
        "competition": {"focus": "performance", "ratio": {"speed": 0.5, "endurance": 0.4, "recovery": 0.1}},
        "general_fitness": {"focus": "balanced", "ratio": {"speed": 0.3, "endurance": 0.3, "recovery": 0.4}},
    },
    "crossfit": {
        "increase_speed": {"focus": "metcon", "ratio": {"conditioning": 0.6, "strength": 0.3, "skill": 0.1}},
        "improve_endurance": {"focus": "engine", "ratio": {"conditioning": 0.5, "strength": 0.2, "skill": 0.3}},
        "weight_loss": {"focus": "metcon", "ratio": {"conditioning": 0.6, "strength": 0.2, "skill": 0.2}},
        "general_fitness": {"focus": "balanced", "ratio": {"conditioning": 0.4, "strength": 0.4, "skill": 0.2}},
    },
    "functional": {
        "increase_speed": {"focus": "power", "ratio": {"hiit": 0.5, "strength": 0.3, "mobility": 0.2}},
        "improve_endurance": {"focus": "aerobic", "ratio": {"circuit": 0.5, "strength": 0.3, "mobility": 0.2}},
        "general_fitness": {"focus": "balanced", "ratio": {"circuit": 0.4, "strength": 0.3, "mobility": 0.3}},
    },
    "swimming": {
        "increase_speed": {"focus": "technique", "ratio": {"speed": 0.5, "endurance": 0.3, "technique": 0.2}},
        "improve_endurance": {"focus": "distance", "ratio": {"endurance": 0.7, "speed": 0.2, "technique": 0.1}},
        "general_fitness": {"focus": "balanced", "ratio": {"endurance": 0.4, "technique": 0.3, "speed": 0.3}},
    },
    "cycling": {
        "increase_speed": {"focus": "power", "ratio": {"speed": 0.6, "endurance": 0.3, "recovery": 0.1}},
        "improve_endurance": {"focus": "distance", "ratio": {"endurance": 0.7, "speed": 0.2, "recovery": 0.1}},
        "general_fitness": {"focus": "balanced", "ratio": {"endurance": 0.5, "speed": 0.3, "recovery": 0.2}},
    },
}


class WorkoutEngine:
    """
    Multi-sport workout generation engine.
    Rule-based, no external API calls (Fase 1).
    """
    
    def __init__(self):
        self.exercises = SPORT_EXERCISES
        self.level_config = LEVEL_CONFIG
        self.goal_mapping = SPORT_GOAL_MAPPING
    
    def generate_plan(
        self,
        sport: str,
        goal: str,
        level: str,
        days_per_week: int,
        duration_minutes: int,
        available_equipment: List[str] = None,
        injuries: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a weekly workout plan for any sport.
        """
        # Normalize inputs
        sport = sport.lower()
        level = level.lower()
        
        # Validate sport exists
        if sport not in self.exercises:
            raise ValueError(f"Sport '{sport}' not supported. Available: {list(self.exercises.keys())}")
        
        # Get configuration
        level_cfg = self.level_config.get(level, self.level_config["intermediate"])
        sport_goal = self.goal_mapping.get(sport, {}).get(goal, {
            "focus": "balanced",
            "ratio": {"endurance": 0.4, "speed": 0.3, "recovery": 0.3}
        })
        
        # Calculate sessions per week
        sessions = self._generate_weekly_sessions(
            sport=sport,
            days=days_per_week,
            level_cfg=level_cfg,
            goal_cfg=sport_goal,
            duration=duration_minutes,
        )
        
        return {
            "plan_id": self._generate_plan_id(),
            "sport": sport,
            "goal": goal,
            "level": level,
            "days_per_week": days_per_week,
            "duration_minutes": duration_minutes,
            "weekly_plan": sessions,
            "created_at": datetime.now().isoformat(),
        }
    
    def _generate_weekly_sessions(
        self,
        sport: str,
        days: int,
        level_cfg: Dict,
        goal_cfg: Dict,
        duration: int,
    ) -> Dict[str, Any]:
        """
        Generate daily sessions for the week.
        """
        weekly = {}
        sport_exercises = self.exercises.get(sport, {})
        
        # Distribute session types based on goal ratio
        session_types = []
        for session_type, ratio in goal_cfg.get("ratio", {}).items():
            count = max(1, int(days * ratio))
            session_types.extend([session_type] * count)
        
        # Trim to exact days
        session_types = session_types[:days]
        
        # If not enough sessions, pad with "balanced"
        while len(session_types) < days:
            session_types.append("balanced")
        
        # Shuffle for variety
        random.shuffle(session_types)
        
        for day in range(1, days + 1):
            session_type = session_types[day - 1]
            
            # Get exercises for this session type
            exercises = self._get_exercises_for_session(
                sport_exercises, session_type, level_cfg
            )
            
            # Adjust duration based on level
            adjusted_duration = int(duration * level_cfg["volume_multiplier"])
            
            weekly[f"day_{day}"] = {
                "session_type": session_type,
                "exercises": exercises,
                "estimated_duration": adjusted_duration,
                "notes": self._get_session_notes(sport, session_type, level_cfg["intensity"]),
            }
        
        return weekly
    
    def _get_exercises_for_session(
        self,
        sport_exercises: Dict,
        session_type: str,
        level_cfg: Dict,
    ) -> List[Dict]:
        """
        Get appropriate exercises for a session type.
        """
        exercises = []
        
        # Map session type to exercise categories
        category_mapping = {
            "speed": ["cardio", "wod", "speed"],
            "endurance": ["cardio", "endurance", "distance"],
            "strength": ["strength", "power", "wod"],
            "conditioning": ["wod", "metcon", "conditioning"],
            "skill": ["gymnastics", "technique", "drills"],
            "recovery": ["mobility", "recovery", "stretching"],
            "balanced": ["cardio", "strength", "mobility"],
            "hiit": ["hiit", "interval", "circuit"],
            "technique": ["technique", "drills", "mobility"],
        }
        
        categories = category_mapping.get(session_type, ["cardio", "strength"])
        
        for category in categories:
            for cat_key in sport_exercises.keys():
                if category in cat_key.lower() or cat_key.lower() in category:
                    ex_list = sport_exercises.get(cat_key, [])
                    if ex_list:
                        exercise = random.choice(ex_list).copy()
                        
                        # Adjust based on level
                        exercise["sets"] = self._calculate_sets(level_cfg)
                        exercise["reps_or_duration"] = self._calculate_duration(level_cfg, exercise.get("type", ""))
                        
                        exercises.append(exercise)
                        break
            
            if len(exercises) >= 3:
                break
        
        return exercises[:4]  # Max 4 exercises per session
    
    def _calculate_sets(self, level_cfg: Dict) -> int:
        """Calculate number of sets based on level."""
        base_sets = 3
        multiplier = level_cfg["volume_multiplier"]
        return max(1, int(base_sets * multiplier))
    
    def _calculate_duration(self, level_cfg: Dict, exercise_type: str) -> str:
        """Calculate duration based on level and exercise type."""
        base = {
            "endurance": 20,
            "speed": 15,
            "strength": 12,
            "hiit": 10,
        }.get(exercise_type, 15)
        
        adjusted = int(base * level_cfg["volume_multiplier"])
        return f"{adjusted} min"
    
    def _get_session_notes(self, sport: str, session_type: str, intensity: str) -> str:
        """Get session-specific notes."""
        notes = {
            "running": {
                "speed": "Mantén un ritmo sostenido. Escucha a tu cuerpo.",
                "endurance": "Paso cómodo. Concéntrate en la respiración.",
                "recovery": "Ritmo muy suave. Debes poder hablar mientras corres.",
            },
            "crossfit": {
                "conditioning": "Mantén técnica limpia. No sacrifiques forma por tiempo.",
                "strength": "Progresión gradual. Calienta bien antes de pesos pesados.",
                "skill": "Practica la técnica. Usa progresiones si es necesario.",
            },
        }
        
        sport_notes = notes.get(sport, {})
        return sport_notes.get(session_type, f"Intensidad: {intensity}. Escucha a tu cuerpo.")
    
    def adapt_plan(
        self,
        current_plan: Dict[str, Any],
        feedback: Dict[str, Any],
        completion_percentage: float,
    ) -> Dict[str, Any]:
        """
        Adapt plan based on feedback and performance.
        """
        adapted = current_plan.copy()
        
        # Get feedback metrics
        difficulty = feedback.get("difficulty", 5)
        has_pain = feedback.get("pain_reported", False)
        enjoyment = feedback.get("enjoyment", 3)
        
        # Rule 1: Pain management
        if has_pain:
            adapted["adjustments"] = ["Pain reported - replacing impact exercises"]
            adapted["weekly_plan"] = self._reduce_impact(adapted["weekly_plan"])
        
        # Rule 2: Progression based on completion
        if completion_percentage >= 90 and difficulty <= 5 and enjoyment >= 4:
            adapted["volume_multiplier"] = 1.1
            adapted["adjustments"] = ["Good performance - increasing volume"]
        elif completion_percentage <= 70 or difficulty >= 8:
            adapted["volume_multiplier"] = 0.85
            adapted["adjustments"] = ["Low completion or high difficulty - reducing volume"]
        else:
            adapted["volume_multiplier"] = 1.0
        
        adapted["adapted_at"] = datetime.now().isoformat()
        adapted["previous_plan_id"] = current_plan.get("plan_id")
        
        return adapted
    
    def _reduce_impact(self, weekly_plan: Dict) -> Dict:
        """Replace high-impact exercises with low-impact alternatives."""
        low_impact_sports = {
            "walking", "swimming", "cycling", "elliptical"
        }
        
        for day, session in weekly_plan.items():
            for exercise in session.get("exercises", []):
                # Replace running with walking or cycling
                if "run" in exercise.get("id", ""):
                    exercise["id"] = "walking"
                    exercise["name"] = "Caminata"
                    exercise["notes"] = "Ejercicio de bajo impacto (reemplazo por dolor)"
        
        return weekly_plan
    
    def get_exercises(
        self,
        sport: Optional[str] = None,
        exercise_type: Optional[str] = None,
        difficulty: Optional[int] = None,
    ) -> List[Dict]:
        """
        Get filtered list of exercises by sport and criteria.
        """
        results = []
        
        sports_to_search = [sport] if sport else self.exercises.keys()
        
        for s in sports_to_search:
            for category, ex_list in self.exercises.get(s, {}).items():
                for ex in ex_list:
                    ex_with_sport = ex.copy()
                    ex_with_sport["sport"] = s
                    ex_with_sport["category"] = category
                    
                    if exercise_type and ex.get("type") != exercise_type:
                        continue
                    if difficulty and ex.get("difficulty") != difficulty:
                        continue
                    
                    results.append(ex_with_sport)
        
        return results
    
    def _generate_plan_id(self) -> str:
        """Generate unique plan ID."""
        return f"plan_{uuid.uuid4().hex[:8]}"