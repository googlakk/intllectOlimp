from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Subject(Base):
    __tablename__ = "subjects"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    grade: Mapped[int] = mapped_column(Integer)
    hours_per_week: Mapped[int] = mapped_column(Integer)
    hours_per_year: Mapped[int] = mapped_column(Integer)
    source_info: Mapped[str | None] = mapped_column(Text)
    instruction_language: Mapped[str] = mapped_column(String(10), default="ru")
    program: Mapped[str | None] = mapped_column(String(20))  # cambridge | national
    school_system: Mapped[int | None] = mapped_column(Integer)  # 11 | 12
    teacher_name: Mapped[str | None] = mapped_column(String(255))
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
    quarter: Mapped[int | None] = mapped_column(Integer)  # 1..4
    sort_number: Mapped[int | None] = mapped_column(Integer)
    # Repeated KTP rows of one learning topic point to its first row; the lesson lives there.
    lesson_topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"))


class SchoolClass(Base):
    """A real class such as 7Б: system (11/12-year) + grade + letter + program."""
    __tablename__ = "school_classes"
    # Local classes are unique by grade+letter; BilimOs classes are unique by external_id
    # (BilimOs branches may each have a 7А).
    __table_args__ = (
        Index(
            "school_classes_grade_letter_local_key", "grade", "letter",
            unique=True, postgresql_where=text("external_id IS NULL"),
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    school_system: Mapped[int] = mapped_column(Integer)  # 11 | 12
    grade: Mapped[int] = mapped_column(Integer)
    letter: Mapped[str] = mapped_column(String(40))
    program: Mapped[str] = mapped_column(String(20))  # cambridge | national
    external_id: Mapped[str | None] = mapped_column(String(64), unique=True)  # BilimOs id; NULL = local


class SubjectClass(Base):
    """One KTP can be taught to several classes (e.g. 7Е, 7Ж, 7З)."""
    __tablename__ = "subject_classes"
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("school_classes.id", ondelete="CASCADE"), primary_key=True)


class Quarter(Base):
    __tablename__ = "quarters"
    __table_args__ = (UniqueConstraint("academic_year", "number"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    academic_year: Mapped[str] = mapped_column(String(9))  # 2026-2027
    number: Mapped[int] = mapped_column(Integer)
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)


class TopicDelivery(Base):
    """A KTP row taught in class on a date (the «Проведено» mark). Opens lesson parts for that class."""
    __tablename__ = "topic_deliveries"
    __table_args__ = (UniqueConstraint("topic_id", "class_id", "conducted_on"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"))
    class_id: Mapped[int] = mapped_column(ForeignKey("school_classes.id", ondelete="CASCADE"))
    conducted_on: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    login: Mapped[str] = mapped_column(String(100), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))  # admin | teacher | student
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    external_id: Mapped[str | None] = mapped_column(String(64), unique=True)  # BilimOs User.id


class Teacher(Base):
    __tablename__ = "teachers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id"), nullable=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    external_id: Mapped[str | None] = mapped_column(String(64), unique=True)  # BilimOs id
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Student(Base):
    __tablename__ = "students"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    grade: Mapped[int] = mapped_column(Integer, default=7)
    class_id: Mapped[int | None] = mapped_column(ForeignKey("school_classes.id", ondelete="SET NULL"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    external_id: Mapped[str | None] = mapped_column(String(64), unique=True)  # BilimOs id
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UsedJti(Base):
    """One-time BilimOs SSO token ids; rows past expires_at are purged."""
    __tablename__ = "used_jti"
    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


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