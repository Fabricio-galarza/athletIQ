from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.infra.db.models.base_model import BaseModel

class AthleteSportProfile(BaseModel):
    __tablename__ = "athlete_sport_profile"
    
    profile_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("train.athlete_profile.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    sport_id = Column(String, nullable=False, index=True)
    form_id = Column(UUID(as_uuid=True), nullable=True)
    
    # Use strings for relationships to avoid circular imports
    profile = relationship("AthleteProfile", back_populates="sport_profiles")
    values = relationship("AthleteSportProfileValue", back_populates="sport_profile", cascade="all, delete-orphan")


class AthleteSportProfileValue(BaseModel):
    __tablename__ = "athlete_sport_profile_value"
    
    sport_profile_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("train.athlete_sport_profile.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    field_id = Column(UUID(as_uuid=True), nullable=False)
    value = Column(String, nullable=True)
    
    # Use string for relationship
    sport_profile = relationship("AthleteSportProfile", back_populates="values")