"""
Pydantic schemas for athlete profile management (CU-TRAIN-01)
"""
from uuid import UUID
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class SportProfileCreate(BaseModel):
    """Request schema for creating a sport profile."""
    sport_id: str = Field(..., description="Sport name (e.g., 'Running')")
    form_data: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Dynamic form data by form code"
    )


class SportProfileResponse(BaseModel):
    """Response schema after creating a sport profile."""
    message: str
    profile_id: UUID
    sport_profile_id: UUID
    has_sufficient_data: bool
    requires_test: bool
    missing_fields: List[str] = []


class SportProfileUpdate(BaseModel):
    """Request schema for updating specific fields of a sport profile."""
    form_data: Dict[str, Dict[str, Any]] = Field(
        ...,
        description="Fields to update, organized by form code"
    )


class SportProfileUpdateResponse(BaseModel):
    """Response schema after updating a sport profile."""
    message: str
    profile_id: UUID
    sport_profile_id: UUID
    updated_fields: List[str]
    has_sufficient_data: bool
    requires_test: bool