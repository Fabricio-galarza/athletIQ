"""
API endpoints for workout generation and management.
TEMPORARILY WITHOUT AUTH for testing.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status

# Comentar la autenticación temporalmente
# from app.core.context import RequireAthlete, UserContext
from app.workout_engine import WorkoutEngine
from app.redis_operations import redis_ops

router = APIRouter(prefix="/workout", tags=["Workout"])

# Initialize engine
engine = WorkoutEngine()


# ============================================
# GET endpoint for testing (easy to test)
# ============================================

@router.get("/generate", status_code=status.HTTP_200_OK)
async def generate_workout_get(
    sport: str,
    goal: str,
    level: str,
    days_per_week: int,
    duration_minutes: int = 45,
):
    """
    Generate a personalized workout plan using GET method.
    Easy to test from browser or curl.
    
    Example:
    /api/v1/workout/generate?sport=running&goal=improve_endurance&level=intermediate&days_per_week=4&duration_minutes=45
    """
    # Validate inputs
    if days_per_week < 1 or days_per_week > 7:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="days_per_week must be between 1 and 7"
        )
    
    if duration_minutes < 20 or duration_minutes > 120:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="duration_minutes must be between 20 and 120"
        )
    
    # Validate sport
    valid_sports = ["running", "crossfit", "functional", "swimming", "cycling"]
    if sport.lower() not in valid_sports:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Sport must be one of: {valid_sports}"
        )
    
    # Validate goal
    valid_goals = ["increase_speed", "improve_endurance", "weight_loss", "competition", "general_fitness"]
    if goal.lower() not in valid_goals:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Goal must be one of: {valid_goals}"
        )
    
    # Validate level
    valid_levels = ["beginner", "intermediate", "advanced", "elite"]
    if level.lower() not in valid_levels:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Level must be one of: {valid_levels}"
        )
    
    try:
        # Generate plan
        plan = engine.generate_plan(
            sport=sport.lower(),
            goal=goal.lower(),
            level=level.lower(),
            days_per_week=days_per_week,
            duration_minutes=duration_minutes,
        )
        
        # Save to Redis
        plan_id = plan["plan_id"]
        await redis_ops.save_workout_plan(plan_id, plan)
        
        # Save daily workouts
        for day_key, day_workout in plan.get("weekly_plan", {}).items():
            day_num = int(day_key.split("_")[1])
            await redis_ops.save_daily_workout(plan_id, day_num, day_workout)
        
        return {
            "success": True,
            "plan_id": plan_id,
            "sport": plan["sport"],
            "goal": plan["goal"],
            "level": plan["level"],
            "days_per_week": plan["days_per_week"],
            "duration_minutes": plan["duration_minutes"],
            "weekly_plan": plan["weekly_plan"],
            "message": f"✅ Plan generado para {sport} - nivel {level}"
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating plan: {str(e)}"
        )


# ============================================
# POST endpoint (original)
# ============================================

@router.post("/generate", status_code=status.HTTP_200_OK)
async def generate_workout_post(
    sport: str,
    goal: str,
    level: str,
    days_per_week: int,
    duration_minutes: int = 45,
    available_equipment: Optional[List[str]] = None,
    injuries: Optional[List[str]] = None,
):
    """
    Generate a personalized workout plan using POST method.
    """
    # Validate inputs
    if days_per_week < 1 or days_per_week > 7:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="days_per_week must be between 1 and 7"
        )
    
    if duration_minutes < 20 or duration_minutes > 120:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="duration_minutes must be between 20 and 120"
        )
    
    try:
        # Generate plan
        plan = engine.generate_plan(
            sport=sport,
            goal=goal,
            level=level,
            days_per_week=days_per_week,
            duration_minutes=duration_minutes,
            available_equipment=available_equipment,
            injuries=injuries,
        )
        
        # Save to Redis
        plan_id = plan["plan_id"]
        await redis_ops.save_workout_plan(plan_id, plan)
        
        # Use temp user for testing
        temp_user_id = f"temp_user_{sport}"
        await redis_ops.set_active_plan(temp_user_id, plan_id)
        
        # Save user profile
        user_profile = {
            "user_id": temp_user_id,
            "sport": sport,
            "level": level,
            "goal": goal,
            "days_per_week": days_per_week,
            "active_plan_id": plan_id,
        }
        await redis_ops.save_user_profile(temp_user_id, user_profile)
        
        # Save daily workouts
        for day_key, day_workout in plan.get("weekly_plan", {}).items():
            day_num = int(day_key.split("_")[1])
            await redis_ops.save_daily_workout(plan_id, day_num, day_workout)
        
        return {
            "success": True,
            "plan_id": plan_id,
            "plan": plan,
            "message": f"Plan generado para {sport} - nivel {level}"
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating plan: {str(e)}"
        )


# ============================================
# Other endpoints
# ============================================

@router.get("/today", status_code=status.HTTP_200_OK)
async def get_today_workout(
    user_id: str = "temp_user_running",
):
    """
    Get today's scheduled workout.
    """
    workout = await redis_ops.get_today_workout(user_id)
    
    if not workout:
        profile = await redis_ops.get_user_profile(user_id)
        if not profile or not profile.get("active_plan_id"):
            return {
                "success": False,
                "message": "No hay plan activo. Genera un plan primero.",
                "workout": None,
            }
        
        return {
            "success": False,
            "message": "No hay entrenamiento programado para hoy.",
            "workout": None,
        }
    
    return {
        "success": True,
        "workout": workout,
    }


@router.get("/exercises", status_code=status.HTTP_200_OK)
async def list_exercises(
    sport: Optional[str] = None,
    exercise_type: Optional[str] = None,
    difficulty: Optional[int] = None,
):
    """
    List available exercises filtered by criteria.
    """
    exercises = engine.get_exercises(
        sport=sport,
        exercise_type=exercise_type,
        difficulty=difficulty,
    )
    
    return {
        "success": True,
        "count": len(exercises),
        "exercises": exercises,
    }


@router.get("/plan/{plan_id}", status_code=status.HTTP_200_OK)
async def get_workout_plan(
    plan_id: str,
):
    """
    Get a specific workout plan by ID.
    """
    plan = await redis_ops.get_workout_plan(plan_id)
    
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan {plan_id} not found"
        )
    
    return {
        "success": True,
        "plan": plan,
    }


@router.post("/feedback", status_code=status.HTTP_200_OK)
async def submit_feedback(
    plan_id: str,
    day: int,
    completed: bool,
    difficulty: int,
    enjoyment: Optional[int] = None,
    pain_reported: bool = False,
    painful_exercises: Optional[List[str]] = None,
    notes: Optional[str] = None,
):
    """
    Submit feedback for a completed workout.
    """
    if difficulty < 1 or difficulty > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="difficulty must be between 1 and 10"
        )
    
    # Get current plan
    current_plan = await redis_ops.get_workout_plan(plan_id)
    if not current_plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan {plan_id} not found"
        )
    
    # Calculate completion percentage
    daily_workout = await redis_ops.get_daily_workout(plan_id, day)
    completion_percentage = 100 if completed else 70
    
    # Save feedback
    feedback_data = {
        "plan_id": plan_id,
        "day": day,
        "completed": completed,
        "completion_percentage": completion_percentage,
        "difficulty": difficulty,
        "enjoyment": enjoyment,
        "pain_reported": pain_reported,
        "painful_exercises": painful_exercises or [],
        "notes": notes,
    }
    
    temp_user_id = f"temp_user_{current_plan.get('sport', 'unknown')}"
    await redis_ops.save_feedback(temp_user_id, plan_id, day, feedback_data)
    
    # Adapt plan if needed
    if completion_percentage <= 70 or difficulty >= 8 or pain_reported:
        adapted_plan = engine.adapt_plan(
            current_plan=current_plan,
            feedback=feedback_data,
            completion_percentage=completion_percentage,
        )
        
        new_plan_id = f"{plan_id}_v2"
        adapted_plan["plan_id"] = new_plan_id
        adapted_plan["original_plan_id"] = plan_id
        
        await redis_ops.save_workout_plan(new_plan_id, adapted_plan)
        await redis_ops.set_active_plan(temp_user_id, new_plan_id)
        
        return {
            "success": True,
            "message": "Feedback recibido. Plan adaptado generado.",
            "adaptation_applied": True,
            "new_plan_id": new_plan_id,
        }
    
    return {
        "success": True,
        "message": "Feedback recibido. Gracias por tu retroalimentación.",
        "adaptation_applied": False,
    }


@router.get("/progress", status_code=status.HTTP_200_OK)
async def get_progress(
    user_id: str = "temp_user_running",
):
    """
    Get user's progress statistics.
    """
    profile = await redis_ops.get_user_profile(user_id)
    if not profile or not profile.get("active_plan_id"):
        return {
            "success": True,
            "has_active_plan": False,
            "message": "No hay plan activo",
        }
    
    plan_id = profile["active_plan_id"]
    completion_rate = await redis_ops.calculate_completion_rate(user_id, plan_id)
    avg_difficulty = await redis_ops.get_average_difficulty(user_id, plan_id)
    
    return {
        "success": True,
        "has_active_plan": True,
        "plan_id": plan_id,
        "completion_rate": completion_rate,
        "average_difficulty": round(avg_difficulty, 1),
        "user_level": profile.get("level"),
        "sport": profile.get("sport"),
        "goal": profile.get("goal"),
    }