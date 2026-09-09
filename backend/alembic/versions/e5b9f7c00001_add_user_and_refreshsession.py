"""add_user_and_refreshsession

Revision ID: e5b9f7c00001
Revises: 4d9fbe0b0a7f
Create Date: 2026-09-08 17:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5b9f7c00001'
down_revision: Union[str, Sequence[str], None] = '4d9fbe0b0a7f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('users',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('email', sa.String(), nullable=False),
    sa.Column('hashed_password', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)

    op.create_table('refresh_sessions',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('refresh_token_jti', sa.String(), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.Column('revoked', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('refresh_sessions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_refresh_sessions_refresh_token_jti'), ['refresh_token_jti'], unique=True)
        batch_op.create_index(batch_op.f('ix_refresh_sessions_user_id'), ['user_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('refresh_sessions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_refresh_sessions_user_id'))
        batch_op.drop_index(batch_op.f('ix_refresh_sessions_refresh_token_jti'))
    op.drop_table('refresh_sessions')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_email'))
    op.drop_table('users')
