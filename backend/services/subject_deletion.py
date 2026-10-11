"""Delete an unused program without deleting student history or textbook files."""

from sqlalchemy import delete, or_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from errors import ApplicationError
from feedback.models import LessonFeedback
from models import (
    GeneratedLesson, GenerationJob, LessonAttempt, LessonVersion, Progress,
    Section, StudentSkillMastery, StudentTopicAccess, Subject, Teacher, Topic,
    WarpGateEvent,
)
from services.catalog import clear_subject_outline_cache
from textbooks.models import Textbook
from tutor.models import TutorTurn


class SubjectDeletionError(ApplicationError):
    pass


HISTORY_MESSAGE = "КТП нельзя удалить: у программы есть результаты или история учеников. Они должны сохраниться."


async def delete_subject(subject_id: int, db: AsyncSession) -> dict[str, bool]:
    try:
        subject = await db.scalar(select(Subject).where(Subject.id == subject_id).with_for_update())
        if subject is None:
            raise SubjectDeletionError(404, "Программа не найдена")

        # Lock the parents of FK inserts before checking history: concurrent
        # progress/attempt inserts cannot slip between the check and deletion.
        section_ids = list((await db.scalars(
            select(Section.id).where(Section.subject_id == subject_id).order_by(Section.id).with_for_update()
        )).all())
        topic_ids = list((await db.scalars(
            select(Topic.id).where(Topic.section_id.in_(section_ids)).order_by(Topic.id).with_for_update()
        )).all())
        lesson_ids = list((await db.scalars(
            select(GeneratedLesson.id).where(GeneratedLesson.topic_id.in_(topic_ids)).order_by(GeneratedLesson.id).with_for_update()
        )).all())
        version_ids = list((await db.scalars(
            select(LessonVersion.id).where(LessonVersion.lesson_id.in_(lesson_ids)).order_by(LessonVersion.id).with_for_update()
        )).all())

        # These optional tables are installed by manual migrations. Absence is
        # safe; an unexpected query failure must still abort the transaction.
        optional_tables = set((await db.scalars(text(
            "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public' "
            "AND tablename IN ('tutor_turns', 'lesson_feedback', 'textbooks')"
        ))).all())
        history_checks = [
            select(Progress.id).where(Progress.topic_id.in_(topic_ids)).exists(),
            select(LessonAttempt.id).where(LessonAttempt.topic_id.in_(topic_ids)).exists(),
            select(StudentSkillMastery.id).where(StudentSkillMastery.source_topic_id.in_(topic_ids)).exists(),
            select(StudentTopicAccess.id).where(
                StudentTopicAccess.topic_id.in_(topic_ids),
                StudentTopicAccess.state.in_(("in_progress", "mastered")),
            ).exists(),
            select(WarpGateEvent.id).where(or_(
                WarpGateEvent.from_topic_id.in_(topic_ids), WarpGateEvent.to_topic_id.in_(topic_ids),
            )).exists(),
        ]
        for model in (TutorTurn, LessonFeedback):
            if model.__tablename__ in optional_tables:
                history_checks.append(select(model.id).where(model.topic_id.in_(topic_ids)).exists())
        if await db.scalar(select(or_(*history_checks))):
            raise SubjectDeletionError(409, HISTORY_MESSAGE)
        if await db.scalar(select(select(GenerationJob.id).where(
            GenerationJob.lesson_version_id.in_(version_ids),
            GenerationJob.status.in_(("queued", "submitted", "processing", "running")),
        ).exists())):
            raise SubjectDeletionError(409, "Для программы создаются материалы. Дождитесь завершения и повторите удаление.")
        running_lessons = (await db.scalars(select(GeneratedLesson).where(
            GeneratedLesson.id.in_(lesson_ids),
            GeneratedLesson.lesson_metadata.op("->")("generation_job").op("->>")("status").in_(("queued", "running")),
        ))).all()
        from services.lesson_generation_jobs import marker_expired, marker_for
        if any(not marker_expired(marker_for(row)) for row in running_lessons):
            raise SubjectDeletionError(409, "Для программы создаётся урок. Дождитесь завершения и повторите удаление.")

        await db.execute(update(Teacher).where(Teacher.subject_id == subject_id).values(subject_id=None))
        if "textbooks" in optional_tables:
            await db.execute(update(Textbook).where(Textbook.subject_id == subject_id).values(subject_id=None))
        # Existing ON DELETE rules remove sections, topics, draft/unused lessons,
        # versions, assets, links and assignments. Book files remain untouched.
        await db.execute(delete(Subject).where(Subject.id == subject_id))
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise SubjectDeletionError(409, "КТП связан с другими данными и не может быть удалён. Ничего не изменено.") from exc
    except Exception:
        await db.rollback()
        raise

    from services.curriculum_graph import clear_curriculum_map_cache
    from services.lessons import clear_lesson_manifest_cache

    clear_subject_outline_cache(subject_id)
    clear_curriculum_map_cache()
    for topic_id in topic_ids:
        clear_lesson_manifest_cache(topic_id)
    return {"deleted": True}
