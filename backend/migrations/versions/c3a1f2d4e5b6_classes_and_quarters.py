"""school classes, programs and KTP quarters

Additive only: no existing row is deleted and no existing value is changed.
Existing topics get a quarter computed from hours (weeks 8/7/8/11, the school
calendar rule); existing students keep grade and get class_id = NULL until an
admin assigns a class.

Revision ID: c3a1f2d4e5b6
Revises: 40678e966b53
Create Date: 2026-11-25
"""
from datetime import date
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3a1f2d4e5b6"
down_revision: Union[str, Sequence[str], None] = "40678e966b53"
branch_labels = None
depends_on = None

QUARTER_WEEKS = (8, 7, 8, 11)
QUARTERS_2026 = (
    (1, date(2026, 9, 1), date(2026, 11, 15)),
    (2, date(2026, 11, 16), date(2027, 1, 10)),
    (3, date(2027, 1, 11), date(2027, 3, 8)),
    (4, date(2027, 3, 9), date(2027, 5, 31)),
)


def _quarter_for(position_hours: float, total_hours: float) -> int:
    """Quarter of a topic that starts after `position_hours` of `total_hours`."""
    if total_hours <= 0:
        return 1
    share, bound = position_hours / total_hours, 0.0
    for number, weeks in enumerate(QUARTER_WEEKS, start=1):
        bound += weeks / sum(QUARTER_WEEKS)
        if share < bound:
            return number
    return 4


def upgrade() -> None:
    op.create_table(
        "school_classes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("school_system", sa.Integer(), nullable=False),
        sa.Column("grade", sa.Integer(), nullable=False),
        sa.Column("letter", sa.String(5), nullable=False),
        sa.Column("program", sa.String(20), nullable=False),
        sa.UniqueConstraint("grade", "letter", name="school_classes_grade_letter_key"),
    )
    op.create_table(
        "subject_classes",
        sa.Column("subject_id", sa.Integer(), sa.ForeignKey("subjects.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("school_classes.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "quarters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("academic_year", sa.String(9), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.UniqueConstraint("academic_year", "number", name="quarters_year_number_key"),
    )
    op.add_column("students", sa.Column("class_id", sa.Integer(), nullable=True))
    op.create_foreign_key("students_class_id_fkey", "students", "school_classes", ["class_id"], ["id"], ondelete="SET NULL")
    op.add_column("subjects", sa.Column("program", sa.String(20), nullable=True))
    op.add_column("subjects", sa.Column("school_system", sa.Integer(), nullable=True))
    op.add_column("subjects", sa.Column("teacher_name", sa.String(255), nullable=True))
    op.add_column("topics", sa.Column("quarter", sa.Integer(), nullable=True))
    op.add_column("topics", sa.Column("sort_number", sa.Integer(), nullable=True))

    connection = op.get_bind()
    quarters = sa.table("quarters", sa.column("academic_year"), sa.column("number"), sa.column("starts_on"), sa.column("ends_on"))
    op.bulk_insert(quarters, [{"academic_year": "2026-2027", "number": n, "starts_on": s, "ends_on": e} for n, s, e in QUARTERS_2026])

    # Backfill quarter + running number for existing KTP, in current display order.
    subject_ids = connection.execute(sa.text("SELECT id FROM subjects ORDER BY id")).scalars().all()
    for subject_id in subject_ids:
        topics = connection.execute(
            sa.text(
                "SELECT t.id, t.hours FROM topics t JOIN sections s ON s.id = t.section_id "
                "WHERE s.subject_id = :sid ORDER BY s.sort_order, s.id, t.id"
            ),
            {"sid": subject_id},
        ).all()
        total = sum(max(hours or 1, 1) for _, hours in topics)
        position = 0
        for number, (topic_id, hours) in enumerate(topics, start=1):
            connection.execute(
                sa.text("UPDATE topics SET quarter = :q, sort_number = :n WHERE id = :id"),
                {"q": _quarter_for(position, total), "n": number, "id": topic_id},
            )
            position += max(hours or 1, 1)


def downgrade() -> None:
    op.drop_column("topics", "sort_number")
    op.drop_column("topics", "quarter")
    op.drop_column("subjects", "teacher_name")
    op.drop_column("subjects", "school_system")
    op.drop_column("subjects", "program")
    op.drop_constraint("students_class_id_fkey", "students", type_="foreignkey")
    op.drop_column("students", "class_id")
    op.drop_table("quarters")
    op.drop_table("subject_classes")
    op.drop_table("school_classes")
