import argparse
import asyncio
import json
from contextlib import contextmanager
from time import perf_counter
from typing import Any

from sqlalchemy import event

from database import AsyncSessionLocal, engine, warm_database_pool
from services.curriculum_graph import get_student_curriculum_map
from services.catalog import list_subject_outline
from services.lessons import clear_lesson_manifest_cache, get_student_lesson_manifest


@contextmanager
def count_sql_statements():
    sync_engine = engine.sync_engine
    stats = {"count": 0}

    def before_cursor_execute(*_args):
        stats["count"] += 1

    event.listen(sync_engine, "before_cursor_execute", before_cursor_execute)
    try:
        yield stats
    finally:
        event.remove(sync_engine, "before_cursor_execute", before_cursor_execute)


async def measure(label: str, fn) -> dict[str, Any]:
    with count_sql_statements() as sql:
        started = perf_counter()
        payload = await fn()
        elapsed_ms = round((perf_counter() - started) * 1000, 2)
    payload_bytes = len(json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"))
    return {
        "label": label,
        "elapsed_ms": elapsed_ms,
        "sql_statements": sql["count"],
        "payload_bytes": payload_bytes,
        "_payload": payload,
    }


async def run(student_id: int, topic_id: int, subject_id: int | None) -> list[dict[str, Any]]:
    async with AsyncSessionLocal() as db:
        manifest = await measure(
            "lesson_manifest",
            lambda: get_student_lesson_manifest(topic_id=topic_id, student_id=student_id, db=db),
        )
        await db.rollback()
        curriculum = await measure(
            "curriculum_map",
            lambda: get_student_curriculum_map(student_id, db, subject_id=subject_id),
        )
        await db.rollback()
    return [manifest, curriculum]


def summarize_manifest(data: dict[str, Any]) -> dict[str, Any]:
    lesson = data["lesson"]
    progress = data["progress"]
    return {
        "topic_id": lesson["topic_id"],
        "lesson_id": lesson["id"],
        "blocks": len(lesson.get("blocks") or []),
        "has_lesson_document": isinstance(lesson.get("lesson_document"), dict),
        "progress_status": progress.get("status") if progress else None,
    }


def summarize_curriculum(data: dict[str, Any]) -> dict[str, Any]:
    topics = data.get("topics") or []
    return {
        "topics": len(topics),
        "available": sum(1 for topic in topics if topic.get("state") in {"available", "in_progress", "mastered"}),
        "published": sum(1 for topic in topics if topic.get("lesson_status") == "published"),
    }


def summarize_subject_outline(data: list[dict[str, Any]]) -> dict[str, Any]:
    topics = [
        topic
        for section in data
        for topic in (section.get("topics") or [])
    ]
    return {
        "sections": len(data),
        "topics": len(topics),
        "published": sum(1 for topic in topics if topic.get("lesson_status") == "published"),
        "contains_blocks": any("blocks" in topic or "lesson_document" in topic for topic in topics),
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Measure lesson hot-path backend calls.")
    parser.add_argument("--student-id", type=int, required=True)
    parser.add_argument("--topic-id", type=int, required=True)
    parser.add_argument("--subject-id", type=int)
    parser.add_argument("--refresh-map", action="store_true", help="Force curriculum access refresh before reading the course map.")
    args = parser.parse_args()

    results = []
    results.append(await measure("db_warmup", warm_database_pool))
    results[-1].pop("_payload")
    clear_lesson_manifest_cache(args.topic_id)
    async with AsyncSessionLocal() as db:
        results.append(await measure(
            "lesson_manifest",
            lambda: get_student_lesson_manifest(topic_id=args.topic_id, student_id=args.student_id, db=db),
        ))
        results[-1].update(summarize_manifest(results[-1].pop("_payload")))
        await db.rollback()
        results.append(await measure(
            "lesson_manifest_cached",
            lambda: get_student_lesson_manifest(topic_id=args.topic_id, student_id=args.student_id, db=db),
        ))
        results[-1].update(summarize_manifest(results[-1].pop("_payload")))
        await db.rollback()
        results.append(await measure(
            "curriculum_map",
            lambda: get_student_curriculum_map(
                args.student_id,
                db,
                subject_id=args.subject_id,
                refresh=args.refresh_map,
            ),
        ))
        results[-1].update(summarize_curriculum(results[-1].pop("_payload")))
        await db.rollback()
        results.append(await measure(
            "curriculum_map_cached",
            lambda: get_student_curriculum_map(
                args.student_id,
                db,
                subject_id=args.subject_id,
                refresh=False,
            ),
        ))
        results[-1].update(summarize_curriculum(results[-1].pop("_payload")))
        await db.rollback()
        if args.subject_id is not None:
            results.append(await measure(
                "subject_outline",
                lambda: list_subject_outline(args.subject_id, db),
            ))
            results[-1].update(summarize_subject_outline(results[-1].pop("_payload")))
            await db.rollback()
            results.append(await measure(
                "subject_outline_cached",
                lambda: list_subject_outline(args.subject_id, db),
            ))
            results[-1].update(summarize_subject_outline(results[-1].pop("_payload")))
            await db.rollback()

    print(json.dumps(results, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
