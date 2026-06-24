"""
API endpoints for training plan generation (CU-TRAIN-04)
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.context import RequireAthlete, RequireCoach, UserContext
from app.core.exceptions import ValidationError
from app.infra.db.session import get_db
from app.schemas.plan import PlanGenerationRequest, PlanGenerationResponse
from app.services.plan_generator import PlanGenerator
from app.services.plan_matcher import PlanMatcher
from app.services.ia_workout_generator import IAWorkoutGenerator
from app.infra.db.models.plan import TrainingPlan, TrainingPlanPhase, TrainingPlanSession
from app.infra.db.models.session import TrainingSession
from app.infra.db.models.athlete import AthleteProfile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plans", tags=["Plans"])


@router.post(
    "/generate",
    response_model=PlanGenerationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate training plan",
    description="CU-TRAIN-04: Generate a training plan for an athlete"
)
async def generate_training_plan(
    request: PlanGenerationRequest,
    context: UserContext = Depends(RequireAthlete),
    db: Session = Depends(get_db),
):
    """
    Generate a training plan based on athlete profile.
    
    Flow:
    1. Validate profile completeness
    2. Check for reusable plans (if not forced to regenerate)
    3. If reuse possible, clone and assign existing plan
    4. If not, generate new plan
    5. For generic plans: generate all sessions upfront
    6. For adaptive plans: create structure + first week only
    """
    # Validate sport exists in user's sports
    if request.sport_id not in context.sports:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Sport '{request.sport_id}' is not configured for this user"
        )
    
    # Check feature availability based on plan type
    is_premium = context.has_feature("adaptive_training")
    
    if request.plan_type == "adaptive" and not is_premium:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Adaptive training feature not available in your plan"
        )
    
    # Initialize services
    plan_generator = PlanGenerator(db, context.user_id, request.sport_id, context)
    plan_matcher = PlanMatcher(db, context.user_id, request.sport_id, context)
    
    # Step 1: Get athlete profile data
    try:
        profile_data = plan_generator._get_athlete_profile_data()
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    # Step 2: Check if profile is complete
    if not plan_generator._is_profile_complete(profile_data):
        return PlanGenerationResponse(
            success=False,
            plan_id=None, 
            plan_type=request.plan_type,
            is_new_plan=False,
            message="Profile incomplete. Please complete your profile before generating a plan.",
            sessions_created=0,
            total_weeks=0
        )
    
    # Step 3: Try to reuse existing plan (unless forced to regenerate)
    plan = None
    is_new_plan = True
    reused_from = None
    
    if not request.force_regenerate and request.plan_type == "generic":
        can_reuse, existing_plan, reason = plan_matcher.can_reuse_plan(profile_data)
        
        if can_reuse and existing_plan:
            # Clone the existing plan for this athlete
            profile_id = plan_generator._get_profile_id()
            plan, sessions_created = plan_matcher.clone_plan(existing_plan, profile_id)
            is_new_plan = False
            reused_from = existing_plan.id

            logger.info(f"Reused plan {existing_plan.id} for user {context.user_id}")

            return PlanGenerationResponse(
                success=True,
                plan_id=plan.id,
                plan_type=plan.plan_type,
                is_new_plan=is_new_plan,
                reused_from_plan_id=reused_from,
                message=f"Plan reused from existing template. {reason}",
                sessions_created=sessions_created,
                total_weeks=plan.duration_weeks
            )
    
    # Step 4: Generate new plan
    try:
        if request.plan_type == "generic":
            # Generate complete plan with all sessions
            plan, sessions = plan_generator.generate_generic_plan()
            
            return PlanGenerationResponse(
                success=True,
                plan_id=plan.id,
                plan_type=plan.plan_type,
                is_new_plan=True,
                message=f"Generic plan generated for {request.sport_id}",
                sessions_created=len(sessions),
                total_weeks=plan.duration_weeks
            )
        
        else:
            # Adaptive plan: create structure only (first session generated later)
            plan = plan_generator.generate_adaptive_plan_structure()
            
            # Generate first week's sessions
            ia_generator = IAWorkoutGenerator(db, context.user_id, request.sport_id)
            
            # Get previous metrics (empty for first week)
            previous_metrics = []
            
            # Generate first week
            sessions = await ia_generator.generate_next_week(
                plan_id=str(plan.id),
                profile_data=profile_data,
                previous_metrics=previous_metrics
            )
            
            return PlanGenerationResponse(
                success=True,
                plan_id=plan.id,
                plan_type=plan.plan_type,
                is_new_plan=True,
                message=f"Adaptive plan structure created. First week generated.",
                sessions_created=len(sessions),
                total_weeks=plan.duration_weeks
            )
    
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Plan generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate plan: {str(e)}"
        )


@router.get(
    "/active",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get active training plan",
    description="Get the currently active training plan for a sport"
)
async def get_active_plan(
    sport_id: str,
    context: UserContext = Depends(RequireAthlete),
    db: Session = Depends(get_db),
):
    """
    Get the active training plan for a specific sport.
    """
    # Get athlete profile
    profile = db.query(AthleteProfile).filter_by(
        user_id=context.user_id
    ).first()
    
    if not profile:
        return {"has_active_plan": False, "plan": None}
    
    # Find active plan
    plan = db.query(TrainingPlan).filter_by(
        profile_id=profile.id,
        sport_id=sport_id,
        is_active=True
    ).first()
    
    if not plan:
        return {"has_active_plan": False, "plan": None}
    
    # Count sessions in plan
    session_count = db.query(TrainingPlanSession).filter_by(
        plan_id=plan.id
    ).count()
    
    return {
        "has_active_plan": True,
        "plan": {
            "id": str(plan.id),
            "name": plan.name,
            "plan_type": plan.plan_type,
            "start_date": plan.start_date.isoformat() if plan.start_date else None,
            "end_date": plan.end_date.isoformat() if plan.end_date else None,
            "duration_weeks": plan.duration_weeks,
            "total_sessions": session_count,
            "source": plan.source
        }
    }


@router.get(
    "/{plan_id}/schedule",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get plan schedule",
    description="Get the complete schedule for a training plan"
)
async def get_plan_schedule(
    plan_id: str,
    context: UserContext = Depends(RequireAthlete),
    db: Session = Depends(get_db),
):
    """
    Get the complete schedule (phases and sessions) for a training plan.
    """
    # Verify plan belongs to user
    profile = db.query(AthleteProfile).filter_by(
        user_id=context.user_id
    ).first()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Athlete profile not found")
    
    plan = db.query(TrainingPlan).filter_by(
        id=plan_id,
        profile_id=profile.id
    ).first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    # Get phases with their sessions
    phases = db.query(TrainingPlanPhase).filter_by(
        plan_id=plan.id
    ).order_by(TrainingPlanPhase.week_number).all()
    
    schedule = []
    for phase in phases:
        plan_sessions = db.query(TrainingPlanSession).filter_by(
            phase_id=phase.id
        ).order_by(TrainingPlanSession.day_number).all()
        
        sessions_data = []
        for ps in plan_sessions:
            session = db.query(TrainingSession).filter_by(
                id=ps.session_id
            ).first()
            
            if session:
                sessions_data.append({
                    "session_id": str(session.id),
                    "day_number": ps.day_number,
                    "scheduled_date": ps.scheduled_date.isoformat() if ps.scheduled_date else None,
                    "duration_minutes": session.planned_duration_minutes,
                    "status": session.status
                })
        
        schedule.append({
            "week_number": phase.week_number,
            "name": phase.name,
            "focus": phase.focus,
            "start_date": phase.start_date.isoformat() if phase.start_date else None,
            "end_date": phase.end_date.isoformat() if phase.end_date else None,
            "sessions": sessions_data
        })
    
    return {
        "plan_id": str(plan.id),
        "plan_name": plan.name,
        "plan_type": plan.plan_type,
        "total_weeks": len(phases),
        "schedule": schedule
    }