"""merged multi-row KTP topics and «Проведено» marks

Additive only. Repeated rows of one section with the same name get
lesson_topic_id -> first row. A row that already has its own generated lesson
is never linked, so no existing lesson or progress changes owner.

Revision ID: d5b2e3f4a6c7
Revises: c3a1f2d4e5b6
Create Date: 2026-11-25
"""
import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d5b2e3f4a6c7"
down_revision: Union[str, Sequence[str], None] = "c3a1f2d4e5b6"
branch_labels = None
depends_on = None

# Frozen copy of curriculum.merge_key so this migration never changes behaviour.
_GENERIC = re.compile(
    r"^(итоговая\s+)?(контрольная|самостоятельная|проверочная)|^закреплени|^повторени|^обобщени|^ключевые идеи|^входная",
    re.IGNORECASE,
)


def _key(name: str) -> str | None:
    normalized = re.sub(r"\s+", " ", (name or "").casefold().replace("ё", "е")).strip(" .")
    if not normalized or _GENERIC.search(normalized):
        return None
    return normalized


def upgrade() -> None:
    op.add_column("topics", sa.Column("lesson_topic_id", sa.Integer(), nullable=True))
    op.create_foreign_key("topics_lesson_topic_id_fkey", "topics", "topics", ["lesson_topic_id"], ["id"], ondelete="SET NULL")
    op.create_table(
        "topic_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("topic_id", sa.Integer(), sa.ForeignKey("topics.id", ondelete="CASCADE"), nullable=False),
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conducted_on", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("topic_id", "class_id", "conducted_on", name="topic_deliveries_unique"),
    )
    op.create_index("topic_deliveries_class_topic", "topic_deliveries", ["class_id", "topic_id"])

    connection = op.get_bind()
    rows = connection.execute(sa.text(
        "SELECT t.id, t.section_id, t.name, EXISTS (SELECT 1 FROM generated_lessons g WHERE g.topic_id = t.id) "
        "FROM topics t ORDER BY t.section_id, t.sort_number NULLS LAST, t.id"
    )).all()
    first: dict[tuple[int, str], int] = {}
    for topic_id, section_id, name, has_lesson in rows:
        key = _key(name)
        if key is None:
            continue
        group = (section_id, key)
        if group not in first:
            first[group] = topic_id
        elif not has_lesson:
            connection.execute(
                sa.text("UPDATE topics SET lesson_topic_id = :p WHERE id = :id"),
                {"p": first[group], "id": topic_id},
            )


def downgrade() -> None:
    op.drop_index("topic_deliveries_class_topic", "topic_deliveries")
    op.drop_table("topic_deliveries")
    op.drop_constraint("topics_lesson_topic_id_fkey", "topics", type_="foreignkey")
    op.drop_column("topics", "lesson_topic_id")
