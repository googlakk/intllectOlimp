"""Отзывы учеников об уроке: оценка, были ли ошибки, комментарий.

Как и журнал тьютора, таблица описана ОТДЕЛЬНО от общего Base: create_all при старте её не
создаёт. lesson_feedback появляется только миграцией
supabase/migrations/20260927100000_lesson_feedback.sql, которую применяет владелец.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, SmallInteger, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class FeedbackBase(DeclarativeBase):
    """Модели, которые create_all при старте НЕ создаёт."""


class LessonFeedback(FeedbackBase):
    __tablename__ = "lesson_feedback"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    organization_id: Mapped[int] = mapped_column(Integer)
    student_id: Mapped[int] = mapped_column(Integer)
    topic_id: Mapped[int] = mapped_column(Integer)
    lesson_version_id: Mapped[int | None] = mapped_column(BigInteger)
    rating: Mapped[int | None] = mapped_column(SmallInteger)
    had_errors: Mapped[bool | None] = mapped_column(Boolean)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
