from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Subject(Base):
    __tablename__ = "subjects"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    grade: Mapped[int] = mapped_column(Integer)
    hours_per_week: Mapped[float] = mapped_column(Float)   # 1,8 часа в неделю бывает
    hours_per_year: Mapped[int] = mapped_column(Integer)
    source_info: Mapped[str | None] = mapped_column(Text)
    instruction_language: Mapped[str] = mapped_column(String(10), default="ru")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sections: Mapped[list["Section"]] = relationship(cascade="all, delete-orphan")


class Section(Base):
    __tablename__ = "sections"
    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    sort_order: Mapped[int] = mapped_column(Integer)
    total_hours: Mapped[int] = mapped_column(Integer)
    topics: Mapped[list["Topic"]] = relationship(cascade="all, delete-orphan")


class Topic(Base):
    __tablename__ = "topics"
    id: Mapped[int] = mapped_column(primary_key=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("sections.id", ondelete="CASCADE"))
    ktp_number: Mapped[str | None] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(500))
    hours: Mapped[int] = mapped_column(Integer, default=1)
    lesson_type: Mapped[str] = mapped_column(String(50), default="study")
    learning_objectives: Mapped[str | None] = mapped_column(Text)
    skills: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    resources: Mapped[str | None] = mapped_column(Text)


class Teacher(Base):
    __tablename__ = "teachers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Student(Base):
    __tablename__ = "students"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    grade: Mapped[int] = mapped_column(Integer, default=7)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GeneratedLesson(Base):
    __tablename__ = "generated_lessons"
    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), unique=True)
    blocks: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    lesson_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(50), default="draft")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_by: Mapped[int | None] = mapped_column(ForeignKey("teachers.id"))
    model_used: Mapped[str | None] = mapped_column(String(255))


class Progress(Base):
    __tablename__ = "progress"
    __table_args__ = (UniqueConstraint("student_id", "topic_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(50), default="not_started")
    score: Mapped[float | None] = mapped_column(Float)
    mastery_level: Mapped[str | None] = mapped_column(String(50))
    time_spent_sec: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    max_opened_step: Mapped[int] = mapped_column(Integer, default=0)
    answers: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    attempts_by_step: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    elapsed_time_sec: Mapped[int] = mapped_column(Integer, default=0)
    objective_evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    objective_mastery: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    mastery_status: Mapped[str] = mapped_column(String(50), default="not_assessed")