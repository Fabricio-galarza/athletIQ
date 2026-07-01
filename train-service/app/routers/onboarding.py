"""
CU-TRAIN-01-HU-05 + HU-06: Evaluate and automatically create test session if needed.
"""
from datetime import date
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.context import RequireAthlete, UserContext
from app.infra.db.session import get_db
from app.services.sufficiency_service import SufficiencyService

router = APIRouter(prefix="/onboarding", tags=["Onboarding"])


@router.get("/status", status_code=status.HTTP_200_OK)
async def get_onboarding_status(
    sport_id: str,
    context: UserContext = Depends(RequireAthlete),
    db: Session = Depends(get_db),
):
    """
    HU-05 + HU-06: Evaluate and automatically create test session if needed.
    
    If athlete lacks sufficient data:
    - Finds appropriate test template
    - Creates training_session (source='test')
    - Creates training_session_block entries with all fields
    - Returns session info
    """
    # Step 1: Evaluate data sufficiency
    service = SufficiencyService(db, context.user_id, sport_id, context)
    evaluation = service.evaluate()
    
    test_session = None
    
    # Step 2: If test needed and template exists, create session
    if evaluation["requires_test"] and evaluation.get("test_template"):
        template = evaluation["test_template"]
        
        # Get athlete profile
        profile_query = text("""
            SELECT id FROM train.athlete_profile WHERE user_id = :user_id
        """)
        profile_result = db.execute(profile_query, {"user_id": context.user_id}).first()
        
        if not profile_result:
            return {
                "success": False,
                "message": "Athlete profile not found",
                **evaluation
            }
        
        profile_id = profile_result[0]
        
        # Create training session
        session_query = text("""
            INSERT INTO train.training_session (
                id, profile_id, sport_id, status, source, 
                planned_date, planned_duration_minutes, created_at
            ) VALUES (
                gen_random_uuid(), :profile_id, :sport_id, 'planned', 'test',
                :planned_date, :duration_minutes, NOW()
            )
            RETURNING id, planned_duration_minutes
        """)
        
        session_result = db.execute(session_query, {
            "profile_id": profile_id,
            "sport_id": sport_id,
            "planned_date": date.today(),
            "duration_minutes": template.get("duration_minutes", 20),
        }).first()
        
        session_id = session_result[0]
        
        # Create training session blocks from template with all fields
        for block in template.get("blocks", []):
            block_query = text("""
                INSERT INTO train.training_session_block (
                    id, session_id, "order", block_type, 
                    duration_minutes, intensity, instructions,
                    created_at
                ) VALUES (
                    gen_random_uuid(), :session_id, :block_order, :block_type,
                    :duration_minutes, :intensity, :instructions, NOW()
                )
            """)
            
            db.execute(block_query, {
                "session_id": session_id,
                "block_order": block.get("block_order"),
                "block_type": block.get("block_type"),
                "duration_minutes": block.get("duration_minutes"),
                "intensity": block.get("intensity"),
                "instructions": block.get("instructions"),
            })
        
        db.commit()
        
        test_session = {
            "session_id": str(session_id),
            "status": "planned",
            "source": "test",
            "planned_duration_minutes": session_result[1],
            "template_used": template.get("code"),
            "blocks": template.get("blocks", []),
        }
    
    return {
        "has_sufficient_data": evaluation["has_sufficient_data"],
        "missing_required_fields": evaluation["missing_required_fields"],
        "completion_score": evaluation["completion_score"],
        "requires_test": evaluation["requires_test"],
        "total_required_fields": evaluation.get("total_required_fields", 0),
        "completed_required_fields": evaluation.get("completed_required_fields", 0),
        "test_created": test_session is not None,
        "test_session": test_session,
        "next_step": "complete_test" if evaluation["requires_test"] else "ready_for_plan"
    }