"""
Training session models for storing workout sessions and test sessions.
"""

from sqlalchemy import Column, String, Integer, Text, Date, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.infra.db.models.base_model import BaseModel


class TrainingSession(BaseModel):
    """
    Training session (including test sessions from CU-TRAIN-01-HU-06).
    Table: training_session
    Schema: train
    """
    __tablename__ = "training_session"

    # References
    profile_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    sport_id = Column(String(50), nullable=False, index=True)
    
    # Session metadata
    status = Column(String(20), nullable=False, default="planned")  # planned, completed, skipped
    source = Column(String(20), nullable=False, default="ai")  # ai, coach, template, test
    
    # Scheduling
    planned_date = Column(Date, nullable=True)
    planned_duration_minutes = Column(Integer, nullable=True)
    
    # Execution
    executed_at = Column(DateTime, nullable=True)
    
    # Relationships
    blocks = relationship("TrainingSessionBlock", back_populates="session", cascade="all, delete-orphan")


class TrainingSessionBlock(BaseModel):
    """
    Blocks within a training session.
    Table: training_session_block
    Schema: train
    """
    __tablename__ = "training_session_block"

    session_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("train.training_session.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    order = Column(Integer, nullable=False)  # 1, 2, 3...
    block_type = Column(String(50), nullable=False)  # warmup, main, cooldown, interval
    
    # 🔥 Campos que faltaban en el modelo
    duration_minutes = Column(Integer, nullable=True)  # Block duration in minutes
    intensity = Column(String(20), nullable=True)  # easy, moderate, hard, max
    instructions = Column(Text, nullable=True)  # Instrucciones for the block
    
    # Relationships
    session = relationship("TrainingSession", back_populates="blocks")