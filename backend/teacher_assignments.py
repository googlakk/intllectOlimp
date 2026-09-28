"""Subject permissions are migrated manually, never by application startup."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class TeacherAssignmentBase(DeclarativeBase):
    pass


class TeacherSubjectAssignment(TeacherAssignmentBase):
    __tablename__ = "teacher_subject_assignments"

    teacher_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(BigInteger)
    assigned_by_profile_id: Mapped[int | None] = mapped_column(BigInteger)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
