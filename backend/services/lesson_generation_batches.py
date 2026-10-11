"""Background batches persisted in existing lesson JSON; no paid automatic retry."""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from languages import LANGUAGES
from models import GeneratedLesson, Section, Subject, Teacher, Topic
from services.auth import AuthPrincipal
from services.educator_access import require_subject_management, require_topic_management
from services.lessons import LessonServiceError
from services import lesson_generation_jobs as jobs


def batch_markers(lesson: GeneratedLesson) -> list[dict[str, Any]]:
    history = (lesson.lesson_metadata or {}).get("generation_batch_history") or {}
    markers = list(history.values()) if isinstance(history, dict) else []
    current = jobs.marker_for(lesson)
    if current.get("batch_id"):
        markers.append(current)
    return [marker for marker in markers if isinstance(marker, dict)]


def batch_index(rows: list[GeneratedLesson]) -> dict[str, dict[int, tuple[GeneratedLesson, dict[str, Any]]]]:
    groups: dict[str, dict[int, tuple[GeneratedLesson, dict[str, Any]]]] = {}
    for row in rows:
        for marker in batch_markers(row):
            groups.setdefault(marker["batch_id"], {})[row.topic_id] = (row, marker)
    return groups


def batch_payload(batch_id: str, subject_id: int, rows: list[GeneratedLesson], *,
                  index: dict[str, dict[int, tuple[GeneratedLesson, dict[str, Any]]]] | None = None) -> dict[str, Any]:
    found = (index if index is not None else batch_index(rows)).get(batch_id, {})
    if not found:
        raise LessonServiceError(404, "Очередь создания уроков не найдена")
    sample = next(iter(found.values()))[1]
    items = []
    for topic_id in sample["topic_ids"]:
        row, marker = found.get(topic_id, (None, {}))
        item = {"job_id": marker.get("job_id"), "topic_id": topic_id,
                "topic_name": sample.get("topic_names", {}).get(str(topic_id), f"Тема {topic_id}"),
                "status": marker.get("status", "failed"), "lesson_id": row.id if row else None}
        if marker.get("error"):
            item["error"] = marker["error"]
        elif row is None:
            item["error"] = "Тема или запись задания была удалена."
        items.append(item)
    counts = {status: sum(item["status"] == status for item in items)
              for status in ("queued", "running", "succeeded", "failed", "cancelled")}
    if counts["running"]:
        status = "running"
    elif counts["queued"]:
        status = "queued"
    elif counts["succeeded"] == len(items):
        status = "succeeded"
    elif counts["cancelled"] == len(items):
        status = "cancelled"
    elif counts["succeeded"]:
        status = "partial_failed"
    elif counts["failed"]:
        status = "failed"
    else:
        status = "cancelled"
    return {"batch_id": batch_id, "subject_id": subject_id, "created_at": sample["created_at"],
            "status": status, "total": len(items), "counts": counts, "items": items}


async def subject_batch_rows(subject_id: int, db: AsyncSession) -> list[GeneratedLesson]:
    return list((await db.scalars(select(GeneratedLesson)
        .options(load_only(GeneratedLesson.id, GeneratedLesson.topic_id, GeneratedLesson.lesson_metadata))
        .join(Topic, GeneratedLesson.topic_id == Topic.id)
        .join(Section, Topic.section_id == Section.id)
        .where(Section.subject_id == subject_id)
        .execution_options(populate_existing=True))).all())


async def expire_batch_jobs(rows: list[GeneratedLesson], db: AsyncSession) -> None:
    for row in sorted(rows, key=lambda item: item.topic_id):
        marker = jobs.marker_for(row)
        if marker.get("status") not in jobs.ACTIVE_STATUSES or not jobs.marker_expired(marker):
            continue
        # Re-read under the topic/lesson lock; a completion may have won the race.
        locked = await db.scalar(select(GeneratedLesson).where(GeneratedLesson.topic_id == row.topic_id)
                                 .execution_options(populate_existing=True).with_for_update())
        current = jobs.marker_for(locked)
        if current.get("job_id") == marker.get("job_id") and current.get("status") in jobs.ACTIVE_STATUSES and jobs.marker_expired(current):
            jobs.write_marker(locked, {**current, "status": "failed",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "error": "Создание урока прервано или превысило время ожидания. Повторите запуск вручную."})
    await db.commit()


async def list_generation_batches(subject_id: int, user: AuthPrincipal, db: AsyncSession) -> list[dict[str, Any]]:
    await require_subject_management(user, subject_id, db)
    rows = await subject_batch_rows(subject_id, db)
    await expire_batch_jobs(rows, db)
    index = batch_index(rows)
    ordered = sorted((batch_payload(batch_id, subject_id, rows, index=index) for batch_id in index),
                     key=lambda batch: batch["created_at"], reverse=True)
    active = [batch for batch in ordered if batch["status"] in jobs.ACTIVE_STATUSES]
    terminal = [batch for batch in ordered if batch["status"] not in jobs.ACTIVE_STATUSES]
    return active + terminal[:3]


async def generation_batch_status(batch_id: str, subject_id: int, user: AuthPrincipal, db: AsyncSession) -> dict[str, Any]:
    await require_subject_management(user, subject_id, db)
    rows = await subject_batch_rows(subject_id, db)
    await expire_batch_jobs(rows, db)
    return batch_payload(batch_id, subject_id, rows)


async def start_generation_batch(subject_id: int, topic_ids: list[int], teacher_id: int,
                                 request_id: str, user: AuthPrincipal, db: AsyncSession, *,
                                 model_choice: str | None = None, content_language: str | None = None,
                                 replace_existing_drafts: bool = False, dispatch: bool = True) -> dict[str, Any]:
    from llm.catalog import ModelChoiceError, resolve_lesson_choice
    if not topic_ids or len(topic_ids) > jobs.MAX_BATCH_TOPICS or len(set(topic_ids)) != len(topic_ids) or any(item < 1 for item in topic_ids):
        raise LessonServiceError(422, "Выберите от 1 до 30 разных тем")
    await require_subject_management(user, subject_id, db)
    # Authorization of the entire selection happens before reservations or dispatch.
    topics = [await require_topic_management(user, topic_id, db) for topic_id in topic_ids]
    for topic in topics:
        section = await db.get(Section, topic.section_id)
        if section.subject_id != subject_id:
            raise LessonServiceError(422, "Все темы должны принадлежать выбранному предмету")
    if content_language is not None and content_language not in LANGUAGES:
        raise LessonServiceError(422, "Выберите русский, кыргызский или английский язык урока.")
    try:
        resolve_lesson_choice(model_choice)
    except ModelChoiceError as exc:
        raise LessonServiceError(422, str(exc)) from exc
    if await db.get(Teacher, teacher_id) is None:
        raise LessonServiceError(404, "Преподаватель не найден")
    # Subject lock serializes same request IDs even when the selected topics differ.
    await db.scalar(select(Subject).where(Subject.id == subject_id).with_for_update())
    rows = await subject_batch_rows(subject_id, db)
    fingerprint = {"topic_ids": sorted(topic_ids), "teacher_id": teacher_id,
                   "model": model_choice, "content_language": content_language,
                   "replace_existing_drafts": replace_existing_drafts}
    previous = next((marker for row in rows for marker in batch_markers(row)
                     if marker.get("batch_id") == request_id), None)
    if previous:
        if previous.get("request") != fingerprint:
            raise LessonServiceError(409, "Этот запрос уже использован для другой очереди. Обновите страницу и повторите выбор.")
        await expire_batch_jobs(rows, db)
        return batch_payload(request_id, subject_id, rows)
    reserved = []
    topics_by_id = {topic.id: topic for topic in topics}
    # Deterministic topic locks match single generation and final-save fencing.
    for topic_id in sorted(topic_ids):
        row = await jobs.locked_lesson(topic_id, db)
        topic = topics_by_id[topic_id]
        if not (topic.learning_objectives or "").strip():
            raise LessonServiceError(422, f"В теме «{topic.name}» сначала заполните цели КТП")
        marker = jobs.marker_for(row)
        if marker.get("status") in jobs.ACTIVE_STATUSES and not jobs.marker_expired(marker):
            raise LessonServiceError(409, f"Для темы «{topic.name}» урок уже создаётся")
        if row and (row.status == "published" or row.published_version_id):
            raise LessonServiceError(409, f"Урок «{topic.name}» опубликован. Он не будет заменён очередью.")
        if row and (row.blocks or row.active_version_id) and not replace_existing_drafts:
            raise LessonServiceError(409, f"В теме «{topic.name}» уже есть материалы. Подтвердите замену черновиков.")
        reserved.append(row or GeneratedLesson(topic_id=topic_id, blocks=[], lesson_metadata={}, status="draft"))
    now = datetime.now(timezone.utc)
    for row in reserved:
        if row.id is None:
            db.add(row)
        jobs.write_marker(row, {"job_id": str(uuid4()), "batch_id": request_id, "request_id": request_id,
            "status": "queued", "worker_token": jobs.WORKER_TOKEN, "created_at": now.isoformat(),
            "deadline_at": (now + timedelta(seconds=jobs.GENERATION_TIMEOUT_SECONDS * jobs.MAX_BATCH_TOPICS + jobs.STALE_GRACE_SECONDS)).isoformat(),
            "topic_ids": topic_ids, "topic_names": {str(topic.id): topic.name for topic in topics},
            "request": fingerprint, "base_version_id": row.active_version_id,
            "base_published_version_id": row.published_version_id})
    # Commit all reservations atomically before any external work begins.
    await db.commit()
    if dispatch:
        for row in reserved:
            jobs.dispatch_generation_job(jobs.marker_for(row)["job_id"], row.topic_id, teacher_id, model_choice, content_language)
    return batch_payload(request_id, subject_id, reserved)


async def cancel_generation_batch(batch_id: str, subject_id: int, user: AuthPrincipal, db: AsyncSession) -> dict[str, Any]:
    await require_subject_management(user, subject_id, db)
    rows = await subject_batch_rows(subject_id, db)
    batch_payload(batch_id, subject_id, rows)  # Unknown ID is not a silent success.
    for row in sorted(rows, key=lambda item: item.topic_id):
        if jobs.marker_for(row).get("batch_id") != batch_id:
            continue
        locked = await db.scalar(select(GeneratedLesson).where(GeneratedLesson.topic_id == row.topic_id)
                                 .execution_options(populate_existing=True).with_for_update())
        marker = jobs.marker_for(locked)
        if marker.get("batch_id") == batch_id and marker.get("status") == "queued":
            jobs.write_marker(locked, {**marker, "status": "cancelled", "finished_at": datetime.now(timezone.utc).isoformat()})
    await db.commit()
    return batch_payload(batch_id, subject_id, rows)
