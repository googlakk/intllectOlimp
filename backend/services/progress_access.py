"""Subject scope for educator reads of raw progress and saved attempt answers."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Progress, Section, Topic
from services.auth import AuthPrincipal
from services.progress import ProgressServiceError, list_student_progress, serialize_progress
from services.teacher_assignments import teacher_subject_ids


async def list_visible_student_progress(student_id: int, db: AsyncSession, *, user: AuthPrincipal) -> list[dict]:
    # The route has already checked student/class visibility. A teacher additionally needs the exact subject.
    if user.role != "teacher":
        return await list_student_progress(student_id, db)
    subjects = await teacher_subject_ids(user, db)
    rows = (await db.execute(
        select(Progress, Topic.name, Topic.archived_at)
        .join(Topic, Topic.id == Progress.topic_id)
        .join(Section, Section.id == Topic.section_id)
        .where(Progress.student_id == student_id, Section.subject_id.in_(subjects))
    )).all()
    return [{**serialize_progress(row), "topic_name": name, "archived_at": archived_at}
            for row, name, archived_at in rows]


async def require_progress_topic_visibility(topic_id: int, db: AsyncSession, *, user: AuthPrincipal) -> None:
    if user.role != "teacher":
        return
    subjects = await teacher_subject_ids(user, db)
    topic = await db.scalar(select(Topic.id).join(Section, Section.id == Topic.section_id)
                            .where(Topic.id == topic_id, Section.subject_id.in_(subjects)))
    if topic is None:
        raise ProgressServiceError(404, "Урок недоступен.")
