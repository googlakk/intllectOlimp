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
from services.avatar import refresh_avatar_job

logger = logging.getLogger(__name__)

POLL_SEC = int(os.getenv("AVATAR_POLL_SEC", "30"))
# Старше недели не опрашиваем вечно; неделя подхватывает и задания, зависшие без открытого редактора.
MAX_AGE = timedelta(days=7)


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
