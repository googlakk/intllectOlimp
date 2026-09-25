"""Учебники в базе: книга → страницы → параграфы → элементы, и связь с темами КТП.

Как журнал тьютора, таблицы описаны в отдельном наборе моделей: create_all при
старте их не создаёт. Они появляются только миграцией
supabase/migrations/20260926150000_textbooks.sql после согласования владельцем.
Внешние ключи заданы там же, в SQL.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Integer, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Что ученик видит из учебника: только ссылку на страницу или и текст задач (когда права подтверждены).
STUDENT_DISPLAY = ("refs_only", "verbatim")
TEXTBOOK_STATUSES = ("uploaded", "extracting", "recognizing", "structuring", "ready", "failed")


class TextbookBase(DeclarativeBase):
    """Модели, которые create_all при старте НЕ создаёт."""


class Textbook(TextbookBase):
    __tablename__ = "textbooks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(Integer)
    subject_id: Mapped[int | None] = mapped_column(Integer)
    grade: Mapped[int] = mapped_column(Integer)
    language: Mapped[str] = mapped_column(String(2), default="ru")
    title: Mapped[str] = mapped_column(String(300))
    authors: Mapped[str | None] = mapped_column(String(300))
    year: Mapped[int | None] = mapped_column(Integer)
    storage_path: Mapped[str] = mapped_column(Text)
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    page_count: Mapped[int | None] = mapped_column(Integer)
    page_offset: Mapped[int | None] = mapped_column(Integer)
    student_display: Mapped[str] = mapped_column(String(16), default="refs_only")
    status: Mapped[str] = mapped_column(String(20), default="uploaded")
    progress: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    created_by_profile_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TextbookPage(TextbookBase):
    __tablename__ = "textbook_pages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    textbook_id: Mapped[int] = mapped_column(BigInteger)
    page_index: Mapped[int] = mapped_column(Integer)
    printed_page: Mapped[int | None] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(8), default="text")      # text | ocr | edited
    status: Mapped[str] = mapped_column(String(12), default="pending")  # pending | done | failed
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    uncertain: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    figures: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TextbookSection(TextbookBase):
    __tablename__ = "textbook_sections"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    textbook_id: Mapped[int] = mapped_column(BigInteger)
    position: Mapped[int] = mapped_column(Integer)
    number: Mapped[str] = mapped_column(String(40), default="")
    title: Mapped[str] = mapped_column(Text)
    chapter: Mapped[str] = mapped_column(Text, default="")
    printed_page: Mapped[int | None] = mapped_column(Integer)
    pdf_from: Mapped[int] = mapped_column(Integer)
    pdf_to: Mapped[int] = mapped_column(Integer)
    items_status: Mapped[str] = mapped_column(String(12), default="pending")


class TextbookItem(TextbookBase):
    __tablename__ = "textbook_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    textbook_id: Mapped[int] = mapped_column(BigInteger)
    section_id: Mapped[int] = mapped_column(BigInteger)
    position: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(16))
    label: Mapped[str] = mapped_column(String(120), default="")
    page: Mapped[int | None] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text)
    difficulty: Mapped[int | None] = mapped_column(SmallInteger)


class TopicTextbookLink(TextbookBase):
    __tablename__ = "topic_textbook_links"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    topic_id: Mapped[int] = mapped_column(Integer)
    section_id: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(12), default="suggested")  # suggested | confirmed
    source: Mapped[str] = mapped_column(String(12), default="match")      # ktp | match | model | manual
    role: Mapped[str] = mapped_column(String(12), default="primary")      # primary | supporting
    score: Mapped[float | None] = mapped_column(Float)
    confirmed_by_profile_id: Mapped[int | None] = mapped_column(Integer)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
