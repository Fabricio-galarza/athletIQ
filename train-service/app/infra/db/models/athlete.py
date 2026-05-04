from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.infra.db.models.base_model import BaseModel


class AthleteProfile(BaseModel):
    __tablename__ = "athlete_profile"
    
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    form_id = Column(UUID(as_uuid=True), nullable=True)
    
    # Relationships - use strings to avoid circular imports
    sport_profiles = relationship("AthleteSportProfile", back_populates="profile", cascade="all, delete-orphan")
    values = relationship("AthleteProfileValue", back_populates="profile", cascade="all, delete-orphan")


class AthleteProfileValue(BaseModel):
    __tablename__ = "athlete_profile_value"
    
    profile_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("train.athlete_profile.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    field_id = Column(UUID(as_uuid=True), nullable=False)
    value = Column(String, nullable=True)
    
    # Relationship
    profile = relationship("AthleteProfile", back_populates="values")