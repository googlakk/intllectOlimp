from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from errors import ApplicationError
from models import Skill, StudentSkillMastery, Classroom, ClassroomStudent, ClassroomTeacher, GeneratedLesson, Progress, Section, Student, Subject, Topic
from services.auth import AuthPrincipal


def build_dashboard_overview(
    *,
    students: int,
    subjects: int,
    topics: int,
    published_lessons: int,
    completed_lessons: int,
) -> dict[str, int | float]:
    return {
        "students": students,
        "subjects": subjects,
        "topics": topics,
        "published_lessons": published_lessons,
        "average_progress": min(100, round(completed_lessons / (topics * students) * 100, 1)) if topics and students else 0,
    }


def serialize_student_summary(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "grade": row.grade,
        "completed_topics": row.completed_topics,
        "average_score": float(row.average_score),
    }


async def _visible_student_ids(db: AsyncSession, user: AuthPrincipal) -> list[int] | None:
    if user.role == "admin":
        return None
    return list((await db.scalars(
        select(ClassroomStudent.student_id)
        .join(ClassroomTeacher, ClassroomTeacher.classroom_id == ClassroomStudent.classroom_id)
        .join(Classroom, Classroom.id == ClassroomStudent.classroom_id)
        .where(ClassroomTeacher.teacher_id == user.teacher_id, ClassroomStudent.left_at.is_(None), Classroom.status == "active")
        .distinct()
    )).all())


async def _visible_max_grade(db: AsyncSession, user: AuthPrincipal) -> int | None:
    if user.role == "admin":
        return None
    grade = await db.scalar(
        select(func.max(Classroom.grade))
        .join(ClassroomTeacher, ClassroomTeacher.classroom_id == Classroom.id)
        .where(
            ClassroomTeacher.teacher_id == user.teacher_id,
            Classroom.status == "active",
        )
    )
    return int(grade) if grade is not None else 0


async def get_dashboard_overview(db: AsyncSession, *, user: AuthPrincipal) -> dict[str, int | float]:
    visible_ids = await _visible_student_ids(db, user)
    max_grade = await _visible_max_grade(db, user)
    students_query = select(func.count(Student.id))
    completed_query = select(func.count(Progress.id)).join(Topic, Topic.id == Progress.topic_id).join(Section, Section.id == Topic.section_id).join(Subject, Subject.id == Section.subject_id).where(Progress.status == "completed", Topic.archived_at.is_(None))
    if visible_ids is not None:
        students_query = students_query.where(Student.id.in_(visible_ids))
        completed_query = completed_query.where(Progress.student_id.in_(visible_ids))
    students = await db.scalar(students_query) or 0
    subjects_query = select(func.count(Subject.id))
    topics_query = select(func.count(Topic.id)).join(Section, Section.id == Topic.section_id).join(Subject, Subject.id == Section.subject_id).where(Topic.archived_at.is_(None))
    published_query = (
        select(func.count(GeneratedLesson.id))
        .join(Topic, Topic.id == GeneratedLesson.topic_id)
        .join(Section, Section.id == Topic.section_id)
        .join(Subject, Subject.id == Section.subject_id)
        .where(GeneratedLesson.status == "published", Topic.archived_at.is_(None))
    )
    if max_grade is not None:
        subjects_query = subjects_query.where(Subject.grade <= max_grade)
        topics_query = topics_query.where(Subject.grade <= max_grade)
        completed_query = completed_query.where(Subject.grade <= max_grade)
        published_query = published_query.where(Subject.grade <= max_grade)
    subjects = await db.scalar(subjects_query) or 0
    topics = await db.scalar(topics_query) or 0
    published = await db.scalar(published_query) or 0
    completed = await db.scalar(completed_query) or 0
    return build_dashboard_overview(
        students=students,
        subjects=subjects,
        topics=topics,
        published_lessons=published,
        completed_lessons=completed,
    )


async def get_dashboard_students(db: AsyncSession, *, user: AuthPrincipal) -> list[dict[str, Any]]:
    visible_ids = await _visible_student_ids(db, user)
    statement = select(
        Student.id,
        Student.name,
        Student.grade,
        func.count(Progress.id)
        .filter(and_(Progress.status == "completed", Topic.archived_at.is_(None)))
        .label("completed_topics"),
        func.coalesce(func.avg(Progress.score).filter(Topic.archived_at.is_(None)), 0).label("average_score"),
    ).outerjoin(Progress, Progress.student_id == Student.id).outerjoin(Topic, Topic.id == Progress.topic_id)
    if visible_ids is not None:
        statement = statement.where(Student.id.in_(visible_ids))
    rows = (await db.execute(statement.group_by(Student.id).order_by(Student.name))).all()
    return [serialize_student_summary(row) for row in rows]


async def get_student_learning_report(student_id: int, db: AsyncSession, *, user: AuthPrincipal) -> dict[str, Any]:
    visible_ids = await _visible_student_ids(db, user)
    if visible_ids is not None and student_id not in visible_ids:
        raise ApplicationError(404, "Ученик недоступен.")
    student = await db.get(Student, student_id)
    if student is None:
        raise ApplicationError(404, "Ученик не найден.")
    skills = (await db.execute(select(StudentSkillMastery, Skill).join(Skill, Skill.id == StudentSkillMastery.skill_id)
        .where(StudentSkillMastery.student_id == student_id, StudentSkillMastery.evidence_count > 0)
        .order_by(Skill.name))).all()
    lessons = (await db.execute(select(Progress, Topic).join(Topic, Topic.id == Progress.topic_id)
        .where(Progress.student_id == student_id).order_by(Topic.sort_order, Topic.id))).all()
    return {"student_id": student_id, "name": student.name,
            "skills": [{"id": skill.id, "name": skill.name, "status": mastery.status,
                        "mastery_score": mastery.mastery_score, "evidence_count": mastery.evidence_count} for mastery, skill in skills],
            "lessons": [{"topic_id": topic.id, "name": topic.name, "status": progress.status,
                         "mastery_status": progress.mastery_status, "score": progress.score,
                         "archived": topic.archived_at is not None} for progress, topic in lessons]}
