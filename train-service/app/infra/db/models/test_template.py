"""
Test template models for CU-TRAIN-01-HU-06.
Predefined tests by sport, level, age, gender, health status.
"""

from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.infra.db.models.base_model import BaseModel


class TestTemplate(BaseModel):
    """Predefined test template by athlete criteria."""
    __tablename__ = "test_template"

    code = Column(String(100), nullable=False, unique=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    # Search criteria
    sport = Column(String(50), nullable=False, index=True)
    level = Column(String(50), nullable=False, index=True)
    min_age = Column(Integer, nullable=True)
    max_age = Column(Integer, nullable=True)
    gender = Column(String(20), nullable=True)  # male, female, any
    health_status = Column(String(50), nullable=True)  # healthy, injuries, any
    
    # Template content
    duration_minutes = Column(Integer, default=30)
    priority = Column(Integer, default=100)  # lower = higher priority
    is_active = Column(Boolean, default=True)
    
    # Relationships
    blocks = relationship("TestTemplateBlock", back_populates="template", cascade="all, delete-orphan")


class TestTemplateBlock(BaseModel):
    """Blocks for test templates."""
    __tablename__ = "test_template_block"

    template_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("train.test_template.id", ondelete="CASCADE"), 
        nullable=False,
        index=True
    )
    block_order = Column(Integer, nullable=False)  # 1, 2, 3...
    block_type = Column(String(50), nullable=False)  # warmup, main, cooldown, interval
    duration_minutes = Column(Integer, nullable=False)
    intensity = Column(String(20), nullable=True)  # easy, moderate, hard, max
    instructions = Column(Text, nullable=True)
    
    # Relationships
    template = relationship("TestTemplate", back_populates="blocks")