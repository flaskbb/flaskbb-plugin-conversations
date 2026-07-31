"""move message quota setting

Revision ID: 1785520254
Revises: 1770409336
Create Date: 2026-07-31 17:50:54.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "1785520254"
down_revision = "1770409336"
branch_labels = ()
depends_on = None


def upgrade():
    conn = op.get_bind()

    settings_table = sa.table(
        "settings",
        sa.column("key", sa.String),
        sa.column("group_key", sa.String),
    )

    conn.execute(
        settings_table.update()
        .where(
            sa.func.lower(settings_table.c.key) == "message_quota",
            settings_table.c.group_key == "misc",
        )
        .values(group_key="conversations")
    )


def downgrade():
    conn = op.get_bind()

    settings_table = sa.table(
        "settings",
        sa.column("key", sa.String),
        sa.column("group_key", sa.String),
    )

    conn.execute(
        settings_table.update()
        .where(
            sa.func.lower(settings_table.c.key) == "message_quota",
            settings_table.c.group_key == "conversations",
        )
        .values(group_key="misc")
    )
