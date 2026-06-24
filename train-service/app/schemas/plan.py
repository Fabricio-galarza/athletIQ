# app/schemas/plan.py
"""
Pydantic schemas for plan generation (CU-TRAIN-04)
"""

from uuid import UUID
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from datetime import date


class PlanGenerationRequest(BaseModel):
    """
    Request schema for generating a training plan.
    """
    sport_id: str = Field(..., description="Sport name (e.g., 'Running')")
    plan_type: str = Field(
        default="generic",
        description="Plan type: 'generic' or 'adaptive'"
    )
    force_regenerate: bool = Field(
        default=False,
        description="Force generation even if reusable plan exists"
    )


class PlanGenerationResponse(BaseModel):
    """
    Response schema after generating a training plan.
    """
    success: bool
    plan_id: Optional[UUID] = None  # 🔥 Allow None for failed generation
    plan_type: str
    is_new_plan: bool
    reused_from_plan_id: Optional[UUID] = None
    message: str
    sessions_created: int = 0
    total_weeks: int = 0