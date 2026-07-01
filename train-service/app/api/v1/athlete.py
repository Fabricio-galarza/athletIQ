"""
API endpoints for athlete profile management (CU-TRAIN-01)
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.core.context import RequireAthlete, UserContext
from app.core.exceptions import ValidationError, NotFoundError
from app.infra.db.session import get_db
from app.schemas.athlete import (
    SportProfileCreate, 
    SportProfileResponse,
    SportProfileUpdate,
    SportProfileUpdateResponse
)
from app.services.athlete_service import AthleteService

router = APIRouter(prefix="/athlete", tags=["Athlete"])


@router.post(
    "/sport-profile",
    response_model=SportProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create athlete sport profile",
)
async def create_sport_profile(
    data: SportProfileCreate,
    db: Session = Depends(get_db),
    context: UserContext = Depends(RequireAthlete),
):
    """Create or update complete sport profile for authenticated athlete."""
    sport_name = data.sport_id
    if sport_name not in context.sports:
        raise ValidationError(f"Sport '{sport_name}' is not configured for this user")
    
    profile_data = data.form_data.get("athlete_profile", {})
    health_data = data.form_data.get("athlete_health_profile", {})
    training_structure_data = data.form_data.get("athlete_training_structure", {})
    goal_data = data.form_data.get("athlete_goal", {})
    
    service = AthleteService(db, context.user_id)
    
    profile_id, sport_profile_id, has_sufficient_data, missing_fields = await service.create_sport_profile(
        sport_id=sport_name,
        profile_data=profile_data,
        health_data=health_data,
        training_structure_data=training_structure_data,
        goal_data=goal_data,
        context=context,
    )
    
    return SportProfileResponse(
        message="Sport profile created successfully",
        profile_id=profile_id,
        sport_profile_id=sport_profile_id,
        has_sufficient_data=has_sufficient_data,
        requires_test=not has_sufficient_data,
        missing_fields=missing_fields,
    )


@router.get(
    "/profile/{sport_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get athlete profile",
)
async def get_athlete_profile(
    sport_id: str,
    context: UserContext = Depends(RequireAthlete),
    db: Session = Depends(get_db),
):
    """Get complete athlete profile for a specific sport."""
    service = AthleteService(db, context.user_id)
    
    try:
        profile = service.get_complete_profile(sport_id)
        return profile
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/sports",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get athlete sports",
)
async def get_athlete_sports(
    context: UserContext = Depends(RequireAthlete),
    db: Session = Depends(get_db),
):
    """Get all sports configured for the athlete."""
    service = AthleteService(db, context.user_id)
    sports = service.get_athlete_sports()
    return {"sports": sports}


@router.get(
    "/me",
    response_model=None,
    summary="Get current user context",
)
async def get_current_user(
    context: UserContext = Depends(RequireAthlete)
):
    """Return current user context for debugging."""
    return context.to_dict()


@router.patch(
    "/sport-profile/{sport_id}",
    response_model=SportProfileUpdateResponse,
    status_code=status.HTTP_200_OK,
    summary="Update athlete sport profile",
)
async def update_sport_profile(
    sport_id: str,
    data: SportProfileUpdate,
    context: UserContext = Depends(RequireAthlete),
    db: Session = Depends(get_db),
):
    """
    Update specific fields of an athlete's sport profile.
    
    All fields are optional. Only provided fields will be updated.
    Useful for adding missing fields like age_range and gender.
    """
    if sport_id not in context.sports:
        raise ValidationError(f"Sport '{sport_id}' is not configured for this user")
    
    service = AthleteService(db, context.user_id)
    
    profile_id, sport_profile_id, updated_fields, has_sufficient_data = service.update_sport_profile(
        sport_id=sport_id,
        form_data=data.form_data,
        context=context,
    )
    
    return SportProfileUpdateResponse(
        message="Sport profile updated successfully",
        profile_id=profile_id,
        sport_profile_id=sport_profile_id,
        updated_fields=updated_fields,
        has_sufficient_data=has_sufficient_data,
        requires_test=not has_sufficient_data,
    )

# app/api/v1/athlete.py - Modificar el endpoint get_goal_history

@router.get(
    "/goals/{sport_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get goal history",
)
async def get_goal_history(
    sport_id: str,
    context: UserContext = Depends(RequireAthlete),
    db: Session = Depends(get_db),
):
    """
    Get all goals for a specific sport.
    Returns both active and inactive goals ordered by creation date.
    """
    service = AthleteService(db, context.user_id)
    goals = service.get_goal_history(sport_id, context)  # 🔥 Pasar context
    
    return {
        "sport_id": sport_id,
        "total_goals": len(goals),
        "active_goal": next((g for g in goals if g["is_active"]), None),
        "goals": goals
    }

@router.put(
    "/goal/{goal_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Update a specific goal",
    description="Update a goal by its ID. Only provided fields will be updated."
)
async def update_goal(
    goal_id: UUID,
    data: dict,
    context: UserContext = Depends(RequireAthlete),
    db: Session = Depends(get_db),
):
    """
    Update a specific goal.
    
    Only the fields sent in the request will be updated.
    """
    service = AthleteService(db, context.user_id)
    
    try:
        result = service.update_goal(goal_id, data, context)
        return result
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post(
    "/goal",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new goal",
    description="Creates a new goal for a sport. Deactivates any previous active goal."
)
async def create_goal(
    sport_id: str,
    data: dict,
    context: UserContext = Depends(RequireAthlete),
    db: Session = Depends(get_db),
):
    """
    Create a new goal for a sport.
    
    The previous active goal for this sport will be automatically deactivated.
    """
    service = AthleteService(db, context.user_id)
    
    try:
        result = service.create_goal(sport_id, data, context)
        return result
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    

# app/api/v1/athlete.py - Modificar el endpoint get_equipment

@router.get(
    "/equipment/{sport_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get equipment",
)
async def get_equipment(
    sport_id: str,
    context: UserContext = Depends(RequireAthlete),
    db: Session = Depends(get_db),
):
    """
    Get equipment for a specific sport.
    """
    service = AthleteService(db, context.user_id)
    result = service.get_equipment(sport_id, context)  # 🔥 Pasar context
    return result

# app/api/v1/athlete.py - Agregar al final

@router.put(
    "/equipment/{sport_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Update equipment",
    description="Update equipment available for a specific sport"
)
async def update_equipment(
    sport_id: str,
    data: dict,
    context: UserContext = Depends(RequireAthlete),
    db: Session = Depends(get_db),
):
    """
    Update equipment for a specific sport.
    
    Request body example:
    {
        "equipment": ["running_shoes", "heart_rate_monitor", "dumbbells"]
    }
    """
    equipment_list = data.get("equipment", [])
    
    if not isinstance(equipment_list, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Equipment must be a list"
        )
    
    service = AthleteService(db, context.user_id)
    
    try:
        result = service.update_equipment(sport_id, equipment_list, context)
        return result
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))