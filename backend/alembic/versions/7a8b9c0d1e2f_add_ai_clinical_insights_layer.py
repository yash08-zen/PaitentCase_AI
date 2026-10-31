"""add_ai_clinical_insights_layer

Revision ID: 7a8b9c0d1e2f
Revises: 1cc939388310
Create Date: 2026-10-31 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a8b9c0d1e2f'
down_revision: Union[str, None] = '1cc939388310'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. ai_insights table
    op.create_table(
        'ai_insights',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('encounter_id', sa.Integer(), nullable=False),
        sa.Column('insight_type', sa.String(length=100), nullable=False),
        sa.Column('content', sa.JSON(), nullable=False),
        sa.Column('evidence', sa.JSON(), nullable=True),
        sa.Column('status', sa.Enum('pending', 'accepted', 'edited', 'rejected', name='aiinsightstatus'), nullable=False),
        sa.Column('provenance', sa.String(length=100), nullable=False),
        sa.Column('model_name', sa.String(length=100), nullable=True),
        sa.Column('prompt_version', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('decided_by', sa.Integer(), nullable=True),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('doctor_edits', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['decided_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['encounter_id'], ['encounters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_insights_id'), 'ai_insights', ['id'], unique=False)
    op.create_index(op.f('ix_ai_insights_encounter_id'), 'ai_insights', ['encounter_id'], unique=False)

    # 2. lab_results table
    op.create_table(
        'lab_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('encounter_id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=True),
        sa.Column('test_name', sa.String(length=150), nullable=False),
        sa.Column('normalized_test', sa.String(length=150), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=50), nullable=True),
        sa.Column('ref_low', sa.Float(), nullable=True),
        sa.Column('ref_high', sa.Float(), nullable=True),
        sa.Column('flag', sa.String(length=50), nullable=True),
        sa.Column('test_date', sa.String(length=50), nullable=True),
        sa.Column('source_span', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['encounter_id'], ['encounters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_lab_results_id'), 'lab_results', ['id'], unique=False)
    op.create_index(op.f('ix_lab_results_encounter_id'), 'lab_results', ['encounter_id'], unique=False)
    op.create_index(op.f('ix_lab_results_document_id'), 'lab_results', ['document_id'], unique=False)
    op.create_index(op.f('ix_lab_results_normalized_test'), 'lab_results', ['normalized_test'], unique=False)

    # 3. document_entities table
    op.create_table(
        'document_entities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('encounter_id', sa.Integer(), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('value', sa.JSON(), nullable=False),
        sa.Column('raw_text', sa.Text(), nullable=True),
        sa.Column('source_span', sa.String(length=255), nullable=True),
        sa.Column('grounded', sa.Boolean(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('provenance', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['encounter_id'], ['encounters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_document_entities_id'), 'document_entities', ['id'], unique=False)
    op.create_index(op.f('ix_document_entities_document_id'), 'document_entities', ['document_id'], unique=False)
    op.create_index(op.f('ix_document_entities_encounter_id'), 'document_entities', ['encounter_id'], unique=False)

    # 4. trend_flags table
    op.create_table(
        'trend_flags',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('encounter_id', sa.Integer(), nullable=False),
        sa.Column('test_name', sa.String(length=150), nullable=False),
        sa.Column('previous_value', sa.Float(), nullable=False),
        sa.Column('current_value', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=50), nullable=True),
        sa.Column('delta', sa.Float(), nullable=False),
        sa.Column('percent_change', sa.Float(), nullable=False),
        sa.Column('direction', sa.String(length=20), nullable=False),
        sa.Column('time_span_days', sa.Integer(), nullable=True),
        sa.Column('rule_matched', sa.String(length=100), nullable=True),
        sa.Column('clinical_label', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['encounter_id'], ['encounters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_trend_flags_id'), 'trend_flags', ['id'], unique=False)
    op.create_index(op.f('ix_trend_flags_encounter_id'), 'trend_flags', ['encounter_id'], unique=False)

    # 5. risk_scores table
    op.create_table(
        'risk_scores',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('encounter_id', sa.Integer(), nullable=False),
        sa.Column('score_name', sa.String(length=100), nullable=False),
        sa.Column('score_value', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('inputs', sa.JSON(), nullable=True),
        sa.Column('missing_inputs', sa.JSON(), nullable=True),
        sa.Column('formula_version', sa.String(length=50), nullable=False),
        sa.Column('interpretation', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['encounter_id'], ['encounters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_risk_scores_id'), 'risk_scores', ['id'], unique=False)
    op.create_index(op.f('ix_risk_scores_encounter_id'), 'risk_scores', ['encounter_id'], unique=False)

    # 6. guideline_passages table
    op.create_table(
        'guideline_passages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(length=255), nullable=False),
        sa.Column('version_date', sa.String(length=50), nullable=False),
        sa.Column('condition_or_topic', sa.String(length=150), nullable=False),
        sa.Column('section', sa.String(length=150), nullable=False),
        sa.Column('passage_text', sa.Text(), nullable=False),
        sa.Column('citations', sa.JSON(), nullable=True),
        sa.Column('is_sample', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_guideline_passages_id'), 'guideline_passages', ['id'], unique=False)
    op.create_index(op.f('ix_guideline_passages_condition_or_topic'), 'guideline_passages', ['condition_or_topic'], unique=False)

    # 7. llm_jobs table
    op.create_table(
        'llm_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('encounter_id', sa.Integer(), nullable=False),
        sa.Column('job_type', sa.String(length=100), nullable=False),
        sa.Column('status', sa.Enum('pending', 'running', 'completed', 'failed', 'unavailable', name='jobstatus'), nullable=False),
        sa.Column('progress', sa.Float(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['encounter_id'], ['encounters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_llm_jobs_id'), 'llm_jobs', ['id'], unique=False)
    op.create_index(op.f('ix_llm_jobs_encounter_id'), 'llm_jobs', ['encounter_id'], unique=False)


def downgrade() -> None:
    op.drop_table('llm_jobs')
    op.drop_table('guideline_passages')
    op.drop_table('risk_scores')
    op.drop_table('trend_flags')
    op.drop_table('document_entities')
    op.drop_table('lab_results')
    op.drop_table('ai_insights')

