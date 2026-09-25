"""Журнал реплик тьютора.

Таблица описана в ОТДЕЛЬНОМ наборе моделей, а не в общем Base: при старте
бэкенд вызывает Base.metadata.create_all, и новая таблица иначе сама появилась
бы в общей базе. tutor_turns создаётся только миграцией
supabase/migrations/20260926120000_tutor_turns.sql — после согласования
владельцем. Внешние ключи заданы там же, в SQL.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class TutorBase(DeclarativeBase):
    """Модели, которые create_all при старте НЕ создаёт."""


class TutorTurn(TutorBase):
    __tablename__ = "tutor_turns"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    student_id: Mapped[int] = mapped_column(Integer)
    topic_id: Mapped[int] = mapped_column(Integer)
    lesson_version_id: Mapped[int | None] = mapped_column(BigInteger)
    block_index: Mapped[int] = mapped_column(Integer)
    question_index: Mapped[int | None] = mapped_column(Integer)
    step_index: Mapped[int | None] = mapped_column(Integer)
    event: Mapped[str] = mapped_column(String(24))
    student_text: Mapped[str | None] = mapped_column(Text)
    student_value: Mapped[str | None] = mapped_column(String(200))
    check_outcome: Mapped[str | None] = mapped_column(String(16))
    reply: Mapped[str] = mapped_column(Text, default="")
    reply_source: Mapped[str] = mapped_column(String(12))
    action: Mapped[str | None] = mapped_column(String(24))
    action_args: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    misconception_code: Mapped[str | None] = mapped_column(String(80))
    diagnosis: Mapped[str | None] = mapped_column(Text)
    hint_level: Mapped[int | None] = mapped_column(Integer)
    safety_flag: Mapped[str] = mapped_column(String(16), default="none")
    off_topic: Mapped[bool] = mapped_column(Boolean, default=False)
    leak_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    llm_called: Mapped[bool] = mapped_column(Boolean, default=False)
    provider: Mapped[str | None] = mapped_column(String(80))
    model: Mapped[str | None] = mapped_column(String(80))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cache_read_tokens: Mapped[int | None] = mapped_column(Integer)
    cache_write_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
