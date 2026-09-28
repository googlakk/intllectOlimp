"""Подготовка и атомарная вставка одного блока с проверенным источником."""

from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import hmac
import json
import math
import os
import re
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai.component_generator import generate_component
from ai.textbook_grounding import textbook_warnings
from llm.base import LLMError
from models import GeneratedLesson, Section, Subject, Topic
from objectives import GENERATION_COMPONENTS, component_content_warnings, decompose_objectives, default_evidence_stage, validate_block_answers
from services.components import load_component_registry
from services.lessons import LessonServiceError, get_lesson_or_error, update_lesson_blocks
from services.textbook_context import load_component_textbook_context

TOKEN_TTL = 1800
NO_SOURCE = "Подтвердите связь темы с параграфом учебника, затем выберите параграф или упражнение."


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                                     separators=(",", ":")).encode()).hexdigest()


def lesson_revision(lesson: GeneratedLesson, topic: Topic) -> str:
    return _digest({"lesson": lesson.id, "version": lesson.active_version_id,
                    "blocks": lesson.blocks or [], "objectives": topic.learning_objectives,
                    "topic": topic.name, "hours": topic.hours, "lesson_type": topic.lesson_type,
                    "archived": bool(topic.archived_at)})


def _plain_excerpt(value: str, limit: int) -> str:
    return re.sub(r"(?:https?://|data:)[^\s<>\]\)]+", "[ссылка]", value).strip()[:limit]


def _neighbor_excerpt(content: dict[str, Any]) -> str:
    """Только учебный текст; ни источники, ни медиа, ни правильные ответы не копируются."""
    fragments: list[str] = []
    text_fields = {"title", "heading", "term", "question", "problem", "task", "prompt",
                   "instruction", "text", "body", "description", "definition", "explanation"}
    nested_fields = {"slides", "steps", "questions", "events", "nodes", "items", "options", "key_concepts"}
    def collect(value: Any, depth: int = 0) -> None:
        if depth > 3 or len(fragments) >= 12:
            return
        if isinstance(value, str):
            fragments.append(_plain_excerpt(value, 400))
        elif isinstance(value, dict):
            for key, item in value.items():
                if key in text_fields and isinstance(item, str):
                    collect(item, depth + 1)
                elif key in nested_fields:
                    collect(item, depth + 1)
        elif isinstance(value, list):
            for item in value[:4]:
                collect(item, depth + 1)
    collect(content)
    return "\n".join(fragments)[:1600]


def _insertion_context(blocks: list[dict[str, Any]], after_index: int | None, component: str) -> dict[str, Any]:
    position = _position(after_index, len(blocks))
    outline = []
    neighbors = []
    for index, block in enumerate(blocks):
        content = block.get("content") if isinstance(block.get("content"), dict) else {}
        title = next((content[key] for key in ("title", "heading", "term", "question", "problem", "prompt", "task")
                      if isinstance(content.get(key), str) and content[key].strip()), "")
        entry = {"index": index, "component": str(block.get("component") or "")[:100],
                 "title": _plain_excerpt(title, 160),
                 "stage": content.get("evidence_stage") or default_evidence_stage(block.get("component", ""))}
        outline.append(entry)
        if index in (position - 1, position):
            neighbors.append({**entry, "position": "before" if index < position else "after",
                              "excerpt": _neighbor_excerpt(content)})
    return {"after_index": after_index, "insertion_index": position,
            "new_block_stage": default_evidence_stage(component), "outline": outline, "neighbors": neighbors}


def _key() -> bytes:
    secret = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not secret:
        raise LessonServiceError(status_code=503, detail="Подготовка блоков пока не настроена на сервере.")
    return hmac.digest(secret.encode(), b"intellect:prepared-lesson-component:v1", "sha256")


def _sign(payload: dict[str, Any]) -> str:
    encoded = base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).decode().rstrip("=")
    return encoded + "." + hmac.new(_key(), encoded.encode(), hashlib.sha256).hexdigest()


def _verify(token: str) -> dict[str, Any]:
    try:
        encoded, signature = token.split(".", 1)
        expected = hmac.new(_key(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("signature")
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if not isinstance(payload, dict) or not isinstance(payload.get("expires"), int):
            raise ValueError("payload")
        return payload
    except (ValueError, TypeError, UnicodeError):
        raise LessonServiceError(status_code=422, detail="Подготовленный блок изменён. Подготовьте его заново.") from None


async def _topic(lesson: GeneratedLesson, db: AsyncSession) -> Topic:
    topic = await db.get(Topic, lesson.topic_id)
    if topic is None:
        raise LessonServiceError(status_code=404, detail="Тема не найдена.")
    if topic.archived_at:
        raise LessonServiceError(status_code=409, detail="Сначала восстановите тему из архива.")
    return topic


def _schema(component: str) -> dict[str, Any]:
    if component not in GENERATION_COMPONENTS or component == "GeneratedMedia":
        raise LessonServiceError(status_code=422, detail="Этот компонент недоступен для подготовки по учебнику.")
    for entry in load_component_registry():
        if "".join(word.capitalize() for word in entry["id"].split("-")) == component:
            return entry["content_schema"]
    raise LessonServiceError(status_code=422, detail="Схема компонента не найдена.")


def _validate_schema(value: Any, schema: dict[str, Any], path: str = "content") -> None:
    kind = schema.get("type")
    valid = {"object": isinstance(value, dict), "array": isinstance(value, list),
             "string": isinstance(value, str), "number": type(value) in (int, float),
             "integer": type(value) is int, "boolean": type(value) is bool, "null": value is None}
    kinds = kind if isinstance(kind, list) else [kind]
    if kind is not None and not any(valid.get(candidate, True) for candidate in kinds):
        raise ValueError(f"Некорректное поле {path}")
    if isinstance(value, (int, float)) and not isinstance(value, bool) and not math.isfinite(value):
        raise ValueError(f"Некорректное число {path}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"Недопустимое значение {path}")
    if isinstance(value, str) and (len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", 120_000)):
        raise ValueError(f"Недопустимая длина {path}")
    if type(value) in (int, float) and (value < schema.get("minimum", -math.inf) or value > schema.get("maximum", math.inf)):
        raise ValueError(f"Число вне допустимых границ {path}")
    if isinstance(value, dict):
        if set(schema.get("required", [])) - value.keys():
            raise ValueError(f"Не заполнены обязательные поля {path}")
        for name, item in value.items():
            _validate_schema(item, schema.get("properties", {}).get(name, {}), f"{path}.{name}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", 1000):
            raise ValueError(f"Недопустимое число элементов {path}")
        if schema.get("uniqueItems") and len({_digest(item) for item in value}) != len(value):
            raise ValueError(f"Повторяющиеся элементы {path}")
        for index, item in enumerate(value):
            _validate_schema(item, schema.get("items", {}), f"{path}[{index}]")


def _validate_block(block: dict[str, Any], schema: dict[str, Any]) -> None:
    try:
        _validate_schema(block["content"], schema)
        errors = validate_block_answers(block, 0) + component_content_warnings([block])
        if errors:
            raise ValueError(errors[0].get("message") or "Проверьте правильность ответа.")
    except (ValueError, TypeError, KeyError) as exc:
        raise LessonServiceError(status_code=422, detail=f"Не удалось подготовить корректный блок: {exc}") from None


def _position(after_index: int | None, count: int) -> int:
    if after_index is None:
        return count
    if after_index < -1 or after_index >= count:
        raise LessonServiceError(status_code=409, detail="Порядок блоков изменился. Откройте добавление заново.")
    return after_index + 1


def _check_revision(lesson: GeneratedLesson, topic: Topic, expected: str) -> None:
    if lesson_revision(lesson, topic) != expected:
        raise LessonServiceError(status_code=409, detail="Урок или его цели изменились. Откройте добавление заново.")


def _objective(topic: Topic, objective_id: str) -> dict[str, Any]:
    objective = next((item for item in decompose_objectives(topic.learning_objectives) if item["id"] == objective_id), None)
    if objective is None:
        raise LessonServiceError(status_code=422, detail="Выберите актуальную цель урока из КТП.")
    return objective


async def _material(db: AsyncSession, topic: Topic, section_id: int | None, item_id: int | None) -> dict[str, Any]:
    if section_id is None and item_id is None:
        raise LessonServiceError(status_code=422, detail="Выберите параграф или упражнение учебника.")
    material = await load_component_textbook_context(db, topic, source_section_id=section_id, source_item_id=item_id)
    if not material:
        raise LessonServiceError(status_code=422, detail=NO_SOURCE)
    sections = material.get("sections") or []
    if not sections or not any(str(section.get("text") or "").strip() or
                               any(str(item.get("text") or "").strip() for item in section.get("items", []))
                               for section in sections):
        raise LessonServiceError(status_code=422, detail="В выбранном источнике нет распознанного текста. Выберите другой источник.")
    return material


def _source_ref(material: dict[str, Any], item_id: int | None) -> tuple[dict[str, Any], str]:
    section = material["sections"][0]
    item = next((item for item in section["items"] if item["id"] == item_id), None)
    ref = {"kind": "analog" if item else "section", "textbook_id": material["textbook_id"],
           "section_id": section["id"], "page": item.get("page") if item else section["page_from"]}
    if item:
        ref["item_id"] = item["id"]
    label = f"{material['title']} · {section['title']}"
    if item:
        label += f" · {item.get('label') or 'Упражнение'}"
        label += " · адаптация задания"
    if ref["page"] is not None:
        label += f" · стр. {ref['page']}"
    return ref, label


def _bind(block: dict[str, Any], ref: dict[str, Any], objective_id: str) -> dict[str, Any]:
    block = deepcopy(block)
    def clean(value: Any) -> None:
        if isinstance(value, dict):
            value.pop("source_ref", None)
            for item in value.values():
                clean(item)
        elif isinstance(value, list):
            for item in value:
                clean(item)
    clean(block)
    content = block["content"]
    content.pop("anchor", None)
    content.update(source_ref=deepcopy(ref), objective_ids=[objective_id],
                   evidence_stage=default_evidence_stage(block["component"]) or "practice")
    if block["component"] == "MasteryCheck":
        for question in content.get("questions", []):
            if isinstance(question, dict):
                question.update(source_ref=deepcopy(ref), objective_ids=[objective_id], dimension=objective_id)
    return block


async def component_context(lesson_id: int, db: AsyncSession) -> dict[str, Any]:
    lesson = await get_lesson_or_error(lesson_id, db)
    topic = await _topic(lesson, db)
    material = await load_component_textbook_context(db, topic)
    objectives = decompose_objectives(topic.learning_objectives)
    sources = [{"section_id": section["id"], "title": section["title"],
                "page_from": section["page_from"], "page_to": section["page_to"],
                "items": [{key: item.get(key) for key in ("id", "label", "kind", "page")}
                          for item in section["items"]]}
               for section in (material or {}).get("sections", [])]
    return {"revision": lesson_revision(lesson, topic), "objectives": objectives, "sources": sources,
            "supported_components": [name for name in sorted(GENERATION_COMPONENTS)
                                     if name != "GeneratedMedia" and _schema(name)],
            "reason": NO_SOURCE if not sources else ("Укажите цели обучения в КТП." if not objectives else None)}


async def prepare_component(lesson_id: int, *, component: str, objective_id: str,
                            after_index: int | None, base_revision: str, source_item_id: int | None,
                            source_section_id: int | None, model: str | None, db: AsyncSession) -> dict[str, Any]:
    _key()  # проверить настройку до платного вызова
    schema = _schema(component)
    lesson = await get_lesson_or_error(lesson_id, db)
    topic = await _topic(lesson, db)
    _check_revision(lesson, topic, base_revision)
    _position(after_index, len(lesson.blocks or []))
    objective = _objective(topic, objective_id)
    material = await _material(db, topic, source_section_id, source_item_id)
    ref, label = _source_ref(material, source_item_id)
    section = await db.get(Section, topic.section_id)
    subject = await db.get(Subject, section.subject_id) if section is not None else None
    if subject is None:
        raise LessonServiceError(status_code=404, detail="Предмет темы не найден.")
    topic_data = {"name": topic.name, "learning_objectives": topic.learning_objectives,
                  "subject": subject.name, "grade": subject.grade,
                  "language": subject.instruction_language or "ru", "hours": topic.hours,
                  "lesson_type": topic.lesson_type,
                  "existing_lesson": _insertion_context(lesson.blocks or [], after_index, component)}
    # Все данные скопированы; чтение завершено, соединение не ждёт LLM.
    await db.rollback()
    try:
        block = await generate_component(component=component, schema=schema, objective=objective,
                                         topic=topic_data, material=material, model=model)
    except (LLMError, ValueError) as exc:
        raise LessonServiceError(status_code=422, detail=f"Блок не создан: {exc}") from None
    if not isinstance(block, dict) or block.get("component") != component or not isinstance(block.get("content"), dict):
        raise LessonServiceError(status_code=422, detail="Модель вернула неполный блок. Урок не изменён.")
    block = _bind(block, ref, objective_id)
    _validate_block(block, schema)
    warnings = [warning["message"] for warning in textbook_warnings([block], material)]
    token = _sign({"lesson_id": lesson_id, "revision": base_revision, "objective_id": objective_id,
                   "source_section_id": ref["section_id"], "source_item_id": source_item_id,
                   "material": _digest(material), "block": _digest(block), "after_index": after_index,
                   "expires": int(time.time()) + TOKEN_TTL})
    return {"block": block, "base_revision": base_revision, "context_fingerprint": token,
            "source_label": label, "warnings": warnings}


async def insert_component(lesson_id: int, *, block: dict[str, Any], after_index: int | None,
                           base_revision: str, context_fingerprint: str, request_id: str,
                           db: AsyncSession) -> GeneratedLesson:
    token = _verify(context_fingerprint)
    if (token.get("lesson_id") != lesson_id or token.get("revision") != base_revision
            or token.get("block") != _digest(block) or token.get("after_index") != after_index):
        raise LessonServiceError(status_code=422, detail="Подготовленный блок изменён. Подготовьте его заново.")
    # populate_existing обязателен: require_lesson_management уже загрузил объект.
    lesson = await db.scalar(select(GeneratedLesson).where(GeneratedLesson.id == lesson_id)
                             .with_for_update().execution_options(populate_existing=True))
    if lesson is None:
        raise LessonServiceError(status_code=404, detail="Урок не найден.")
    metadata = deepcopy(lesson.lesson_metadata or {})
    requests = dict(metadata.get("component_insert_requests") or {})
    request_digest = _digest({"block": block, "token": context_fingerprint})
    if request_id in requests:
        if requests[request_id] != request_digest:
            raise LessonServiceError(status_code=409, detail="Этот запрос уже использован для другого блока.")
        return lesson
    if token["expires"] < time.time():
        raise LessonServiceError(status_code=409, detail="Время предпросмотра истекло. Подготовьте блок заново.")
    topic = await _topic(lesson, db)
    _check_revision(lesson, topic, base_revision)
    _objective(topic, token["objective_id"])
    position = _position(after_index, len(lesson.blocks or []))
    material = await _material(db, topic, token.get("source_section_id"), token.get("source_item_id"))
    if _digest(material) != token.get("material"):
        raise LessonServiceError(status_code=409, detail="Источник учебника изменился. Подготовьте блок заново.")
    _validate_block(block, _schema(block["component"]))
    requests[request_id] = request_digest
    metadata["component_insert_requests"] = requests
    lesson.lesson_metadata = metadata
    blocks = deepcopy(lesson.blocks or [])
    blocks.insert(position, deepcopy(block))
    return await update_lesson_blocks(lesson_id, blocks, db)
