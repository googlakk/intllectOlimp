"""Durable generation markers with bounded, explicitly requested background work.

No worker is restarted automatically: an interrupted job expires as failed.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal
from languages import LANGUAGES
from models import GeneratedLesson, Teacher, Topic
from services.lessons import LessonServiceError, attach_lesson_document, generate_lesson_draft, serialize_lesson

logger = logging.getLogger(__name__)
GENERATION_TIMEOUT_SECONDS = 900
STALE_GRACE_SECONDS = 30
MAX_BATCH_TOPICS = 30
WORKER_TOKEN = str(uuid4())
ACTIVE_STATUSES = {"queued", "running"}
_generation_slots = asyncio.Semaphore(2)
_tasks: set[asyncio.Task] = set()


def marker_for(lesson: GeneratedLesson | None) -> dict[str, Any]:
    marker = (lesson.lesson_metadata or {}).get("generation_job") if lesson else None
    return dict(marker) if isinstance(marker, dict) else {}


def marker_expired(marker: dict[str, Any], now: datetime | None = None) -> bool:
    if marker.get("worker_token") and marker["worker_token"] != WORKER_TOKEN:
        return True
    try:
        deadline = datetime.fromisoformat(marker["deadline_at"])
        return deadline <= (now or datetime.now(timezone.utc))
    except (KeyError, TypeError, ValueError):
        return True


def write_marker(lesson: GeneratedLesson, marker: dict[str, Any]) -> None:
    metadata = dict(lesson.lesson_metadata or {})
    previous = marker_for(lesson)
    if previous.get("batch_id") and previous.get("job_id") != marker.get("job_id"):
        if previous.get("status") in ACTIVE_STATUSES:
            previous = {**previous, "status": "failed",
                        "error": "Создание урока прервано. Повторите запуск вручную."}
        history = {batch_id: compact_batch_marker(item)
                   for batch_id, item in (metadata.get("generation_batch_history") or {}).items()}
        history[previous["batch_id"]] = compact_batch_marker(previous)
        metadata["generation_batch_history"] = history
    lesson.lesson_metadata = {**metadata, "generation_job": marker}


def compact_batch_marker(marker: dict[str, Any]) -> dict[str, Any]:
    """Retain replay identity/status, without obsolete worker fences or deadlines."""
    keys = {"batch_id", "job_id", "status", "created_at", "topic_ids", "topic_names",
            "request", "error", "finished_at"}
    return {key: value for key, value in marker.items() if key in keys}


def job_payload(lesson: GeneratedLesson) -> dict[str, Any]:
    marker = marker_for(lesson)
    payload = {"job_id": marker["job_id"], "topic_id": lesson.topic_id, "status": marker["status"]}
    if marker.get("error"):
        payload["error"] = marker["error"]
    if marker["status"] == "succeeded":
        payload["lesson"] = serialize_lesson(lesson)
    return payload


async def locked_lesson(topic_id: int, db: AsyncSession) -> GeneratedLesson | None:
    topic = await db.scalar(select(Topic).where(Topic.id == topic_id).with_for_update())
    if topic is None:
        raise LessonServiceError(404, "Тема не найдена")
    if topic.archived_at:
        raise LessonServiceError(409, "Сначала восстановите тему из архива")
    return await db.scalar(select(GeneratedLesson).where(GeneratedLesson.topic_id == topic_id)
                           .execution_options(populate_existing=True).with_for_update())


async def start_generation_job(
    topic_id: int, teacher_id: int, db: AsyncSession, *, model_choice: str | None = None,
    content_language: str | None = None, request_id: str | None = None,
    dispatch: bool = True,
) -> dict[str, Any]:
    from llm.catalog import ModelChoiceError, resolve_lesson_choice

    if content_language is not None and content_language not in LANGUAGES:
        raise LessonServiceError(422, "Выберите русский, кыргызский или английский язык урока.")
    try:
        resolve_lesson_choice(model_choice)
    except ModelChoiceError as exc:
        raise LessonServiceError(422, str(exc)) from exc
    if await db.get(Teacher, teacher_id) is None:
        raise LessonServiceError(404, "Преподаватель не найден")
    lesson = await locked_lesson(topic_id, db)
    marker = marker_for(lesson)
    if marker.get("status") in ACTIVE_STATUSES and marker_expired(marker):
        marker = {**marker, "status": "failed", "error": "Создание урока прервано или превысило время ожидания. Повторите запуск вручную."}
        write_marker(lesson, marker)
    if marker and ((request_id and marker.get("request_id") == request_id) or marker.get("status") in ACTIVE_STATUSES):
        if not dispatch:
            raise LessonServiceError(409, "Для темы уже создаётся урок. Дождитесь завершения.")
        await db.commit()
        if marker.get("status") == "succeeded":
            await attach_lesson_document(lesson, db, hydrate_assets=False)
        return job_payload(lesson)
    if lesson is None:
        lesson = GeneratedLesson(topic_id=topic_id, blocks=[], lesson_metadata={}, status="draft")
        db.add(lesson)
    now = datetime.now(timezone.utc)
    job_id = str(uuid4())
    write_marker(lesson, {
        "job_id": job_id, "request_id": request_id, "status": "queued" if dispatch else "running",
        "worker_token": WORKER_TOKEN,
        "started_at": now.isoformat(),
        "deadline_at": (now + timedelta(seconds=GENERATION_TIMEOUT_SECONDS * MAX_BATCH_TOPICS + STALE_GRACE_SECONDS)).isoformat(),
        "base_version_id": lesson.active_version_id,
        "base_published_version_id": lesson.published_version_id,
    })
    await db.commit()
    if dispatch:
        dispatch_generation_job(job_id, topic_id, teacher_id, model_choice, content_language)
    return job_payload(lesson)


async def generation_job_status(job_id: str, topic_id: int, db: AsyncSession) -> dict[str, Any]:
    # GET normally needs no lock. Only expired markers need a serialized update.
    lesson = await db.scalar(select(GeneratedLesson).where(GeneratedLesson.topic_id == topic_id))
    marker = marker_for(lesson)
    if marker.get("job_id") != job_id:
        raise LessonServiceError(404, "Задание создания урока не найдено")
    if marker.get("status") in ACTIVE_STATUSES and marker_expired(marker):
        lesson = await locked_lesson(topic_id, db)
        marker = marker_for(lesson)
        if marker.get("job_id") != job_id:
            raise LessonServiceError(404, "Задание создания урока не найдено")
        if marker.get("status") in ACTIVE_STATUSES and marker_expired(marker):
            write_marker(lesson, {**marker, "status": "failed", "error": "Создание урока прервано или превысило время ожидания. Повторите запуск вручную."})
            await db.commit()
    if marker_for(lesson).get("status") == "succeeded":
        await attach_lesson_document(lesson, db, hydrate_assets=False)
    return job_payload(lesson)


async def fail_generation_job(job_id: str, topic_id: int, error: str) -> None:
    async with AsyncSessionLocal() as db:
        lesson = await db.scalar(select(GeneratedLesson).where(GeneratedLesson.topic_id == topic_id).with_for_update())
        marker = marker_for(lesson)
        if marker.get("job_id") == job_id and marker.get("status") in ACTIVE_STATUSES:
            write_marker(lesson, {**marker, "status": "failed", "error": error,
                                  "finished_at": datetime.now(timezone.utc).isoformat()})
            await db.commit()


def dispatch_generation_job(job_id: str, topic_id: int, teacher_id: int,
                            model_choice: str | None, content_language: str | None) -> None:
    task = asyncio.create_task(run_generation_job(job_id, topic_id, teacher_id, model_choice, content_language))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


def generation_slot() -> asyncio.Semaphore:
    """The legacy synchronous API and all background workers share this pool."""
    return _generation_slots


async def claim_generation_job(job_id: str, topic_id: int) -> bool:
    """A cancelled, replaced, expired or revised reservation never calls a provider."""
    async with AsyncSessionLocal() as db:
        lesson = await locked_lesson(topic_id, db)
        marker = marker_for(lesson)
        if marker.get("job_id") != job_id or marker.get("status") != "queued":
            return False
        if marker_expired(marker):
            write_marker(lesson, {**marker, "status": "failed", "error": "Создание урока прервано. Повторите запуск вручную."})
            await db.commit()
            return False
        if marker.get("base_version_id") != lesson.active_version_id or marker.get("base_published_version_id") != lesson.published_version_id:
            write_marker(lesson, {**marker, "status": "failed", "error": "Урок изменён в очереди. Изменения сохранены; повторите запуск вручную."})
            await db.commit()
            return False
        now = datetime.now(timezone.utc)
        write_marker(lesson, {**marker, "status": "running", "started_at": now.isoformat(),
                              "deadline_at": (now + timedelta(seconds=GENERATION_TIMEOUT_SECONDS + STALE_GRACE_SECONDS)).isoformat()})
        await db.commit()
        return True


async def run_generation_job(job_id: str, topic_id: int, teacher_id: int,
                             model_choice: str | None, content_language: str | None) -> None:
    async with _generation_slots:
        await _run_generation_job(job_id, topic_id, teacher_id, model_choice, content_language)


async def _run_generation_job(job_id: str, topic_id: int, teacher_id: int,
                              model_choice: str | None, content_language: str | None) -> None:
    error = None
    try:
        if not await claim_generation_job(job_id, topic_id):
            return
        async with AsyncSessionLocal() as db:
            await asyncio.wait_for(generate_lesson_draft(
                topic_id, teacher_id, db, model_choice=model_choice,
                content_language=content_language, generation_job_id=job_id,
            ), timeout=GENERATION_TIMEOUT_SECONDS)
    except TimeoutError:
        error = "Создание урока заняло слишком много времени. Повторите запуск вручную."
    except asyncio.CancelledError:
        error = "Создание урока прервано при остановке сервера. Повторите запуск вручную."
    except Exception as exc:
        # Provider exception text may contain private request data. Persist only
        # a safe user-facing message, while logging the exception class.
        logger.warning("Lesson generation job failed: %s", type(exc).__name__)
        error = "Не удалось создать урок. Существующие материалы сохранены. Повторите запуск вручную."
    if error:
        try:
            await fail_generation_job(job_id, topic_id, error)
        except Exception as exc:
            logger.warning("Lesson generation failure marker unavailable: %s", type(exc).__name__)
            # Durable running marker expires even when this write is unavailable.
