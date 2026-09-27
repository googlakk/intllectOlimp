"""Фоновый опрос HeyGen: видео аватара прикрепляется к уроку, даже если учитель закрыл редактор.

HeyGen делает ролик несколько минут. Раньше статус проверял только открытый редактор (раз в 8 с):
закрыл вкладку — задание так и оставалось «в работе», и видео в урок не попадало.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from database import AsyncSessionLocal
from models import GenerationJob
from services.avatar import AvatarServiceError, refresh_avatar_job

logger = logging.getLogger(__name__)

POLL_SEC = int(os.getenv("AVATAR_POLL_SEC", "30"))
# Старше недели не опрашиваем вечно; неделя подхватывает и задания, зависшие без открытого редактора.
MAX_AGE = timedelta(days=7)


# Урока или версии нет, тема в архиве, документ урока не проходит проверку: повтор не поможет —
# задание закрываем с понятной причиной,
# учитель увидит её в редакторе («Не удалось создать»), а опрос не повторяет его каждые 30 с.
PERMANENT_ERRORS = frozenset({404, 409, 422})


async def _mark_failed(db, job_id: int, message: str) -> None:
    job = await db.get(GenerationJob, job_id)
    if job is None or job.status not in ("submitted", "processing"):
        return
    now = datetime.now(timezone.utc)
    job.status = "failed"
    job.error = {"message": message}
    job.completed_at = now
    job.updated_at = now
    await db.commit()


async def poll_pending_avatar_jobs() -> int:
    """Проверить незавершённые задания; вернуть, сколько опрошено."""
    async with AsyncSessionLocal() as db:
        since = datetime.now(timezone.utc) - MAX_AGE
        job_ids = list((await db.scalars(select(GenerationJob.id).where(
            GenerationJob.provider == "heygen",
            GenerationJob.job_type == "avatar_video",
            GenerationJob.status.in_(("submitted", "processing")),
            GenerationJob.created_at >= since,
        ).order_by(GenerationJob.id))).all())
    for job_id in job_ids:
        # Своя сессия на задание: сбой одного не мешает остальным.
        async with AsyncSessionLocal() as db:
            try:
                await refresh_avatar_job(job_id, db)
            except AvatarServiceError as exc:
                await db.rollback()
                logger.warning("Avatar job %s refresh failed: %s %s", job_id, exc.status_code, exc.detail)
                if exc.status_code in PERMANENT_ERRORS:
                    await _mark_failed(db, job_id, str(exc.detail))
            except Exception as exc:  # временный сбой HeyGen или хранилища — попробуем в следующий раз
                logger.warning("Avatar job %s refresh failed: %s", job_id, exc.__class__.__name__)
                await db.rollback()
    return len(job_ids)


async def run_avatar_poller(stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await poll_pending_avatar_jobs()
        except Exception as exc:  # база недоступна — не роняем приложение, ждём следующего круга
            logger.warning("Avatar poller failed: %s", exc.__class__.__name__)
        try:
            await asyncio.wait_for(stop.wait(), timeout=POLL_SEC)
        except asyncio.TimeoutError:
            pass
