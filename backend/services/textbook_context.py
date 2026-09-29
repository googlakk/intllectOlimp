"""Материал учебника для темы: подтверждённые параграфы, их текст и элементы.

Только подтверждённые учителем связи. Повторение и контрольная берут параграфы
пройденных тем (covered_topic_ids). Нет связей или таблиц учебников — None,
и урок генерируется как раньше (с пометкой «без учебника»).
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from services.textbooks import section_text
from textbooks.models import Textbook, TextbookItem, TextbookPage, TextbookSection, TopicTextbookLink

logger = logging.getLogger(__name__)

COVERED_LESSON_TYPES = frozenset({"review", "assessment"})
MAX_SECTIONS = 4
# Повторение и контрольная охватывают несколько тем: больше параграфов (их задачи важнее текста).
MAX_COVERED_SECTIONS = 8


async def load_textbook_context(db: AsyncSession, topic: Any) -> dict[str, Any] | None:
    topic_id = getattr(topic, "id", None)
    if not hasattr(db, "begin_nested"):  # подмена сессии в тестах старых генераторов
        return None
    # Отложенные изменения записываем явно: их ошибка не должна выглядеть как «нет учебника».
    await db.flush()
    try:
        # Точка сохранения: сбой чтения учебника откатывает только её, а не всю сессию
        # (полный откат сбросил бы уже загруженные тему и предмет).
        async with db.begin_nested():
            return await _load(db, topic)
    except SQLAlchemyError as exc:
        # Таблиц учебников может не быть (другая среда) — урок генерируется без учебника.
        logger.warning("Textbook context unavailable for topic %s: %s", topic_id, exc.__class__.__name__)
        return None


async def _load(db: AsyncSession, topic: Any) -> dict[str, Any] | None:
    topic_ids = [topic.id]
    limit = MAX_SECTIONS
    links = await _confirmed_links(db, topic_ids)
    if not links and topic.lesson_type in COVERED_LESSON_TYPES and topic.covered_topic_ids:
        topic_ids = [int(value) for value in topic.covered_topic_ids]
        links = await _confirmed_links(db, topic_ids)
        limit = MAX_COVERED_SECTIONS
    if not links:
        return None
    # Основной параграф первым; все параграфы — из одной книги (той, где основной).
    order = {topic_id: position for position, topic_id in enumerate(topic_ids)}
    links.sort(key=lambda link: (order.get(link.topic_id, 0), link.role != "primary", -(link.score or 0)))
    section_ids = list(dict.fromkeys(link.section_id for link in links))
    sections = {
        section.id: section for section in (await db.scalars(
            select(TextbookSection).where(TextbookSection.id.in_(section_ids))
        )).all()
    }
    first = sections.get(section_ids[0])
    if first is None:
        return None
    book = await db.get(Textbook, first.textbook_id)
    if book is None:
        return None
    language = await _subject_language(db, topic)
    if book.language != language:
        # Связь осталась от старых данных: урок на одном языке по книге на другом не строим.
        logger.warning("Textbook %s language %s differs from subject language %s", book.id, book.language, language)
        return None
    chosen = [sections[section_id] for section_id in section_ids
              if section_id in sections and sections[section_id].textbook_id == book.id][:limit]
    primary = chosen[0]
    pages = (await db.execute(
        select(TextbookPage.page_index, TextbookPage.text)
        .where(TextbookPage.textbook_id == book.id, TextbookPage.page_index.between(primary.pdf_from, primary.pdf_to))
    )).all()
    items = (await db.scalars(
        select(TextbookItem).where(TextbookItem.section_id.in_([section.id for section in chosen]))
        .order_by(TextbookItem.section_id, TextbookItem.position)
    )).all()
    offset = book.page_offset or 0
    by_section: dict[int, list[dict[str, Any]]] = {}
    for item in items:
        by_section.setdefault(item.section_id, []).append({
            "id": item.id, "kind": item.kind, "label": item.label, "page": item.page,
            "text": item.text, "answer": item.answer, "difficulty": item.difficulty,
        })
    return {
        "textbook_id": book.id,
        "title": book.title,
        "student_display": book.student_display,
        "sections": [
            {
                "id": section.id, "number": section.number, "title": section.title,
                "page_from": section.pdf_from - offset, "page_to": section.pdf_to - offset,
                "text": section_text({row.page_index: row.text or "" for row in pages}, section.pdf_from, section.pdf_to, offset)
                if section.id == primary.id else "",
                "items": by_section.get(section.id, []),
            }
            for section in chosen
        ],
    }


async def _subject_language(db: AsyncSession, topic: Any) -> str:
    from models import Section, Subject

    language = await db.scalar(select(Subject.instruction_language).join(Section, Section.subject_id == Subject.id)
                               .where(Section.id == topic.section_id))
    return language or "ru"


async def _confirmed_links(db: AsyncSession, topic_ids: list[int]) -> list[TopicTextbookLink]:
    if not topic_ids:
        return []
    return list((await db.scalars(
        select(TopicTextbookLink).where(TopicTextbookLink.topic_id.in_(topic_ids), TopicTextbookLink.status == "confirmed")
    )).all())


async def load_component_textbook_context(
    db: AsyncSession, topic: Any, *, source_section_id: int | None = None,
    source_item_id: int | None = None,
) -> dict[str, Any] | None:
    """Адресный источник блока: только подтверждённый, без обрезки упражнения.

    Без выбора возвращает каталог всех связанных параграфов. С выбором — ровно
    один полный элемент либо параграф. Не использует ограничения целого урока.
    """
    if not hasattr(db, "begin_nested"):
        return None
    try:
        async with db.begin_nested():
            links = await _confirmed_links(db, [topic.id])
            if not links and topic.lesson_type in COVERED_LESSON_TYPES and topic.covered_topic_ids:
                links = await _confirmed_links(db, [int(value) for value in topic.covered_topic_ids])
            section_ids = list(dict.fromkeys(link.section_id for link in links))
            if not section_ids:
                return None
            sections = list((await db.scalars(
                select(TextbookSection).where(TextbookSection.id.in_(section_ids))
                .order_by(TextbookSection.position, TextbookSection.id)
            )).all())
            items = list((await db.scalars(
                select(TextbookItem).where(TextbookItem.section_id.in_(section_ids))
                .order_by(TextbookItem.position, TextbookItem.id)
            )).all())
            if source_item_id is not None:
                item = next((item for item in items if item.id == source_item_id), None)
                if item is None or (source_section_id is not None and item.section_id != source_section_id):
                    return None
                source_section_id = item.section_id
                items = [item]
            if source_section_id is not None:
                sections = [section for section in sections if section.id == source_section_id]
                if not sections:
                    return None
            output = []
            language = await _subject_language(db, topic)
            for section in sections:
                book = await db.get(Textbook, section.textbook_id)
                if book is None or book.language != language:
                    continue
                offset = book.page_offset or 0
                text = ""
                if source_section_id is not None and source_item_id is None:
                    pages = (await db.execute(
                        select(TextbookPage.page_index, TextbookPage.text).where(
                            TextbookPage.textbook_id == book.id,
                            TextbookPage.page_index.between(section.pdf_from, section.pdf_to),
                        )
                    )).all()
                    text = section_text({row.page_index: row.text or "" for row in pages},
                                        section.pdf_from, section.pdf_to, offset)
                output.append({
                    "id": section.id, "number": section.number, "title": section.title,
                    "textbook_id": book.id, "textbook_title": book.title,
                    "student_display": book.student_display,
                    "page_from": section.pdf_from - offset, "page_to": section.pdf_to - offset,
                    "text": text,
                    "items": [{"id": item.id, "kind": item.kind, "label": item.label,
                               "page": item.page, "text": item.text, "answer": item.answer,
                               "difficulty": item.difficulty}
                              for item in items if item.section_id == section.id and item.textbook_id == book.id],
                })
            if not output:
                return None
            if source_section_id is None:
                return {"sections": output}
            first = output[0]
            return {"textbook_id": first["textbook_id"], "title": first["textbook_title"],
                    "student_display": first["student_display"], "sections": output}
    except SQLAlchemyError as exc:
        logger.warning("Component textbook context unavailable for topic %s: %s", topic.id, exc.__class__.__name__)
        return None


async def subject_has_textbook(db: AsyncSession, topic: Any) -> bool:
    """Есть ли по предмету темы учебник с параграфами — тогда урок без учебника стоит отметить."""
    from models import Section

    if not hasattr(db, "begin_nested"):
        return False
    try:
        async with db.begin_nested():
            subject_id = await db.scalar(select(Section.subject_id).where(Section.id == topic.section_id))
            language = await _subject_language(db, topic)
            found = await db.scalar(
                select(TextbookSection.id).join(Textbook, Textbook.id == TextbookSection.textbook_id)
                .where(Textbook.subject_id == subject_id, Textbook.language == language).limit(1)
            )
            return found is not None
    except SQLAlchemyError:
        return False
