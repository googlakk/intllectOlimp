"""Связь тем КТП с параграфами учебника.

Подбор создаёт предложения только для тем без связей — решения учителя не
затираются. Прямая ссылка из КТП («§ 5», «стр. 31») подтверждается сразу,
остальное подтверждает учитель. В генерацию идут только подтверждённые связи.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from models import Section, Topic
from services.auth import AuthPrincipal
from services.educator_access import require_subject_management, require_topic_management
from services.textbooks import TextbookServiceError, _guarded, _require_access
from textbooks.matching import SectionInfo, suggest_sections
from textbooks.models import Textbook, TextbookPage, TextbookSection, TopicTextbookLink

# Повторение и контрольная опираются на параграфы пройденных тем, своего параграфа у них нет.
COVERED_LESSON_TYPES = frozenset({"review", "assessment"})
SECTION_TEXT_PAGES = 2


async def _book_with_subject(textbook_id: int, db: AsyncSession, user: AuthPrincipal) -> Textbook:
    book = _require_access(await _guarded(db, db.get(Textbook, textbook_id)), user)
    if book.subject_id is None:
        raise TextbookServiceError(422, "Укажите для учебника предмет из КТП — тогда темы можно привязать к параграфам.")
    await require_subject_management(user, book.subject_id, db)
    return book


async def _subject_topics(db: AsyncSession, subject_id: int) -> list[Topic]:
    return list((await _guarded(db, db.scalars(
        select(Topic).join(Section, Section.id == Topic.section_id)
        .where(Section.subject_id == subject_id, Topic.archived_at.is_(None))
        .order_by(Section.sort_order, Topic.sort_order, Topic.id)
    ))).all())


async def _book_sections(db: AsyncSession, book: Textbook, with_text: bool) -> list[tuple[TextbookSection, SectionInfo]]:
    sections = list((await _guarded(db, db.scalars(
        select(TextbookSection).where(TextbookSection.textbook_id == book.id).order_by(TextbookSection.position)
    ))).all())
    texts: dict[int, str] = {}
    if with_text and sections:
        # Для сравнения достаточно начала параграфа: заголовок и первые страницы.
        wanted = {index for section in sections for index in range(section.pdf_from, section.pdf_from + SECTION_TEXT_PAGES)}
        pages = (await _guarded(db, db.execute(
            select(TextbookPage.page_index, TextbookPage.text)
            .where(TextbookPage.textbook_id == book.id, TextbookPage.page_index.in_(wanted))
        ))).all()
        texts = {row.page_index: row.text or "" for row in pages}
    offset = book.page_offset or 0
    return [
        (section, SectionInfo(
            id=section.id, number=section.number, title=section.title,
            printed_from=section.pdf_from - offset, printed_to=section.pdf_to - offset,
            text="\n".join(texts.get(index, "") for index in range(section.pdf_from, section.pdf_from + SECTION_TEXT_PAGES)),
        ))
        for section in sections
    ]


async def suggest_links(textbook_id: int, db: AsyncSession, *, user: AuthPrincipal) -> dict[str, int]:
    book = await _book_with_subject(textbook_id, db, user)
    topics = await _subject_topics(db, book.subject_id)
    sections = await _book_sections(db, book, with_text=True)
    if not sections:
        raise TextbookServiceError(409, "У учебника ещё нет параграфов — дождитесь окончания обработки.")
    infos = [info for _section, info in sections]
    # Решения по ЭТОЙ книге (в том числе «отклонено») не трогаем; у второй книги предмета — свои предложения.
    linked = set((await _guarded(db, db.scalars(
        select(TopicTextbookLink.topic_id).where(
            TopicTextbookLink.topic_id.in_([topic.id for topic in topics]),
            TopicTextbookLink.section_id.in_([info.id for info in infos]),
        )
    ))).all())
    counts = {"confirmed": 0, "suggested": 0, "not_found": 0, "skipped": 0}
    now = datetime.now(timezone.utc)
    for topic in topics:
        if topic.id in linked:
            counts["skipped"] += 1
            continue
        if topic.lesson_type in COVERED_LESSON_TYPES:
            counts["skipped"] += 1
            continue
        # Ссылки на § и страницы ищем только в ресурсах КТП: в названии темы «класс 7» — не страница.
        found = suggest_sections(topic.name, topic.learning_objectives or "", topic.resources or "", infos)
        if not found:
            counts["not_found"] += 1
            continue
        for position, suggestion in enumerate(found):
            direct = suggestion.source == "ktp"
            db.add(TopicTextbookLink(
                topic_id=topic.id, section_id=suggestion.section_id, source=suggestion.source, score=suggestion.score,
                status="confirmed" if direct else "suggested", role="primary" if position == 0 else "supporting",
                confirmed_at=now if direct else None, confirmed_by_profile_id=user.profile_id if direct else None,
            ))
        counts["confirmed" if found[0].source == "ktp" else "suggested"] += 1
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise TextbookServiceError(409, "Подбор уже выполняется — обновите страницу через минуту.") from exc
    return counts


async def links_overview(textbook_id: int, db: AsyncSession, *, user: AuthPrincipal) -> dict[str, Any]:
    book = await _book_with_subject(textbook_id, db, user)
    topics = await _subject_topics(db, book.subject_id)
    sections = await _book_sections(db, book, with_text=False)
    by_id = {section.id: section for section, _info in sections}
    links = (await _guarded(db, db.scalars(
        select(TopicTextbookLink).where(
            TopicTextbookLink.topic_id.in_([topic.id for topic in topics]),
            TopicTextbookLink.section_id.in_(list(by_id)),
        )
    ))).all()
    rejected = {link.topic_id for link in links if link.status == "rejected"}
    links = [link for link in links if link.status != "rejected"]
    per_topic: dict[int, list[TopicTextbookLink]] = {}
    for link in links:
        per_topic.setdefault(link.topic_id, []).append(link)
    return {
        "sections": [{"id": section.id, "number": section.number, "title": section.title, "chapter": section.chapter,
                      "printed_page": section.printed_page} for section, _info in sections],
        "topics": [
            {
                "id": topic.id, "ktp_number": topic.ktp_number, "name": topic.name, "lesson_type": topic.lesson_type,
                "uses_covered_topics": topic.lesson_type in COVERED_LESSON_TYPES,
                "rejected": topic.id in rejected and not per_topic.get(topic.id),
                "links": [
                    {"section_id": link.section_id, "status": link.status, "source": link.source, "role": link.role,
                     "score": link.score, "number": by_id[link.section_id].number, "title": by_id[link.section_id].title}
                    for link in sorted(per_topic.get(topic.id, []), key=lambda link: (link.role != "primary", -(link.score or 0)))
                ],
            }
            for topic in topics
        ],
    }


async def set_topic_links(textbook_id: int, topic_id: int, section_ids: list[int], db: AsyncSession, *,
                          user: AuthPrincipal) -> dict[str, Any]:
    """Учитель подтвердил или выбрал параграфы темы: они становятся подтверждёнными.

    Остальные связи темы с этой книгой помечаются «отклонено»: повторный подбор их не вернёт.
    Пустой выбор — «этой теме параграф из книги не нужен».
    """
    book = await _book_with_subject(textbook_id, db, user)
    topic = await require_topic_management(user, topic_id, db)
    section = await _guarded(db, db.get(Section, topic.section_id))
    if section is None or section.subject_id != book.subject_id:
        raise TextbookServiceError(422, "Тема относится к другому предмету")
    book_sections = set((await _guarded(db, db.scalars(
        select(TextbookSection.id).where(TextbookSection.textbook_id == book.id)
    ))).all())
    chosen = [section_id for section_id in dict.fromkeys(section_ids) if section_id in book_sections]
    if len(chosen) != len(set(section_ids)):
        raise TextbookServiceError(404, "Параграф не найден в этом учебнике")
    existing = {
        link.section_id: link for link in (await _guarded(db, db.scalars(
            select(TopicTextbookLink).where(TopicTextbookLink.topic_id == topic_id,
                                            TopicTextbookLink.section_id.in_(book_sections))
        ))).all()
    }
    now = datetime.now(timezone.utc)
    for section_id, link in existing.items():
        if section_id not in chosen:
            link.status, link.confirmed_at, link.confirmed_by_profile_id = "rejected", now, user.profile_id
    for position, section_id in enumerate(chosen):
        link = existing.get(section_id) or TopicTextbookLink(topic_id=topic_id, section_id=section_id, source="manual")
        link.status, link.role = "confirmed", "primary" if position == 0 else "supporting"
        link.confirmed_at, link.confirmed_by_profile_id = now, user.profile_id
        db.add(link)
    await _guarded(db, db.commit())
    return {"topic_id": topic_id, "section_ids": chosen}
