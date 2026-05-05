"""
CU-TRAIN-02: Training structure management endpoints.
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.context import RequireAthlete, UserContext
from app.core.exceptions import ValidationError
from app.infra.db.session import get_db
from app.infra.db.models.athlete import AthleteProfile
from app.services.athlete_service import AthleteService

router = APIRouter(prefix="/training-structure", tags=["Training Structure"])


@router.post("/{sport_id}", status_code=status.HTTP_201_CREATED)
async def create_training_structure(
    sport_id: str,
    data: dict,
    context: UserContext = Depends(RequireAthlete),
    db: Session = Depends(get_db),
):
    """
    Create a new training structure for a sport.
    Deactivates any existing active structure for this sport.
    Expected data format:
    {
        "form_data": {
            "athlete_training_structure": {
                "days_per_week": 5,
                "available_days": "monday,tuesday,wednesday,thursday,friday",
                "preferred_time": "morning",
                "equipment": ["running_shoes", "heart_rate_monitor"]
            }
        }
    }
    """
    form_data = data.get("form_data", {})
    structure_data = form_data.get("athlete_training_structure", {})
    
    if not structure_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No training structure data provided"
        )
    
    # Validate user has this sport
    if sport_id not in context.sports:
        raise ValidationError(f"Sport '{sport_id}' is not configured for this user")
    
    # Deactivate existing active structure
    profile_query = text("""
        SELECT id FROM train.athlete_profile WHERE user_id = :user_id
    """)
    profile_result = db.execute(profile_query, {"user_id": context.user_id}).first()
    
    if profile_result:
        deactivate_query = text("""
            UPDATE train.athlete_training_structure 
            SET is_active = FALSE 
            WHERE profile_id = :profile_id 
              AND sport_id = :sport_id 
              AND is_active = TRUE
        """)
        db.execute(deactivate_query, {
            "profile_id": profile_result[0],
            "sport_id": sport_id
        })
    
    # Use existing AthleteService to save
    service = AthleteService(db, context.user_id)
    
    profile_id, sport_profile_id, has_sufficient, missing = await service.create_sport_profile(
        sport_id=sport_id,
        profile_data={},
        health_data={},
        training_structure_data=structure_data,
        goal_data={},
        context=context,
    )
    
    # Get the newly created structure (the one with is_active=True)
    new_structure_query = text("""
        SELECT id FROM train.athlete_training_structure 
        WHERE profile_id = :profile_id 
          AND sport_id = :sport_id 
          AND is_active = TRUE
        ORDER BY created_at DESC
        LIMIT 1
    """)
    
    new_structure = db.execute(new_structure_query, {
        "profile_id": profile_result[0] if profile_result else profile_id,
        "sport_id": sport_id
    }).first()
    
    db.commit()
    
    return {
        "message": "Training structure created successfully",
        "structure_id": str(new_structure[0]) if new_structure else None,
        "sport_id": sport_id,
        "is_active": True,
        "previous_structures_deactivated": True
    }


@router.get("/{sport_id}")
async def get_active_training_structure(
    sport_id: str,
    context: UserContext = Depends(RequireAthlete),
    db: Session = Depends(get_db),
):
    """Get the active training structure for a sport."""
    
    # Get athlete profile
    profile = db.query(AthleteProfile).filter_by(
        user_id=context.user_id
    ).first()
    
    if not profile:
        return {
            "has_structure": False,
            "message": "No athlete profile found"
        }
    
    # Query active structure
    query = text("""
        SELECT 
            ats.id,
            ats.is_active,
            ats.created_at,
            atsv.field_id,
            atsv.value
        FROM train.athlete_training_structure ats
        LEFT JOIN train.athlete_training_structure_value atsv ON atsv.structure_id = ats.id
        WHERE ats.profile_id = :profile_id
          AND ats.sport_id = :sport_id
          AND ats.is_active = TRUE
    """)
    
    result = db.execute(query, {
        "profile_id": profile.id,
        "sport_id": sport_id
    }).fetchall()
    
    if not result:
        return {
            "has_structure": False,
            "message": "No active training structure found for this sport"
        }
    
    # Build response
    structure_id = result[0][0]
    values = {}
    for row in result:
        if row[3]:  # field_id
            values[str(row[3])] = row[4]
    
    return {
        "has_structure": True,
        "structure_id": str(structure_id),
        "sport_id": sport_id,
        "is_active": True,
        "created_at": result[0][2].isoformat() if result[0][2] else None,
        "values": values
    }


@router.put("/{sport_id}/activate/{structure_id}")
async def activate_training_structure(
    sport_id: str,
    structure_id: UUID,
    context: UserContext = Depends(RequireAthlete),
    db: Session = Depends(get_db),
):
    """
    Activate an existing training structure.
    Deactivates any other active structure for this sport.
    """
    
    # Get athlete profile
    profile = db.query(AthleteProfile).filter_by(
        user_id=context.user_id
    ).first()
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Athlete profile not found"
        )
    
    # Verify structure exists and belongs to this athlete
    verify_query = text("""
        SELECT id FROM train.athlete_training_structure
        WHERE id = :structure_id
          AND profile_id = :profile_id
          AND sport_id = :sport_id
    """)
    
    structure = db.execute(verify_query, {
        "structure_id": structure_id,
        "profile_id": profile.id,
        "sport_id": sport_id
    }).first()
    
    if not structure:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Training structure not found"
        )
    
    # Deactivate all structures for this sport
    deactivate_query = text("""
        UPDATE train.athlete_training_structure 
        SET is_active = FALSE 
        WHERE profile_id = :profile_id 
          AND sport_id = :sport_id
    """)
    db.execute(deactivate_query, {
        "profile_id": profile.id,
        "sport_id": sport_id
    })
    
    # Activate the selected structure
    activate_query = text("""
        UPDATE train.athlete_training_structure 
        SET is_active = TRUE 
        WHERE id = :structure_id
    """)
    db.execute(activate_query, {"structure_id": structure_id})
    
    db.commit()
    
    return {
        "message": "Training structure activated successfully",
        "structure_id": str(structure_id),
        "sport_id": sport_id,
        "is_active": True
    }


@router.get("/{sport_id}/history")
async def get_training_structure_history(
    sport_id: str,
    context: UserContext = Depends(RequireAthlete),
    db: Session = Depends(get_db),
):
    """Get all training structures (active and inactive) for a sport."""
    
    # Get athlete profile
    profile = db.query(AthleteProfile).filter_by(
        user_id=context.user_id
    ).first()
    
    if not profile:
        return {
            "sport_id": sport_id,
            "total_structures": 0,
            "structures": []
        }
    
    # Query all structures
    query = text("""
        SELECT 
            ats.id,
            ats.is_active,
            ats.created_at,
            atsv.field_id,
            atsv.value
        FROM train.athlete_training_structure ats
        LEFT JOIN train.athlete_training_structure_value atsv ON atsv.structure_id = ats.id
        WHERE ats.profile_id = :profile_id
          AND ats.sport_id = :sport_id
        ORDER BY ats.created_at DESC
    """)
    
    results = db.execute(query, {
        "profile_id": profile.id,
        "sport_id": sport_id
    }).fetchall()
    
    # Group by structure_id
    structures_dict = {}
    for row in results:
        sid = str(row[0])
        if sid not in structures_dict:
            structures_dict[sid] = {
                "structure_id": sid,
                "is_active": row[1],
                "created_at": row[2].isoformat() if row[2] else None,
                "values": {}
            }
        if row[3]:  # field_id
            structures_dict[sid]["values"][str(row[3])] = row[4]
    
    return {
        "sport_id": sport_id,
        "total_structures": len(structures_dict),
        "structures": list(structures_dict.values())
    }