"""Update SQLAlchemy 2

Revision ID: 1770409336
Revises: 0625bc75ab77
Create Date: 2026-02-06 21:22:16.464657

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "1770409336"
down_revision = "0625bc75ab77"
branch_labels = ()
depends_on = None


def upgrade():
    # Version 1.x stored the 16 UUID bytes, sa.Uuid() stores 32 hex characters
    # on MySQL and SQLite
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        # the column has NUMERIC affinity until the rebuild, which would turn
        # hex strings like "1234e567..." into numbers - the "x" prevents that
        op.execute(
            "UPDATE conversations SET shared_id = 'x' || lower(hex(shared_id)) "
            "WHERE typeof(shared_id) = 'blob'"
        )
    elif bind.dialect.name == "mysql":
        shared_id = next(
            column
            for column in sa.inspect(bind).get_columns("conversations")
            if column["name"] == "shared_id"
        )
        if isinstance(shared_id["type"], sa.BINARY):
            op.alter_column(
                "conversations",
                "shared_id",
                existing_type=shared_id["type"],
                type_=sa.VARBINARY(32),
                existing_nullable=False,
            )
            op.execute("UPDATE conversations SET shared_id = LOWER(HEX(shared_id))")

    with op.batch_alter_table("conversations", schema=None) as batch_op:
        batch_op.alter_column(
            "shared_id",
            existing_type=sa.NUMERIC(precision=16),
            type_=sa.Uuid(),
            existing_nullable=False,
        )

    if bind.dialect.name == "sqlite":
        op.execute(
            "UPDATE conversations SET shared_id = substr(shared_id, 2) WHERE shared_id LIKE 'x%'"
        )

    with op.batch_alter_table("messages", schema=None) as batch_op:
        batch_op.alter_column("message", existing_type=sa.TEXT(), nullable=True)
    # ### end Alembic commands ###


def downgrade():
    with op.batch_alter_table("messages", schema=None) as batch_op:
        batch_op.alter_column("message", existing_type=sa.TEXT(), nullable=False)

    with op.batch_alter_table("conversations", schema=None) as batch_op:
        batch_op.alter_column(
            "shared_id",
            existing_type=sa.Uuid(),
            type_=sa.NUMERIC(precision=16),
            existing_nullable=False,
        )

    # ### end Alembic commands ###
