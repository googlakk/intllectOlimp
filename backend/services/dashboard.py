from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from errors import ApplicationError
from models import Skill, StudentSkillMastery, Classroom, ClassroomStudent, ClassroomTeacher, GeneratedLesson, LessonAttempt, LessonVersion, Progress, Section, Student, Subject, Topic, TopicSkill
from services.auth import AuthPrincipal
from services.teacher_assignments import teacher_subject_ids


async def visible_subject_ids(db: AsyncSession, user: AuthPrincipal) -> list[int] | None:
    """Предметы, результаты по которым видит пользователь: админ — все (None), учитель — назначенные."""
    return None if user.role == "admin" else await teacher_subject_ids(user, db)


def topics_of_subjects(subject_ids: list[int]):
    # correlate(None): подзапрос самостоятельный и не цепляется к темам внешнего запроса.
    return (select(Topic.id).join(Section, Section.id == Topic.section_id)
            .where(Section.subject_id.in_(subject_ids)).correlate(None))


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


def _visible_students_subquery(user: AuthPrincipal):
    """Ученики классов учителя — подзапросом, чтобы не ходить в базу отдельно."""
    return (
        select(ClassroomStudent.student_id)
        .join(ClassroomTeacher, ClassroomTeacher.classroom_id == ClassroomStudent.classroom_id)
        .join(Classroom, Classroom.id == ClassroomStudent.classroom_id)
        .where(ClassroomTeacher.teacher_id == user.teacher_id, ClassroomStudent.left_at.is_(None), Classroom.status == "active")
    )


async def get_dashboard_overview(db: AsyncSession, *, user: AuthPrincipal) -> dict[str, int | float]:
    # Все счётчики — одной командой: на далёкой базе каждый отдельный запрос стоит сотни миллисекунд.
    scoped = user.role != "admin"
    students_query = select(func.count(Student.id))
    completed_query = select(func.count(Progress.id)).join(Topic, Topic.id == Progress.topic_id).join(Section, Section.id == Topic.section_id).join(Subject, Subject.id == Section.subject_id).where(Progress.status == "completed", Topic.archived_at.is_(None))
    subjects_query = select(func.count(Subject.id))
    topics_query = select(func.count(Topic.id)).join(Section, Section.id == Topic.section_id).join(Subject, Subject.id == Section.subject_id).where(Topic.archived_at.is_(None))
    published_query = (
        select(func.count(GeneratedLesson.id))
        .join(Topic, Topic.id == GeneratedLesson.topic_id)
        .join(Section, Section.id == Topic.section_id)
        .join(Subject, Subject.id == Section.subject_id)
        .where(GeneratedLesson.status == "published", Topic.archived_at.is_(None))
    )
    if scoped:
        students_query = students_query.where(Student.id.in_(_visible_students_subquery(user)))
        completed_query = completed_query.where(Progress.student_id.in_(_visible_students_subquery(user)))
        subject_ids = await teacher_subject_ids(user, db)
        subjects_query = subjects_query.where(Subject.id.in_(subject_ids))
        topics_query = topics_query.where(Subject.id.in_(subject_ids))
        completed_query = completed_query.where(Subject.id.in_(subject_ids))
        published_query = published_query.where(Subject.id.in_(subject_ids))
    row = (await db.execute(select(
        students_query.scalar_subquery().label("students"),
        subjects_query.scalar_subquery().label("subjects"),
        topics_query.scalar_subquery().label("topics"),
        published_query.scalar_subquery().label("published"),
        completed_query.scalar_subquery().label("completed"),
    ))).one()
    return build_dashboard_overview(
        students=row.students or 0,
        subjects=row.subjects or 0,
        topics=row.topics or 0,
        published_lessons=row.published or 0,
        completed_lessons=row.completed or 0,
    )


async def get_dashboard_students(db: AsyncSession, *, user: AuthPrincipal) -> list[dict[str, Any]]:
    subject_ids = await visible_subject_ids(db, user)
    # Учитель считает только уроки своих предметов; ученик без них всё равно остаётся в списке.
    progress_join = Progress.student_id == Student.id
    if subject_ids is not None:
        progress_join = and_(progress_join, Progress.topic_id.in_(topics_of_subjects(subject_ids)))
    statement = select(
        Student.id,
        Student.name,
        Student.grade,
        func.count(Progress.id)
        .filter(and_(Progress.status == "completed", Topic.archived_at.is_(None)))
        .label("completed_topics"),
        func.coalesce(func.avg(Progress.score).filter(Topic.archived_at.is_(None)), 0).label("average_score"),
    ).select_from(Student).outerjoin(Progress, progress_join).outerjoin(Topic, Topic.id == Progress.topic_id)
    if user.role != "admin":
        statement = statement.where(Student.id.in_(_visible_students_subquery(user)))
    rows = (await db.execute(statement.group_by(Student.id).order_by(Student.name))).all()
    return [serialize_student_summary(row) for row in rows]


async def ensure_student_visible(db: AsyncSession, user: AuthPrincipal, student_id: int) -> None:
    """Админ видит всех; учитель — только учеников своих активных классов."""
    visible_ids = await _visible_student_ids(db, user)
    if visible_ids is not None and student_id not in visible_ids:
        raise ApplicationError(404, "Ученик недоступен.")


async def _report_student(student_id: int, db: AsyncSession, user: AuthPrincipal) -> Student:
    statement = select(Student).where(Student.id == student_id)
    if user.role != "admin":
        statement = statement.where(Student.id.in_(_visible_students_subquery(user)))
    student = await db.scalar(statement)
    if student is None:
        raise ApplicationError(404, "Ученик недоступен." if user.role != "admin" else "Ученик не найден.")
    return student


async def _latest_completed_snapshots(student_id: int, db: AsyncSession, subject_ids: list[int] | None,
                                      topic_id: int | None = None) -> dict[int, dict[str, Any]]:
    # Select one completed snapshot per topic in one batch; never query attempts per lesson.
    latest = select(LessonAttempt.topic_id, func.max(LessonAttempt.attempt_number).label("number")).where(
        LessonAttempt.student_id == student_id)
    if subject_ids is not None:
        latest = latest.where(LessonAttempt.topic_id.in_(topics_of_subjects(subject_ids)))
    if topic_id is not None:
        latest = latest.where(LessonAttempt.topic_id == topic_id)
    latest = latest.group_by(LessonAttempt.topic_id).subquery()
    rows = (await db.execute(select(LessonAttempt).join(latest, and_(
        LessonAttempt.topic_id == latest.c.topic_id, LessonAttempt.attempt_number == latest.c.number))
        .where(LessonAttempt.student_id == student_id))).scalars().all()
    return {row.topic_id: {**(row.snapshot or {}), "status": "completed", "completed_at": row.completed_at,
                           "lesson_version_id": row.lesson_version_id} for row in rows}


async def get_student_learning_report(student_id: int, db: AsyncSession, *, user: AuthPrincipal) -> dict[str, Any]:
    from services.student_statistics import lesson_row, summarize_lessons

    student = await _report_student(student_id, db, user)
    subject_ids = await visible_subject_ids(db, user)
    subjects_query = select(Subject).where(Subject.grade == student.grade)
    skills_query = (select(StudentSkillMastery, Skill).join(Skill, Skill.id == StudentSkillMastery.skill_id)
        .where(StudentSkillMastery.student_id == student_id, StudentSkillMastery.evidence_count > 0,
               StudentSkillMastery.source_topic_id.is_not(None)))
    lessons_query = (select(Topic, Subject, GeneratedLesson.status, Progress)
        .join(Section, Section.id == Topic.section_id).join(Subject, Subject.id == Section.subject_id)
        .outerjoin(GeneratedLesson, GeneratedLesson.topic_id == Topic.id)
        .outerjoin(Progress, and_(Progress.topic_id == Topic.id, Progress.student_id == student_id))
        .where(or_(and_(Subject.grade == student.grade, Topic.archived_at.is_(None), GeneratedLesson.status == "published"),
                   Progress.id.is_not(None))))
    if subject_ids is not None:
        subjects_query = subjects_query.where(Subject.id.in_(subject_ids))
        # The measured value must itself originate in an assigned subject. A skill's general mapping isn't enough.
        skills_query = skills_query.where(StudentSkillMastery.source_topic_id.in_(topics_of_subjects(subject_ids)))
        lessons_query = lessons_query.where(Subject.id.in_(subject_ids))
    subjects = (await db.execute(subjects_query.order_by(Subject.name, Subject.grade, Subject.id))).scalars().all()
    skills = (await db.execute(skills_query.order_by(Skill.name))).all()
    rows = (await db.execute(lessons_query.order_by(
        Subject.name, Subject.grade, Subject.id, Section.sort_order, Topic.sort_order, Topic.id))).all()
    latest = await _latest_completed_snapshots(student_id, db, subject_ids)
    lessons = [lesson_row(topic, subject, status == "published", progress, latest.get(topic.id), student.grade)
               for topic, subject, status, progress in rows]
    return {
        "student_id": student_id, "name": student.name, "grade": student.grade,
        "skills": [{"id": skill.id, "name": skill.name, "status": mastery.status,
                    "mastery_score": mastery.mastery_score, "evidence_count": mastery.evidence_count,
                    "source_topic_id": mastery.source_topic_id} for mastery, skill in skills],
        "lessons": lessons, "summary": summarize_lessons(lessons),
        "subjects": [{"id": subject.id, "name": subject.name, "grade": subject.grade,
                      "summary": summarize_lessons([lesson for lesson in lessons if lesson["subject_id"] == subject.id])}
                     for subject in subjects],
    }


async def get_student_lesson_report(student_id: int, topic_id: int, db: AsyncSession, *, user: AuthPrincipal) -> dict[str, Any]:
    from services.student_statistics import build_attempt_detail, progress_snapshot

    await _report_student(student_id, db, user)
    subject_ids = await visible_subject_ids(db, user)
    query = (select(Topic).join(Section, Section.id == Topic.section_id).where(Topic.id == topic_id))
    if subject_ids is not None:
        query = query.where(Section.subject_id.in_(subject_ids))
    topic = await db.scalar(query)
    if topic is None:
        raise ApplicationError(404, "Урок недоступен.")
    progress = await db.scalar(select(Progress).where(Progress.student_id == student_id, Progress.topic_id == topic_id))
    latest = await _latest_completed_snapshots(student_id, db, subject_ids, topic_id)
    current = progress_snapshot(progress) if progress else None
    previous = latest.get(topic_id) if current and current.get("status") != "completed" else None
    version_ids = {snapshot["lesson_version_id"] for snapshot in (current, previous)
                   if snapshot and snapshot.get("lesson_version_id")}
    documents, lesson_types = {}, {}
    if version_ids:
        versions = (await db.execute(select(LessonVersion).join(GeneratedLesson, GeneratedLesson.id == LessonVersion.lesson_id)
                                    .where(LessonVersion.id.in_(version_ids), GeneratedLesson.topic_id == topic_id))).scalars().all()
        documents = {version.id: version.lesson_document for version in versions if version.lesson_document}
        lesson_types = {version.id: (getattr(version, "blueprint", None) or {}).get("lesson_type") for version in versions}
    def detail_for(snapshot):
        if not snapshot:
            return None
        version_id = snapshot.get("lesson_version_id")
        server_graded = (lesson_types.get(version_id) or getattr(topic, "lesson_type", None)) == "assessment"
        return build_attempt_detail(snapshot, documents.get(version_id), server_graded=server_graded)
    return {"student_id": student_id, "topic_id": topic_id, "name": topic.name,
            "current": detail_for(current), "last_completed": detail_for(previous)}
