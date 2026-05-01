from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.infra.db.models.base_model import BaseModel


class AthleteHealthProfile(BaseModel):
    """Athlete's health profile"""
    __tablename__ = "athlete_health_profile"

    profile_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    form_id = Column(UUID(as_uuid=True), nullable=True)
    
    # Relationships
    values = relationship("AthleteHealthProfileValue", back_populates="health_profile", cascade="all, delete-orphan")


class AthleteHealthProfileValue(BaseModel):
    """Dynamic values ​​of the health profile"""
    __tablename__ = "athlete_health_profile_value"

    health_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("train.athlete_health_profile.id", ondelete="CASCADE"),
        nullable=False, 
        index=True
    )
    field_id = Column(UUID(as_uuid=True), nullable=False)
    value = Column(String, nullable=True)
    
    # Relationships
    health_profile = relationship("AthleteHealthProfile", back_populates="values")