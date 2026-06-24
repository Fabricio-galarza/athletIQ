from sqlalchemy import Column, String, Integer, Text, Date, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.infra.db.models.base_model import BaseModel

class TrainingPlanPhase(BaseModel):
    """
    Phase/Mesocycle within a training plan.
    
    Table: training_plan_phase
    Schema: train
    """
    __tablename__ = "training_plan_phase"

    plan_id = Column(
        UUID(as_uuid=True),
        ForeignKey("train.training_plan.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    name = Column(String(100), nullable=False)
    week_number = Column(Integer, nullable=False)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    focus = Column(String(50), nullable=True)  # endurance, speed, strength, taper
    
    # Relationships
    plan = relationship("TrainingPlan", back_populates="phases")
    sessions = relationship("TrainingPlanSession", back_populates="phase", cascade="all, delete-orphan")

# app/infra/db/models/plan.py
"""
Training plan models for CU-TRAIN-04
"""

from sqlalchemy import Column, String, Integer, Boolean, Date, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.infra.db.models.base_model import BaseModel


class TrainingPlan(BaseModel):
    """
    Training plan for an athlete.
    
    Table: training_plan
    Schema: train
    """
    __tablename__ = "training_plan"

    # References
    profile_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    sport_id = Column(String(50), nullable=False, index=True)
    goal_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    # Plan metadata
    plan_type = Column(String(20), nullable=False, default="generic")  # generic, adaptive
    name = Column(String(200), nullable=True)
    description = Column(String(500), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Duration
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    duration_weeks = Column(Integer, default=4)
    
    # Source
    source = Column(String(20), default="ai")  # ai, template, coach
    
    # For cloned plans (reuse)
    original_plan_id = Column(UUID(as_uuid=True), nullable=True, index=True)

     # Hash for exact matching
    profile_hash = Column(String(64), nullable=True, index=True)
    
    # Relationships
    phases = relationship("TrainingPlanPhase", back_populates="plan", cascade="all, delete-orphan")

class TrainingPlanSession(BaseModel):
    """
    Relationship between a plan phase and a training session.
    
    Table: training_plan_session
    Schema: train
    """
    __tablename__ = "training_plan_session"

    plan_id = Column(
        UUID(as_uuid=True),
        ForeignKey("train.training_plan.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    phase_id = Column(
        UUID(as_uuid=True),
        ForeignKey("train.training_plan_phase.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("train.training_session.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    week_number = Column(Integer, nullable=False)
    day_number = Column(Integer, nullable=False)
    scheduled_date = Column(Date, nullable=True)
    order = Column(Integer, default=0)
    
    # Relationships
    plan = relationship("TrainingPlan", foreign_keys=[plan_id])
    phase = relationship("TrainingPlanPhase", back_populates="sessions")
    session = relationship("TrainingSession")