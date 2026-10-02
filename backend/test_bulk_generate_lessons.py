import argparse
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import bulk_generate_lessons as bulk


class Session:
    def __init__(self, existing=None):
        self.existing = existing
        self.rollback = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def scalar(self, statement):
        return self.existing


def args(**overrides):
    values = dict(apply=False, teacher_id=None, per_subject=5, limit=None, subject_ids=None, model=None)
    return argparse.Namespace(**{**values, **overrides})


SUBJECT = SimpleNamespace(id=1, name="Русский язык", grade=5)
TOPICS = [(SUBJECT, SimpleNamespace(id=index, name=f"Тема {index}")) for index in range(1, 6)]


def test_report_mode_never_generates(tmp_path, monkeypatch):
    monkeypatch.setattr(bulk, "LOG_PATH", tmp_path / "log.jsonl")
    generate = AsyncMock()
    with patch.object(bulk, "pending_topics", AsyncMock(return_value=TOPICS)), \
            patch.object(bulk, "print_teachers", AsyncMock()), \
            patch.object(bulk, "generate_one", generate), \
            patch.object(bulk, "engine", SimpleNamespace(dispose=AsyncMock())):
        asyncio.run(bulk.run(args()))
    generate.assert_not_awaited()
    assert not (tmp_path / "log.jsonl").exists()


def test_existing_lesson_is_not_regenerated():
    draft = AsyncMock()
    with patch.object(bulk, "AsyncSessionLocal", lambda: Session(existing=77)), \
            patch("services.lessons.generate_lesson_draft", draft):
        result = asyncio.run(bulk.generate_one(SUBJECT, TOPICS[0][1], teacher_id=3, model=None))
    assert result["status"] == "skipped_existing"
    draft.assert_not_awaited()


def test_stops_after_three_failures_in_a_row_and_respects_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(bulk, "LOG_PATH", tmp_path / "log.jsonl")
    failed = AsyncMock(return_value={"status": "failed", "error": "нет ключа"})
    with patch.object(bulk, "pending_topics", AsyncMock(return_value=TOPICS)), \
            patch.object(bulk, "generate_one", failed), \
            patch.object(bulk, "engine", SimpleNamespace(dispose=AsyncMock())):
        asyncio.run(bulk.run(args(apply=True, teacher_id=3)))
    assert failed.await_count == bulk.MAX_FAILURES_IN_ROW
    assert len((tmp_path / "log.jsonl").read_text(encoding="utf-8").splitlines()) == bulk.MAX_FAILURES_IN_ROW

    generated = AsyncMock(return_value={"status": "generated", "seconds": 1, "publishable": True, "errors": [], "textbook": False})
    with patch.object(bulk, "pending_topics", AsyncMock(return_value=TOPICS)), \
            patch.object(bulk, "generate_one", generated), \
            patch.object(bulk, "engine", SimpleNamespace(dispose=AsyncMock())):
        asyncio.run(bulk.run(args(apply=True, teacher_id=3, limit=2)))
    assert generated.await_count == 2


def test_apply_requires_a_teacher():
    with patch.object(bulk, "pending_topics", AsyncMock(return_value=TOPICS)):
        try:
            asyncio.run(bulk.run(args(apply=True)))
        except SystemExit as exc:
            assert "--teacher-id" in str(exc)
        else:
            raise AssertionError("ожидалась остановка без учителя")
