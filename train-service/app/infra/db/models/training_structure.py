from sqlalchemy import Column, String, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.infra.db.models.base_model import BaseModel


class AthleteTrainingStructure(BaseModel):
    """Athlete training structure"""
    __tablename__ = "athlete_training_structure"

    profile_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    sport_id = Column(String, nullable=False, index=True)
    form_id = Column(UUID(as_uuid=True), nullable=True)
    is_active = Column(Boolean, default=True)

    # Relationships
    values = relationship("AthleteTrainingStructureValue", back_populates="structure", cascade="all, delete-orphan")


class AthleteTrainingStructureValue(BaseModel):
    """Training structure values"""
    __tablename__ = "athlete_training_structure_value"

    structure_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("train.athlete_training_structure.id", ondelete="CASCADE"),
        nullable=False, 
        index=True
    )
    field_id = Column(UUID(as_uuid=True), nullable=False)
    value = Column(String, nullable=True)
    
    # Relationships
    structure = relationship("AthleteTrainingStructure", back_populates="values")