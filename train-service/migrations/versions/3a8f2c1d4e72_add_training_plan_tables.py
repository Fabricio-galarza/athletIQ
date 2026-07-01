"""add_training_plan_tables

Revision ID: 3a8f2c1d4e72
Revises: edb8199edb11
Create Date: 2026-06-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3a8f2c1d4e72'
down_revision: Union[str, Sequence[str], None] = 'edb8199edb11'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # training_plan — no FK dependencies within this feature
    op.create_table(
        'training_plan',
        sa.Column('profile_id', sa.UUID(), nullable=False),
        sa.Column('sport_id', sa.String(length=50), nullable=False),
        sa.Column('goal_id', sa.UUID(), nullable=True),
        sa.Column('plan_type', sa.String(length=20), nullable=False, server_default='generic'),
        sa.Column('name', sa.String(length=200), nullable=True),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text('true')),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('duration_weeks', sa.Integer(), nullable=True, server_default='4'),
        sa.Column('source', sa.String(length=20), nullable=True, server_default='ai'),
        sa.Column('original_plan_id', sa.UUID(), nullable=True),
        sa.Column('profile_hash', sa.String(length=64), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        schema='train'
    )
    op.create_index(op.f('ix_train_training_plan_profile_id'), 'training_plan', ['profile_id'], unique=False, schema='train')
    op.create_index(op.f('ix_train_training_plan_sport_id'), 'training_plan', ['sport_id'], unique=False, schema='train')
    op.create_index(op.f('ix_train_training_plan_goal_id'), 'training_plan', ['goal_id'], unique=False, schema='train')
    op.create_index(op.f('ix_train_training_plan_original_plan_id'), 'training_plan', ['original_plan_id'], unique=False, schema='train')
    op.create_index(op.f('ix_train_training_plan_profile_hash'), 'training_plan', ['profile_hash'], unique=False, schema='train')

    # training_plan_phase — FK to training_plan
    op.create_table(
        'training_plan_phase',
        sa.Column('plan_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('week_number', sa.Integer(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('focus', sa.String(length=50), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['plan_id'], ['train.training_plan.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        schema='train'
    )
    op.create_index(op.f('ix_train_training_plan_phase_plan_id'), 'training_plan_phase', ['plan_id'], unique=False, schema='train')

    # training_plan_session — FK to training_plan, training_plan_phase, training_session
    op.create_table(
        'training_plan_session',
        sa.Column('plan_id', sa.UUID(), nullable=False),
        sa.Column('phase_id', sa.UUID(), nullable=False),
        sa.Column('session_id', sa.UUID(), nullable=False),
        sa.Column('week_number', sa.Integer(), nullable=False),
        sa.Column('day_number', sa.Integer(), nullable=False),
        sa.Column('scheduled_date', sa.Date(), nullable=True),
        sa.Column('order', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['plan_id'], ['train.training_plan.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['phase_id'], ['train.training_plan_phase.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['session_id'], ['train.training_session.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        schema='train'
    )
    op.create_index(op.f('ix_train_training_plan_session_plan_id'), 'training_plan_session', ['plan_id'], unique=False, schema='train')
    op.create_index(op.f('ix_train_training_plan_session_phase_id'), 'training_plan_session', ['phase_id'], unique=False, schema='train')
    op.create_index(op.f('ix_train_training_plan_session_session_id'), 'training_plan_session', ['session_id'], unique=False, schema='train')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_train_training_plan_session_session_id'), table_name='training_plan_session', schema='train')
    op.drop_index(op.f('ix_train_training_plan_session_phase_id'), table_name='training_plan_session', schema='train')
    op.drop_index(op.f('ix_train_training_plan_session_plan_id'), table_name='training_plan_session', schema='train')
    op.drop_table('training_plan_session', schema='train')

    op.drop_index(op.f('ix_train_training_plan_phase_plan_id'), table_name='training_plan_phase', schema='train')
    op.drop_table('training_plan_phase', schema='train')

    op.drop_index(op.f('ix_train_training_plan_profile_hash'), table_name='training_plan', schema='train')
    op.drop_index(op.f('ix_train_training_plan_original_plan_id'), table_name='training_plan', schema='train')
    op.drop_index(op.f('ix_train_training_plan_goal_id'), table_name='training_plan', schema='train')
    op.drop_index(op.f('ix_train_training_plan_sport_id'), table_name='training_plan', schema='train')
    op.drop_index(op.f('ix_train_training_plan_profile_id'), table_name='training_plan', schema='train')
    op.drop_table('training_plan', schema='train')
