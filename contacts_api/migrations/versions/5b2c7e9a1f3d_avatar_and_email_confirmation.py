"""avatar and email confirmation

Revision ID: 5b2c7e9a1f3d
Revises: 11df56f28d68
Create Date: 2026-10-06 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5b2c7e9a1f3d'
down_revision: Union[str, None] = '11df56f28d68'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('avatar', sa.String(length=255), nullable=True))
    op.add_column(
        'users',
        sa.Column('confirmed', sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    # accounts created before email verification existed stay usable
    op.execute(sa.text('UPDATE users SET confirmed = true'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'confirmed')
    op.drop_column('users', 'avatar')