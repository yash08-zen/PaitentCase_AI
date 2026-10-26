"""add_patient_user_id

Revision ID: 1cc939388310
Revises: 5dc1a05e3dc9
Create Date: 2026-10-23 11:50:10.875181

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1cc939388310'
down_revision: Union[str, None] = '5dc1a05e3dc9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('patients', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_patients_user_id'), ['user_id'], unique=False)
        batch_op.create_foreign_key('fk_patients_user_id', 'users', ['user_id'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('patients', schema=None) as batch_op:
        batch_op.drop_constraint('fk_patients_user_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_patients_user_id'))
        batch_op.drop_column('user_id')
