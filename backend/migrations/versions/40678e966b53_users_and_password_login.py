"""users and password login

Revision ID: 40678e966b53
Revises: bb0fd10140f3
Create Date: 2026-11-24 14:51:11.053305

"""
from typing import Sequence, Union

from alembic import op
import re

import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '40678e966b53'
down_revision: Union[str, Sequence[str], None] = 'bb0fd10140f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z",
    "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "ң": "n", "о": "o", "ө": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ү": "u", "ф": "f", "х": "kh", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def _login(full_name: str, taken: set[str]) -> str:
    # Frozen copy of accounts.unique_login so this migration never changes behaviour.
    parts = ["".join(_TRANSLIT.get(c, c) for c in part.casefold()) for part in full_name.split()]
    parts = [re.sub(r"[^a-z0-9]", "", part) for part in parts]
    base = ".".join([part for part in parts if part][:2]) or "user"
    login, counter = base, 2
    while login in taken:
        login, counter = f"{base}{counter}", counter + 1
    taken.add(login)
    return login


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("login", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("must_change_password", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("login", name="users_login_key"),
    )
    for table in ("students", "teachers"):
        op.add_column(table, sa.Column("user_id", sa.Integer(), nullable=True))
        op.create_unique_constraint(f"{table}_user_id_key", table, ["user_id"])
        op.create_foreign_key(f"{table}_user_id_fkey", table, "users", ["user_id"], ["id"], ondelete="CASCADE")

    # Give every existing person an account. No password is set: an admin
    # issues one (manage.py set-password or the admin UI) before first login.
    connection = op.get_bind()
    taken: set[str] = set()
    for table, role in (("teachers", "teacher"), ("students", "student")):
        rows = connection.execute(sa.text(f"SELECT id, name FROM {table} ORDER BY id")).all()
        for person_id, name in rows:
            user_id = connection.execute(
                sa.text(
                    "INSERT INTO users (login, full_name, role) VALUES (:login, :name, :role) RETURNING id"
                ),
                {"login": _login(name, taken), "name": name, "role": role},
            ).scalar_one()
            connection.execute(
                sa.text(f"UPDATE {table} SET user_id = :user_id WHERE id = :id"),
                {"user_id": user_id, "id": person_id},
            )


def downgrade() -> None:
    for table in ("teachers", "students"):
        op.drop_constraint(f"{table}_user_id_fkey", table, type_="foreignkey")
        op.drop_constraint(f"{table}_user_id_key", table, type_="unique")
        op.drop_column(table, "user_id")
    op.drop_table("users")
