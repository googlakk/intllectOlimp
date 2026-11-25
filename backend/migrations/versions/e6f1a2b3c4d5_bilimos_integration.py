"""BilimOs integration: external ids, one-time SSO token ids, sync-safe uniqueness

Additive for existing data: no row is deleted or changed.
- external_id (BilimOs id, NULL for local rows) on users, students, teachers, school_classes.
- used_jti: one-time SSO token ids.
- students.name / teachers.name are no longer unique: two children may share a name.
  Nothing relies on it (lookups go by id / user_id).
- school_classes.letter widened 5 -> 40 (BilimOs letters like «Кембридж», «А-12»);
  grade+letter stays unique only for local classes (BilimOs branches may each have a 7А).

Downgrade fails if synced data violates the old constraints (duplicate names, long letters).

Revision ID: e6f1a2b3c4d5
Revises: d5b2e3f4a6c7
Create Date: 2026-11-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e6f1a2b3c4d5"
down_revision: Union[str, Sequence[str], None] = "d5b2e3f4a6c7"
branch_labels = None
depends_on = None

TABLES = ("users", "students", "teachers", "school_classes")


def upgrade() -> None:
    op.create_table(
        "used_jti",
        sa.Column("jti", sa.String(64), primary_key=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    for table in TABLES:
        op.add_column(table, sa.Column("external_id", sa.String(64), nullable=True))
        op.create_unique_constraint(f"{table}_external_id_key", table, ["external_id"])
    op.drop_constraint("students_name_key", "students", type_="unique")
    op.drop_constraint("teachers_name_key", "teachers", type_="unique")
    op.alter_column("school_classes", "letter", existing_type=sa.String(5), type_=sa.String(40), existing_nullable=False)
    op.drop_constraint("school_classes_grade_letter_key", "school_classes", type_="unique")
    op.create_index(
        "school_classes_grade_letter_local_key", "school_classes", ["grade", "letter"],
        unique=True, postgresql_where=sa.text("external_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("school_classes_grade_letter_local_key", table_name="school_classes")
    op.create_unique_constraint("school_classes_grade_letter_key", "school_classes", ["grade", "letter"])
    op.alter_column("school_classes", "letter", existing_type=sa.String(40), type_=sa.String(5), existing_nullable=False)
    op.create_unique_constraint("teachers_name_key", "teachers", ["name"])
    op.create_unique_constraint("students_name_key", "students", ["name"])
    for table in TABLES:
        op.drop_constraint(f"{table}_external_id_key", table, type_="unique")
        op.drop_column(table, "external_id")
    op.drop_table("used_jti")
