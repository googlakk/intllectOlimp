from sqlalchemy.ext.asyncio import AsyncSession

from errors import ApplicationError
from models import Section, Student, Subject, Topic


class GradeAccessError(ApplicationError):
    pass


async def get_student_for_access(student_id: int, db: AsyncSession) -> Student:
    student = await db.get(Student, student_id)
    if student is None:
        raise GradeAccessError(status_code=404, detail="Ученик не найден")
    return student


async def require_subject_access(
    student_id: int,
    subject_id: int,
    db: AsyncSession,
    *,
    student: Student | None = None,
) -> Subject:
    student = student or await get_student_for_access(student_id, db)
    subject = await db.get(Subject, subject_id)
    if subject is None:
        raise GradeAccessError(status_code=404, detail="Предмет не найден")
    if subject.grade > student.grade:
        raise GradeAccessError(
            status_code=404,
            detail="Предмет недоступен для класса ученика",
        )
    return subject


async def require_section_access(
    student_id: int,
    section_id: int,
    db: AsyncSession,
    *,
    student: Student | None = None,
) -> Section:
    student = student or await get_student_for_access(student_id, db)
    section = await db.get(Section, section_id)
    if section is None:
        raise GradeAccessError(status_code=404, detail="Раздел не найден")
    await require_subject_access(student_id, section.subject_id, db, student=student)
    return section


async def require_topic_access(
    student_id: int,
    topic_id: int,
    db: AsyncSession,
) -> Topic:
    student = await get_student_for_access(student_id, db)
    topic = await db.get(Topic, topic_id)
    if topic is None:
        raise GradeAccessError(status_code=404, detail="Тема не найдена")
    await require_section_access(student_id, topic.section_id, db, student=student)
    return topic
