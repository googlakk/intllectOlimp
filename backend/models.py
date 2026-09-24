from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSON, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Subject(Base):
    __tablename__ = "subjects"
    __table_args__ = (Index("subjects_grade_name_idx", "grade", "name", "id"),)
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
    __table_args__ = (Index("sections_subject_sort_idx", "subject_id", "sort_order"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    sort_order: Mapped[int] = mapped_column(Integer)
    total_hours: Mapped[int] = mapped_column(Integer)
    topics: Mapped[list["Topic"]] = relationship(cascade="all, delete-orphan")


class Topic(Base):
    __tablename__ = "topics"
    __table_args__ = (Index("topics_section_sort_idx", "section_id", "sort_order"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("sections.id", ondelete="CASCADE"))
    ktp_number: Mapped[str | None] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(500))
    hours: Mapped[int] = mapped_column(Integer, default=1)
    lesson_type: Mapped[str] = mapped_column(String(50), default="study")
    learning_objectives: Mapped[str | None] = mapped_column(Text)
    skills: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    resources: Mapped[str | None] = mapped_column(Text)
    covered_topic_ids: Mapped[list[int]] = mapped_column(JSONB, default=list)
    source_assessment_topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_required: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)   # порядок тем в КТП


class Skill(Base):
    __tablename__ = "skills"
    __table_args__ = (
        UniqueConstraint("canonical_key"),
        CheckConstraint("grade_min between 1 and 12"),
        CheckConstraint("grade_max between grade_min and 12"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    canonical_key: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(500))
    normalized_name: Mapped[str] = mapped_column(String(500))
    subject_family: Mapped[str] = mapped_column(String(80), default="general")
    description: Mapped[str | None] = mapped_column(Text)
    grade_min: Mapped[int] = mapped_column(Integer, default=7)
    grade_max: Mapped[int] = mapped_column(Integer, default=10)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TopicSkill(Base):
    __tablename__ = "topic_skills"
    __table_args__ = (
        CheckConstraint("role in ('prerequisite', 'outcome', 'transfer')"),
        CheckConstraint("weight > 0 and weight <= 1"),
        CheckConstraint("mastery_threshold >= 0 and mastery_threshold <= 1"),
        CheckConstraint("confidence >= 0 and confidence <= 1"),
        Index("topic_skills_skill_role_idx", "skill_id", "role"),
    )
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(30), primary_key=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    mastery_threshold: Mapped[float] = mapped_column(Float, default=0.8)
    source: Mapped[str] = mapped_column(String(40), default="inferred")
    confidence: Mapped[float] = mapped_column(Float, default=0.7)
    objective_id: Mapped[str | None] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TopicEdge(Base):
    __tablename__ = "topic_edges"
    __table_args__ = (
        UniqueConstraint("from_topic_id", "to_topic_id", "relation"),
        CheckConstraint("from_topic_id <> to_topic_id"),
        CheckConstraint("relation in ('prerequisite', 'progression', 'transfer', 'cross_subject')"),
        CheckConstraint("required_mastery >= 0 and required_mastery <= 1"),
        CheckConstraint("confidence >= 0 and confidence <= 1"),
        Index("topic_edges_from_relation_idx", "from_topic_id", "relation"),
        Index("topic_edges_to_relation_idx", "to_topic_id", "relation"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    from_topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"))
    to_topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"))
    relation: Mapped[str] = mapped_column(String(30))
    required_mastery: Mapped[float] = mapped_column(Float, default=0.8)
    confidence: Mapped[float] = mapped_column(Float, default=0.7)
    rationale: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(40), default="inferred")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StudentSkillMastery(Base):
    __tablename__ = "student_skill_mastery"
    __table_args__ = (
        UniqueConstraint("student_id", "skill_id"),
        CheckConstraint("mastery_score >= 0 and mastery_score <= 1"),
        CheckConstraint("status in ('emerging', 'developing', 'mastered')"),
        Index("student_skill_mastery_student_status_idx", "student_id", "status"),
        Index("student_skill_mastery_skill_idx", "skill_id"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"))
    mastery_score: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(30), default="emerging")
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    source_topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"))
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    last_evidence_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StudentTopicAccess(Base):
    __tablename__ = "student_topic_access"
    __table_args__ = (
        UniqueConstraint("student_id", "topic_id"),
        CheckConstraint("state in ('locked', 'available', 'in_progress', 'mastered')"),
        CheckConstraint("readiness_score >= 0 and readiness_score <= 1"),
        Index("student_topic_access_student_state_idx", "student_id", "state"),
        Index("student_topic_access_topic_idx", "topic_id"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"))
    state: Mapped[str] = mapped_column(String(30), default="locked")
    readiness_score: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(Text, default="")
    unlocked_by_topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"))
    unlocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WarpGateEvent(Base):
    __tablename__ = "warp_gate_events"
    __table_args__ = (
        UniqueConstraint("student_id", "from_topic_id", "to_topic_id"),
        CheckConstraint("readiness_score >= 0 and readiness_score <= 1"),
        Index("warp_gate_events_student_created_idx", "student_id", "created_at"),
        Index("warp_gate_events_to_topic_idx", "to_topic_id"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    from_topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"))
    to_topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"))
    readiness_score: Mapped[float] = mapped_column(Float)
    trigger_skill_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), default=list)
    explanation: Mapped[str] = mapped_column(Text)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Teacher(Base):
    __tablename__ = "teachers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Student(Base):
    __tablename__ = "students"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    grade: Mapped[int] = mapped_column(Integer, default=7)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Profile(Base):
    __tablename__ = "profiles"
    __table_args__ = (
        UniqueConstraint("auth_user_id"),
        UniqueConstraint("organization_id", "login_name"),
        CheckConstraint("role in ('admin', 'teacher', 'student')"),
        CheckConstraint("status in ('invited', 'active', 'blocked', 'archived')"),
        Index("profiles_org_role_idx", "organization_id", "role", "status"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    auth_user_id: Mapped[UUID] = mapped_column(unique=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(20))
    login_name: Mapped[str] = mapped_column(String(100))
    display_name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="active")
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True)
    teacher_id: Mapped[int | None] = mapped_column(ForeignKey("teachers.id", ondelete="SET NULL"), unique=True)
    student_id: Mapped[int | None] = mapped_column(ForeignKey("students.id", ondelete="SET NULL"), unique=True)
    created_by_profile_id: Mapped[int | None] = mapped_column(ForeignKey("profiles.id", ondelete="SET NULL"))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Classroom(Base):
    __tablename__ = "classrooms"
    __table_args__ = (
        UniqueConstraint("organization_id", "academic_year", "name"),
        CheckConstraint("grade between 1 and 12"),
        CheckConstraint("status in ('active', 'archived')"),
        Index("classrooms_org_grade_idx", "organization_id", "grade", "status"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    grade: Mapped[int] = mapped_column(Integer)
    academic_year: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_by_profile_id: Mapped[int | None] = mapped_column(ForeignKey("profiles.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClassroomTeacher(Base):
    __tablename__ = "classroom_teachers"
    classroom_id: Mapped[int] = mapped_column(ForeignKey("classrooms.id", ondelete="CASCADE"), primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id", ondelete="CASCADE"), primary_key=True)
    assigned_by_profile_id: Mapped[int | None] = mapped_column(ForeignKey("profiles.id", ondelete="SET NULL"))
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClassroomStudent(Base):
    __tablename__ = "classroom_students"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    classroom_id: Mapped[int] = mapped_column(ForeignKey("classrooms.id", ondelete="CASCADE"))
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    enrolled_by_profile_id: Mapped[int | None] = mapped_column(ForeignKey("profiles.id", ondelete="SET NULL"))
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AccountEvent(Base):
    __tablename__ = "account_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    actor_profile_id: Mapped[int | None] = mapped_column(ForeignKey("profiles.id", ondelete="SET NULL"))
    target_profile_id: Mapped[int | None] = mapped_column(ForeignKey("profiles.id", ondelete="SET NULL"))
    event_type: Mapped[str] = mapped_column(String(50))
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GeneratedLesson(Base):
    __tablename__ = "generated_lessons"
    __table_args__ = (
        Index("generated_lessons_published_topic_idx", "topic_id", postgresql_where=text("status = 'published'")),
        Index("generated_lessons_active_version_idx", "active_version_id", postgresql_where=text("active_version_id is not null")),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), unique=True)
    blocks: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    lesson_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(50), default="draft")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_by: Mapped[int | None] = mapped_column(ForeignKey("teachers.id"))
    model_used: Mapped[str | None] = mapped_column(String(255))
    active_version_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("lesson_versions.id", ondelete="SET NULL"), nullable=True
    )

    published_version_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("lesson_versions.id", ondelete="SET NULL"), nullable=True
    )


class LessonVersion(Base):
    __tablename__ = "lesson_versions"
    __table_args__ = (
        UniqueConstraint("lesson_id", "version_number"),
        Index("lesson_versions_lesson_status_idx", "lesson_id", "status", "version_number"),
        Index("lesson_versions_ready_lesson_idx", "lesson_id", "version_number", postgresql_where=text("status in ('ready', 'published')")),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("generated_lessons.id", ondelete="CASCADE"))
    version_number: Mapped[int] = mapped_column(Integer)
    schema_version: Mapped[int] = mapped_column(Integer, default=2)
    status: Mapped[str] = mapped_column(String(50), default="draft")
    blueprint: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    lesson_document: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    generator_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    model_used: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AvatarProfile(Base):
    __tablename__ = "avatar_profiles"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    provider: Mapped[str] = mapped_column(String(50), default="heygen")
    provider_avatar_id: Mapped[str] = mapped_column(String(255))
    provider_voice_id: Mapped[str | None] = mapped_column(String(255))
    supported_languages: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    voice_settings: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    consent_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    preview_image_url: Mapped[str | None] = mapped_column(Text)
    preview_audio_url: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GenerationJob(Base):
    __tablename__ = "generation_jobs"
    __table_args__ = (
        UniqueConstraint("provider", "request_hash"),
        Index("generation_jobs_status_created_idx", "status", "created_at"),
        Index("generation_jobs_version_idx", "lesson_version_id"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    lesson_version_id: Mapped[int] = mapped_column(ForeignKey("lesson_versions.id", ondelete="CASCADE"))
    scene_id: Mapped[str | None] = mapped_column(String(160))
    provider: Mapped[str] = mapped_column(String(50))
    job_type: Mapped[str] = mapped_column(String(50))
    external_job_id: Mapped[str | None] = mapped_column(String(255))
    request_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(50), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    result_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    cost: Mapped[float | None] = mapped_column(Numeric(12, 6))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LessonAsset(Base):
    __tablename__ = "lesson_assets"
    __table_args__ = (
        Index("lesson_assets_version_scene_idx", "lesson_version_id", "scene_id"),
        Index("lesson_assets_ready_version_scene_idx", "lesson_version_id", "scene_id", "created_at", postgresql_where=text("status = 'ready'")),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    lesson_version_id: Mapped[int] = mapped_column(ForeignKey("lesson_versions.id", ondelete="CASCADE"))
    generation_job_id: Mapped[int | None] = mapped_column(ForeignKey("generation_jobs.id", ondelete="SET NULL"))
    scene_id: Mapped[str | None] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(50))
    provider: Mapped[str] = mapped_column(String(50))
    provider_asset_id: Mapped[str | None] = mapped_column(String(255))
    storage_bucket: Mapped[str | None] = mapped_column(String(100))
    storage_path: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    mime_type: Mapped[str | None] = mapped_column(String(150))
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Progress(Base):
    __tablename__ = "progress"
    __table_args__ = (
        UniqueConstraint("student_id", "topic_id"),
        Index("progress_lesson_version_idx", "lesson_version_id", postgresql_where=text("lesson_version_id is not null")),
    )
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
    responses: Mapped[dict[str, str]] = mapped_column(JSONB, default=dict)
    answers: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    attempts_by_step: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    elapsed_time_sec: Mapped[int] = mapped_column(Integer, default=0)
    objective_evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    objective_mastery: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    mastery_status: Mapped[str] = mapped_column(String(50), default="not_assessed")
    lesson_version_id: Mapped[int | None] = mapped_column(ForeignKey("lesson_versions.id", ondelete="SET NULL"))
    current_episode_id: Mapped[str | None] = mapped_column(String(160))
    current_scene_id: Mapped[str | None] = mapped_column(String(160))
    avatar_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    audio_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LessonAttempt(Base):
    __tablename__ = "lesson_attempts"
    __table_args__ = (UniqueConstraint("student_id", "topic_id", "attempt_number"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="RESTRICT"))
    attempt_number: Mapped[int] = mapped_column(Integer)
    lesson_version_id: Mapped[int | None] = mapped_column(ForeignKey("lesson_versions.id", ondelete="RESTRICT"))
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
