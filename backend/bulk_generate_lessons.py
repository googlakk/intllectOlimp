"""Массовая генерация черновиков уроков: первые N учебных тем каждого предмета, у которых урока ещё нет.

По умолчанию — только отчёт: что будет сгенерировано (ничего не пишет и не тратит). С --apply генерирует.
Уроки сохраняются ЧЕРНОВИКАМИ: ничего не публикуется, ученики их не видят, пока учитель не проверит.
Темы, у которых уже есть урок или черновик, не трогаются. Генерация платная — запускает владелец.

Примеры (из папки backend, с переменными из .env):
  python bulk_generate_lessons.py                         # отчёт: предметы, темы, учителя
  python bulk_generate_lessons.py --apply --teacher-id 3 --limit 3     # проба на трёх уроках
  python bulk_generate_lessons.py --apply --teacher-id 3               # всё по 5 тем на предмет
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from database import AsyncSessionLocal, engine
from models import GeneratedLesson, Section, Subject, Teacher, Topic

LOG_PATH = Path(__file__).with_name("bulk_generation_log.jsonl")
# Подряд столько неудач — что-то сломано целиком (ключ, модель, сеть): останавливаемся, а не жжём деньги.
MAX_FAILURES_IN_ROW = 3


async def pending_topics(per_subject: int, subject_ids: list[int] | None) -> list[tuple[Subject, Topic]]:
    """Первые per_subject учебных тем каждого предмета по порядку КТП, у которых ещё нет урока."""
    async with AsyncSessionLocal() as db:
        statement = select(Subject).order_by(Subject.grade, Subject.name, Subject.id)
        if subject_ids:
            statement = statement.where(Subject.id.in_(subject_ids))
        subjects = (await db.scalars(statement)).all()
        has_lesson = select(GeneratedLesson.topic_id)
        chosen: list[tuple[Subject, Topic]] = []
        for subject in subjects:
            topics = (await db.scalars(
                select(Topic).join(Section, Section.id == Topic.section_id)
                .where(Section.subject_id == subject.id, Topic.archived_at.is_(None),
                       Topic.lesson_type == "study", Topic.id.not_in(has_lesson))
                .order_by(Section.sort_order, Topic.sort_order, Topic.id)
                .limit(per_subject)
            )).all()
            chosen.extend((subject, topic) for topic in topics)
        return chosen


async def print_teachers() -> None:
    async with AsyncSessionLocal() as db:
        teachers = (await db.scalars(select(Teacher).order_by(Teacher.id))).all()
    print("\nУчителя (id для --teacher-id, урок будет записан от его имени):")
    for teacher in teachers:
        print(f"  {teacher.id}: {teacher.name}")


async def generate_one(subject: Subject, topic: Topic, teacher_id: int, model: str | None) -> dict:
    from services.lessons import generate_lesson_draft

    started = time.monotonic()
    record = {"at": datetime.now(timezone.utc).isoformat(), "subject_id": subject.id, "subject": subject.name,
              "grade": subject.grade, "topic_id": topic.id, "topic": topic.name}
    async with AsyncSessionLocal() as db:
        # Пока шла очередь, урок мог появиться (учитель открыл тему) — его не перезаписываем.
        if await db.scalar(select(GeneratedLesson.id).where(GeneratedLesson.topic_id == topic.id)):
            return {**record, "status": "skipped_existing"}
        try:
            lesson = await generate_lesson_draft(topic.id, teacher_id, db, model_choice=model)
        except Exception as exc:  # одна тема не должна останавливать остальные
            await db.rollback()
            return {**record, "status": "failed", "error": str(exc)[:300], "seconds": round(time.monotonic() - started)}
        report = (lesson.lesson_metadata or {}).get("quality_report") or {}
        return {**record, "status": "generated", "lesson_id": lesson.id, "seconds": round(time.monotonic() - started),
                "publishable": report.get("publishable"),
                "errors": [item.get("code") for item in report.get("errors") or []],
                "warnings": [item.get("code") for item in report.get("warnings") or []],
                "textbook": bool((lesson.lesson_metadata or {}).get("textbook"))}


async def run(args: argparse.Namespace) -> None:
    topics = await pending_topics(args.per_subject, args.subject_ids)
    if args.limit:
        topics = topics[:args.limit]
    by_subject: dict[str, int] = {}
    for subject, _topic in topics:
        by_subject[f"{subject.name}, {subject.grade} кл. (id {subject.id})"] = by_subject.get(
            f"{subject.name}, {subject.grade} кл. (id {subject.id})", 0) + 1
    print(f"К генерации: {len(topics)} уроков по {len(by_subject)} предметам")
    for name, count in by_subject.items():
        print(f"  {name}: {count}")
    if not args.apply:
        for subject, topic in topics:
            print(f"    · {subject.name} {subject.grade} — {topic.name}")
        await print_teachers()
        print("\nЭто только отчёт. Для генерации: --apply --teacher-id <id> (сначала лучше --limit 3).")
        await engine.dispose()
        return
    if args.teacher_id is None:
        raise SystemExit("Укажите --teacher-id: от чьего имени создаются черновики.")

    failures_in_row = 0
    done = 0
    with LOG_PATH.open("a", encoding="utf-8") as log:
        for position, (subject, topic) in enumerate(topics, start=1):
            print(f"[{position}/{len(topics)}] {subject.name} {subject.grade} — {topic.name} …", flush=True)
            result = await generate_one(subject, topic, args.teacher_id, args.model)
            log.write(json.dumps(result, ensure_ascii=False) + "\n")
            log.flush()
            status = result["status"]
            if status == "generated":
                done += 1
                failures_in_row = 0
                verdict = "можно публиковать после проверки" if result["publishable"] else f"ошибки: {', '.join(result['errors'])}"
                print(f"    готово за {result['seconds']} с · {verdict}"
                      f"{'' if result['textbook'] else ' · без учебника'}", flush=True)
            elif status == "failed":
                failures_in_row += 1
                print(f"    НЕ УДАЛОСЬ: {result['error']}", flush=True)
                if failures_in_row >= MAX_FAILURES_IN_ROW:
                    print(f"Остановлено: {MAX_FAILURES_IN_ROW} неудачи подряд — проверьте ключ, модель и сеть.")
                    break
            else:
                print("    пропущено: урок уже есть", flush=True)
    print(f"\nСгенерировано черновиков: {done}. Журнал: {LOG_PATH}")
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="Генерировать (платно). Без флага — только отчёт.")
    parser.add_argument("--teacher-id", type=int, help="Учитель, от имени которого создаются черновики.")
    parser.add_argument("--per-subject", type=int, default=5, help="Сколько тем на предмет (по умолчанию 5).")
    parser.add_argument("--limit", type=int, help="Не больше стольких уроков за запуск (для пробы).")
    parser.add_argument("--subject-ids", type=int, nargs="*", help="Только эти предметы (id).")
    parser.add_argument("--model", help="Вариант модели из /api/ai/models; пусто — модель по умолчанию.")
    asyncio.run(run(parser.parse_args()))
