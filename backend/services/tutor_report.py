"""Помощник в отчёте учителя: что спрашивал ученик, где застревал, когда звал взрослого.

Сводка считается в Python по последним репликам ученика — на пилоте их немного.
Если журнала нет (таблица не создана или база недоступна), отчёт честно говорит
«нет данных», а остальной отчёт об ученике работает как раньше.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime
from typing import Any, Iterable, Protocol

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from models import Topic
from services.auth import AuthPrincipal
from services.dashboard import ensure_student_visible
from tutor.models import TutorTurn

logger = logging.getLogger(__name__)

SUMMARY_TURNS = 2000
DIALOGUE_TURNS = 500
TOP_MISCONCEPTIONS = 5
ALERTS_LIMIT = 20


class TutorReportStore(Protocol):
    async def student_turns(self, student_id: int, topic_id: int | None, limit: int) -> list[TutorTurn]: ...
    async def topic_names(self, topic_ids: Iterable[int]) -> dict[int, str]: ...


class SqlTutorReportStore:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def student_turns(self, student_id: int, topic_id: int | None, limit: int) -> list[TutorTurn]:
        query = select(TutorTurn).where(TutorTurn.student_id == student_id)
        if topic_id is not None:
            query = query.where(TutorTurn.topic_id == topic_id)
        # Последние реплики, по порядку времени.
        return list(reversed((await self.db.scalars(query.order_by(TutorTurn.id.desc()).limit(limit))).all()))

    async def topic_names(self, topic_ids: Iterable[int]) -> dict[int, str]:
        ids = sorted(set(topic_ids))
        if not ids:
            return {}
        rows = (await self.db.execute(select(Topic.id, Topic.name).where(Topic.id.in_(ids)))).all()
        return {row.id: row.name for row in rows}


def _spoke(turn: TutorTurn) -> bool:
    """Реплика, которую видел ученик или написал он сам (молчание не считаем)."""
    return bool(turn.reply or turn.student_text)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def summarize_turns(turns: list[TutorTurn], topic_names: dict[int, str]) -> dict[str, Any]:
    topics: dict[int, dict[str, Any]] = {}
    misconceptions: Counter[str] = Counter()
    alerts: list[dict[str, Any]] = []
    for turn in turns:
        if not _spoke(turn):
            continue
        row = topics.setdefault(turn.topic_id, {
            "topic_id": turn.topic_id, "name": topic_names.get(turn.topic_id, f"Тема {turn.topic_id}"),
            "turns": 0, "messages": 0, "hints": 0, "leaks_blocked": 0, "teacher_calls": 0, "safety_flags": 0,
            "last_at": None,
        })
        row["turns"] += 1
        row["messages"] += turn.event == "message"
        # Подсказкой считаем выданную помощь, а не отказ по лимиту или запасную фразу.
        row["hints"] += turn.reply_source == "hint" or (turn.event == "hint_requested" and turn.reply_source in {"llm", "guard"})
        row["leaks_blocked"] += bool(turn.leak_blocked)
        row["teacher_calls"] += turn.action == "call_teacher"
        row["safety_flags"] += turn.safety_flag not in (None, "none")
        row["last_at"] = _iso(turn.created_at) or row["last_at"]
        if turn.misconception_code:
            misconceptions[turn.misconception_code] += 1
        if turn.safety_flag == "distress" or turn.action == "call_teacher":
            alerts.append({
                "topic_id": turn.topic_id, "turn_id": turn.id, "created_at": _iso(turn.created_at),
                "kind": "distress" if turn.safety_flag == "distress" else "call_teacher",
                "student_text": turn.student_text,
            })
    return {
        "available": True,
        "topics": sorted(topics.values(), key=lambda row: row["last_at"] or "", reverse=True),
        "misconceptions": [{"code": code, "count": count} for code, count in misconceptions.most_common(TOP_MISCONCEPTIONS)],
        # Сначала самые свежие: учителю важно, что случилось недавно.
        "alerts": list(reversed(alerts))[:ALERTS_LIMIT],
    }


def serialize_dialogue(turns: list[TutorTurn]) -> list[dict[str, Any]]:
    """Диалог для учителя: реплики и служебные пометки, которых ученик не видит (диагноз, утечки)."""
    return [
        {
            "id": turn.id, "created_at": _iso(turn.created_at), "lesson_version_id": turn.lesson_version_id,
            "block_index": turn.block_index, "question_index": turn.question_index, "event": turn.event,
            "student_text": turn.student_text, "student_value": turn.student_value, "check_outcome": turn.check_outcome,
            "reply": turn.reply, "source": turn.reply_source, "action": turn.action,
            "misconception_code": turn.misconception_code, "diagnosis": turn.diagnosis,
            "safety_flag": turn.safety_flag, "off_topic": bool(turn.off_topic), "leak_blocked": bool(turn.leak_blocked),
        }
        for turn in turns if _spoke(turn)
    ]


async def _read(db: AsyncSession, action: Any) -> Any:
    try:
        return await action
    except SQLAlchemyError as exc:
        logger.warning("Tutor report unavailable: %s", exc.__class__.__name__)
        await db.rollback()
        return None


async def get_student_tutor_summary(
    student_id: int, db: AsyncSession, *, user: AuthPrincipal, store: TutorReportStore | None = None,
) -> dict[str, Any]:
    await ensure_student_visible(db, user, student_id)
    store = store or SqlTutorReportStore(db)
    turns = await _read(db, store.student_turns(student_id, None, SUMMARY_TURNS))
    if turns is None:
        return {"available": False, "topics": [], "misconceptions": [], "alerts": []}
    # Без отката: он сбросил бы уже загруженные реплики. Нет названий — покажем номера тем.
    try:
        names = await store.topic_names(turn.topic_id for turn in turns)
    except SQLAlchemyError as exc:
        logger.warning("Tutor report topic names unavailable: %s", exc.__class__.__name__)
        names = {}
    return summarize_turns(turns, names)


async def get_student_tutor_dialogue(
    student_id: int, topic_id: int, db: AsyncSession, *, user: AuthPrincipal, store: TutorReportStore | None = None,
) -> dict[str, Any]:
    await ensure_student_visible(db, user, student_id)
    store = store or SqlTutorReportStore(db)
    turns = await _read(db, store.student_turns(student_id, topic_id, DIALOGUE_TURNS))
    if turns is None:
        return {"available": False, "topic_id": topic_id, "turns": []}
    return {"available": True, "topic_id": topic_id, "turns": serialize_dialogue(turns)}
