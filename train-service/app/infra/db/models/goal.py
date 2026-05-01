from sqlalchemy import Column, String, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.infra.db.models.base_model import BaseModel


class AthleteGoal(BaseModel):
    """Athlete's sports goal"""
    __tablename__ = "athlete_goal"

    profile_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    sport_id = Column(String, nullable=False, index=True)
    form_id = Column(UUID(as_uuid=True), nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    values = relationship("AthleteGoalValue", back_populates="goal", cascade="all, delete-orphan")


class AthleteGoalValue(BaseModel):
    """Dynamic target values"""
    __tablename__ = "athlete_goal_value"

    goal_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("train.athlete_goal.id", ondelete="CASCADE"),
        nullable=False, 
        index=True
    )
    field_id = Column(UUID(as_uuid=True), nullable=False)
    value = Column(String, nullable=True)
    
    # Relationships
    goal = relationship("AthleteGoal", back_populates="values")