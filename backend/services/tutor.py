"""ИИ-тьютор в уроке: один ход диалога.

Урок ведёт маршрут, тьютор помогает внутри шага. Сервер решает всё, что
влияет на правильность: перепроверяет ответ ученика, выбирает, звать ли
модель, не даёт реплике раскрыть ответ и пропускает только команды «назад
к теории» и «позвать учителя». Ошибка модели не ломает урок: ученик
получает готовую фразу.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Protocol

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from errors import ApplicationError
from services.assessment import check_answer
from tutor.context import (
    TurnContext, answer_spec, assessment_mode, authored_hints, lesson_context, nearest_theory_index,
    protected_items, turn_prompt,
)
from tutor.guard import detect_answer_leak, detect_distress, scrub_pii
from tutor.models import TutorTurn
from tutor.policy import BASE_CHARACTER, REPLY_LIMIT, TUTOR_TOOL, grade_profile, lesson_character, template
from tutor.rules import EVENTS, RuleState, decide

logger = logging.getLogger(__name__)

MAX_TOKENS = 700
TIMEOUT_SEC = 20.0
RECENT_TURNS = 20
MODEL_ACTIONS = {"open_theory", "call_teacher"}
LEAK_RETRY_NOTE = (
    "\nВНИМАНИЕ: прошлый вариант реплики раскрывал итоговый ответ. "
    "Дай только следующий шаг или наводящий вопрос, без итогового ответа."
)


class TutorServiceError(ApplicationError):
    pass


@dataclass(frozen=True)
class TutorSettings:
    enabled: bool
    org_ids: frozenset[int] | None
    burst_per_min: int
    max_message_chars: int
    disable_thinking: bool


def _env_int(env: dict[str, str], name: str, default: int, low: int, high: int) -> int:
    try:
        return min(high, max(low, int(str(env.get(name) or default).strip())))
    except ValueError:
        return default


def tutor_settings(env: dict[str, str] | None = None) -> TutorSettings:
    """Тьютор выключен, пока владелец не согласует таблицу и не включит флаг."""
    env = os.environ if env is None else env
    org_ids = {int(item) for item in (env.get("TUTOR_ORG_IDS") or "").split(",") if item.strip().isdigit()}
    return TutorSettings(
        enabled=(env.get("TUTOR_ENABLED") or "").strip().lower() in {"1", "true", "yes"},
        org_ids=frozenset(org_ids) or None,
        burst_per_min=_env_int(env, "TUTOR_BURST_PER_MIN", 6, 1, 60),
        max_message_chars=_env_int(env, "TUTOR_MAX_MESSAGE_CHARS", 500, 50, 500),
        disable_thinking=(env.get("TUTOR_DISABLE_THINKING") or "1").strip() not in {"0", "false", "no"},
    )


class TutorStore(Protocol):
    async def recent_turns(self, student_id: int, topic_id: int, block_index: int, question_index: int | None, version_id: int | None) -> list[TutorTurn]: ...
    async def llm_calls_since(self, student_id: int, since: datetime) -> int: ...
    async def topic_turns(self, student_id: int, topic_id: int, version_id: int | None) -> list[TutorTurn]: ...
    async def release(self) -> None: ...
    async def add(self, turn: TutorTurn) -> TutorTurn: ...


UNAVAILABLE = "Помощник временно недоступен"
SESSION_TURNS = 300


def _db_guarded(method: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    """Сбой базы (например, таблица ещё не создана) — понятная 503, а не 500."""
    async def wrapper(self: "SqlTutorStore", *args: Any, **kwargs: Any) -> Any:
        try:
            return await method(self, *args, **kwargs)
        except SQLAlchemyError as exc:
            logger.warning("Tutor store failed: %s", exc.__class__.__name__)
            await self.db.rollback()
            raise TutorServiceError(status_code=503, detail=UNAVAILABLE) from exc
    return wrapper


class SqlTutorStore:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @_db_guarded
    async def recent_turns(self, student_id: int, topic_id: int, block_index: int, question_index: int | None, version_id: int | None) -> list[TutorTurn]:
        # Только текущая версия урока: после переиздания индексы блоков другие.
        statement = (
            select(TutorTurn)
            .where(TutorTurn.student_id == student_id, TutorTurn.topic_id == topic_id, TutorTurn.block_index == block_index,
                   TutorTurn.lesson_version_id.is_(None) if version_id is None else TutorTurn.lesson_version_id == version_id)
            .order_by(TutorTurn.id.desc()).limit(RECENT_TURNS)
        )
        statement = statement.where(
            TutorTurn.question_index.is_(None) if question_index is None else TutorTurn.question_index == question_index
        )
        return list(reversed((await self.db.scalars(statement)).all()))

    @_db_guarded
    async def llm_calls_since(self, student_id: int, since: datetime) -> int:
        return int(await self.db.scalar(
            select(func.count(TutorTurn.id)).where(
                TutorTurn.student_id == student_id, TutorTurn.llm_called.is_(True), TutorTurn.created_at >= since,
            )
        ) or 0)

    @_db_guarded
    async def topic_turns(self, student_id: int, topic_id: int, version_id: int | None) -> list[TutorTurn]:
        # Только текущая версия урока: после переиздания индексы блоков могли сдвинуться.
        query = select(TutorTurn).where(
            TutorTurn.student_id == student_id, TutorTurn.topic_id == topic_id,
            TutorTurn.lesson_version_id.is_(None) if version_id is None else TutorTurn.lesson_version_id == version_id,
        )
        # Последние SESSION_TURNS реплик, по порядку: иначе после долгого урока новые не вернутся.
        return list(reversed((await self.db.scalars(
            query.order_by(TutorTurn.id.desc()).limit(SESSION_TURNS)
        )).all()))

    @_db_guarded
    async def release(self) -> None:
        """Закрывает транзакцию до вызова модели, чтобы соединение не ждало ответа.

        Именно commit, а не rollback: откат «забывает» загруженные строки, и
        обращение к ним после этого падает; сессия создана с
        expire_on_commit=False. Заодно сохраняются записи загрузчика урока.
        """
        await self.db.commit()

    @_db_guarded
    async def add(self, turn: TutorTurn) -> TutorTurn:
        self.db.add(turn)
        await self.db.commit()
        await self.db.refresh(turn)
        return turn


ManifestLoader = Callable[..., Awaitable[dict[str, Any]]]
ToolCaller = Callable[..., Awaitable[Any]]


@dataclass
class TurnInput:
    topic_id: int
    block_index: int
    event: str
    question_index: int | None = None
    step_index: int | None = None
    message: str | None = None
    student_value: str | None = None
    hint_level: int | None = None
    client_outcome: str | None = None


def _history(turns: list[TutorTurn]) -> list[dict[str, str]]:
    history: list[dict[str, str]] = []
    for turn in turns:
        if turn.student_text:
            history.append({"role": "ученик", "text": turn.student_text})
        elif turn.student_value:
            history.append({"role": "ученик", "text": f"ответил: {turn.student_value}"})
        if turn.reply:
            history.append({"role": "тьютор", "text": turn.reply})
    return history


def _consecutive_wrong(turns: list[TutorTurn], outcome: str | None) -> int:
    count = 1 if outcome == "incorrect" else 0
    for turn in reversed(turns):
        if turn.event != "answer_submitted" or turn.check_outcome in (None, "wrong_unit"):
            continue
        if turn.check_outcome != "incorrect":
            break
        count += 1
    return count if outcome == "incorrect" else 0


async def _load_lesson(manifest_loader: ManifestLoader, student_id: int, topic_id: int, db: Any) -> dict[str, Any]:
    manifest = await manifest_loader(topic_id=topic_id, student_id=student_id, db=db)
    lesson = manifest.get("lesson") or {}
    metadata = lesson.get("lesson_metadata") or {}
    if metadata.get("lesson_type") == "assessment":
        raise TutorServiceError(status_code=403, detail="В контрольной работе помощник недоступен")
    return lesson


def _require_enabled(settings: TutorSettings, organization_id: int | None) -> None:
    if not settings.enabled or (settings.org_ids is not None and organization_id not in settings.org_ids):
        raise TutorServiceError(status_code=403, detail="Помощник пока не включён")


async def take_tutor_turn(
    *,
    student_id: int,
    organization_id: int | None,
    grade: int | None,
    payload: TurnInput,
    db: Any,
    store: TutorStore | None = None,
    manifest_loader: ManifestLoader | None = None,
    tool_caller: ToolCaller | None = None,
    settings: TutorSettings | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    settings = settings or tutor_settings()
    _require_enabled(settings, organization_id)
    if payload.event not in EVENTS:
        raise TutorServiceError(status_code=422, detail="Неизвестное событие")
    if manifest_loader is None:
        from services.lessons import get_student_lesson_manifest as manifest_loader
    if tool_caller is None:
        from llm import call_tool as tool_caller
    store = store or SqlTutorStore(db)
    now = now or datetime.now(timezone.utc)

    lesson = await _load_lesson(manifest_loader, student_id, payload.topic_id, db)
    # Индексы — как во фронтенде (исходный индекс блока): битый блок не выкидываем, а заменяем пустым.
    blocks = [block if isinstance(block, dict) else {} for block in lesson.get("blocks") or []]
    if not 0 <= payload.block_index < len(blocks) or not blocks[payload.block_index]:
        raise TutorServiceError(status_code=404, detail="Задание не найдено")
    block = blocks[payload.block_index]
    metadata = lesson.get("lesson_metadata") or {}
    language = "ky" if metadata.get("content_language") == "ky" else "ru"
    grade = grade or metadata.get("subject_grade")
    locked = assessment_mode(block)

    # Верность ответа решает сервер по правилам урока; то, что прислал клиент, только логируется.
    spec = answer_spec(block, payload.question_index)
    value = scrub_pii(payload.student_value)[:200] or None
    outcome = None
    if value is not None:
        outcome = check_answer(
            value, spec["correct"], numeric=spec["numeric"], unit=spec["unit"],
            accepted_units=spec["accepted_units"], tolerance=spec["tolerance"],
        )
    message = scrub_pii(payload.message)[: settings.max_message_chars] or None

    recent = await store.recent_turns(
        student_id, payload.topic_id, payload.block_index, payload.question_index, lesson.get("active_version_id"),
    )
    hints = authored_hints(block)
    # Подсказки урока, которые ученик уже видел (в том числе выданные защитой вместо реплики).
    hints_shown = [turn.reply for turn in recent if turn.reply_source in {"hint", "guard"} and turn.reply in hints]
    llm_calls = await store.llm_calls_since(student_id, now - timedelta(seconds=60))
    decision = decide(payload.event, RuleState(
        outcome=outcome,
        consecutive_wrong=_consecutive_wrong(recent, outcome),
        offer_after_errors=grade_profile(grade).offer_after_errors,
        assessment=locked,
        idle_offered=any(turn.event == "idle" and turn.reply for turn in recent),
        # Уровень подсказки считает сервер: клиент не может перескочить к модели.
        hint_level=len(hints_shown),
        authored_hints=len(hints),
        llm_calls_last_minute=llm_calls,
        burst_limit=settings.burst_per_min,
        distress=detect_distress(message),
    ))

    turn = TutorTurn(
        student_id=student_id, topic_id=payload.topic_id, lesson_version_id=lesson.get("active_version_id"),
        block_index=payload.block_index, question_index=payload.question_index, step_index=payload.step_index,
        event=payload.event, student_text=message, student_value=value, check_outcome=outcome,
        reply="", reply_source="silent", action=decision.action, action_args={},
        safety_flag="distress" if decision.template_key == "distress" else "none",
        off_topic=False, leak_blocked=False, llm_called=False,
    )
    offer = decision.offer

    if decision.kind == "template":
        turn.reply, turn.reply_source = template(decision.template_key or "fallback", language), "template"
    elif decision.kind == "authored_hint" and decision.hint_index is not None:
        turn.reply, turn.reply_source, turn.hint_level = hints[decision.hint_index], "hint", decision.hint_index
        turn.action = "show_hint"
    elif decision.kind == "llm":
        # Всё нужное из истории — до освобождения соединения.
        history = _history(recent)
        reached = outcome == "correct" or any(t.check_outcome == "correct" for t in recent)
        await store.release()
        await _llm_reply(
            turn, tool_caller, settings, lesson=lesson, blocks=blocks, block=block, grade=grade, language=language,
            spec=spec, hints_shown=hints_shown, hints=hints, outcome=outcome, value=value,
            protected=protected_items(blocks, payload.block_index, payload.question_index),
            message=message, reached=reached, history=history,
            question_index=payload.question_index, event=payload.event,
        )

    theory = nearest_theory_index(blocks, payload.block_index)
    if turn.action == "open_theory" and theory is None:
        turn.action = None
    if turn.action == "open_theory":
        turn.action_args = {"target_block_index": theory}
    if turn.action == "call_teacher" and not turn.reply:
        turn.reply = template("call_teacher_ack", language)

    saved = await store.add(turn)
    return {
        "turn_id": saved.id,
        "reply": saved.reply,
        "source": saved.reply_source,
        "action": {"type": saved.action, **(saved.action_args or {})} if saved.action else None,
        "offer": offer,
        "outcome": outcome,
        "assessment_mode": locked,
        "hint_level": saved.hint_level,
    }


async def _llm_reply(turn: TutorTurn, tool_caller: ToolCaller, settings: TutorSettings, **ctx: Any) -> None:
    from llm.router import TASK_TUTOR

    lesson, block = ctx["lesson"], ctx["block"]
    metadata = lesson.get("lesson_metadata") or {}
    subject_label, show_path = _subject_guidance(metadata)
    system_blocks = [
        {"text": BASE_CHARACTER, "cache": True},
        {"text": lesson_character(ctx["grade"], subject_label, show_path, ctx["language"]) + "\n\n"
                 + lesson_context(ctx["blocks"], metadata), "cache": True},
    ]
    prompt = turn_prompt(TurnContext(
        block=block, block_index=turn.block_index, question_index=ctx["question_index"], event=ctx["event"],
        student_value=ctx["value"], check_outcome=ctx["outcome"], message=ctx["message"],
        hints_shown=ctx["hints_shown"], recent_turns=ctx["history"],
    ))
    extra = {"thinking": {"type": "disabled"}} if settings.disable_thinking else None

    for attempt in range(2):
        started = time.monotonic()
        try:
            result = await tool_caller(
                TASK_TUTOR, system="", user=prompt + (LEAK_RETRY_NOTE if attempt else ""), tool=TUTOR_TOOL,
                max_tokens=MAX_TOKENS, system_blocks=system_blocks, timeout=TIMEOUT_SEC, extra=extra,
            )
        except Exception as exc:
            # Не молчим: если, например, модель отвергает параметры, пилот должен это увидеть в логе.
            logger.warning("Tutor model call failed: %s: %s", exc.__class__.__name__, str(exc)[:300])
            turn.diagnosis = f"llm_error: {exc.__class__.__name__}"
            turn.reply, turn.reply_source = template("fallback", ctx["language"]), "fallback"
            return
        turn.llm_called = True
        turn.latency_ms = int((time.monotonic() - started) * 1000)
        turn.provider, turn.model = getattr(result, "provider", None), getattr(result, "model", None)
        usage = getattr(result, "usage", None) or {}
        turn.input_tokens, turn.output_tokens = usage.get("input_tokens"), usage.get("output_tokens")
        turn.cache_read_tokens, turn.cache_write_tokens = usage.get("cache_read_input_tokens"), usage.get("cache_creation_input_tokens")
        data = getattr(result, "data", None) or {}
        if not getattr(result, "ok", False) or not str(data.get("reply") or "").strip():
            turn.reply, turn.reply_source = template("fallback", ctx["language"]), "fallback"
            return

        reply = str(data["reply"]).strip()[:REPLY_LIMIT]
        turn.misconception_code = (str(data.get("misconception_code") or "").strip()[:80]) or None
        turn.diagnosis = (str(data.get("diagnosis") or "").strip()[:500]) or None
        turn.off_topic = bool(data.get("off_topic"))
        flag = str(data.get("safety_flag") or "none")
        turn.safety_flag = flag if flag in {"none", "distress", "pii", "abuse", "cheating_request"} else "none"
        action = str(data.get("action") or "none")
        turn.action = action if action in MODEL_ACTIONS else None
        if turn.safety_flag == "distress":
            turn.action = "call_teacher"

        leaked = bool(data.get("reveals_answer")) or any(
            detect_answer_leak(
                reply, spec, question_text=item_question, student_value=ctx["value"] if current else None,
                shown_hints=ctx["hints_shown"] if current else None, reached=ctx["reached"] and current, current=current,
            )
            for spec, item_question, current in ctx["protected"]
        )
        if not leaked:
            turn.reply, turn.reply_source = reply, "llm"
            return
        turn.leak_blocked = True

    # Дважды раскрыл ответ — даём следующую заранее написанную подсказку или готовую фразу.
    unseen = [hint for hint in ctx["hints"] if hint not in ctx["hints_shown"]]
    turn.reply, turn.reply_source = (unseen[0], "guard") if unseen else (template("fallback", ctx["language"]), "guard")
    # Сигнал учителю о тревожном сообщении сохраняется, даже если реплика заменена.
    turn.action = "call_teacher" if turn.safety_flag == "distress" else None


def _subject_guidance(metadata: dict[str, Any]) -> tuple[str, str]:
    from ai.generator import SUBJECT_FAMILY_PROFILES

    family = str(metadata.get("subject_family") or "general")
    profile = SUBJECT_FAMILY_PROFILES.get(family) or SUBJECT_FAMILY_PROFILES["general"]
    return str(metadata.get("subject_name") or profile["label"]), str(profile["show_path"])


async def get_tutor_session(
    *,
    student_id: int,
    organization_id: int | None,
    topic_id: int,
    db: Any,
    store: TutorStore | None = None,
    manifest_loader: ManifestLoader | None = None,
    settings: TutorSettings | None = None,
) -> dict[str, Any]:
    """Диалог по уроку — чтобы разговор пережил перезагрузку страницы."""
    settings = settings or tutor_settings()
    try:
        _require_enabled(settings, organization_id)
    except TutorServiceError:
        return {"enabled": False, "turns": []}
    if manifest_loader is None:
        from services.lessons import get_student_lesson_manifest as manifest_loader
    lesson = await _load_lesson(manifest_loader, student_id, topic_id, db)
    store = store or SqlTutorStore(db)
    try:
        turns = await store.topic_turns(student_id, topic_id, lesson.get("active_version_id"))
    except TutorServiceError:
        return {"enabled": False, "turns": []}
    return {
        "enabled": True,
        "turns": [
            {
                "id": turn.id, "block_index": turn.block_index, "question_index": turn.question_index,
                "event": turn.event, "student_text": turn.student_text, "reply": turn.reply,
                "source": turn.reply_source, "hint_level": turn.hint_level,
            }
            for turn in turns if turn.reply or turn.student_text
        ],
    }
