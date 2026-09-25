import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import pytest
from errors import ApplicationError
from services import course_creation


def test_course_creation_checks_grade_before_writing(monkeypatch):
    db = SimpleNamespace(add=Mock())
    monkeypatch.setattr(course_creation, "require_grade_management", AsyncMock(side_effect=ApplicationError(403, "Denied")))
    with pytest.raises(ApplicationError):
        asyncio.run(course_creation.create_course("Math", 8, object(), db))
    db.add.assert_not_called()


def test_course_creation_includes_first_section(monkeypatch):
    rows = []
    async def flush():
        rows[0].id = 9
    db = SimpleNamespace(add=rows.append, flush=flush, commit=AsyncMock(), refresh=AsyncMock())
    monkeypatch.setattr(course_creation, "require_grade_management", AsyncMock())
    result = asyncio.run(course_creation.create_course(" Math ", 8, object(), db))
    assert result["name"] == "Math"
    assert rows[1].subject_id == 9
    assert rows[1].name == "Основной раздел"
    db.commit.assert_awaited_once()


def test_section_creation_checks_subject_before_writing(monkeypatch):
    db = SimpleNamespace(add=Mock())
    monkeypatch.setattr(course_creation, "require_subject_management", AsyncMock(side_effect=ApplicationError(404, "Denied")))
    with pytest.raises(ApplicationError):
        asyncio.run(course_creation.create_section(99, "Chapter", object(), db))
    db.add.assert_not_called()


def test_subject_rename_checks_access_before_writing(monkeypatch):
    db = SimpleNamespace(commit=AsyncMock())
    monkeypatch.setattr(course_creation, "require_subject_management", AsyncMock(side_effect=ApplicationError(403, "Denied")))
    with pytest.raises(ApplicationError):
        asyncio.run(course_creation.rename_subject(5, "Алгебра", object(), db))
    db.commit.assert_not_awaited()


def test_subject_rename_trims_and_keeps_grade(monkeypatch):
    subject = SimpleNamespace(id=5, name="Математика", grade=8, hours_per_week=3, hours_per_year=102,
                              source_info="КТП", instruction_language="ru")
    db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    monkeypatch.setattr(course_creation, "require_subject_management", AsyncMock(return_value=subject))
    result = asyncio.run(course_creation.rename_subject(5, "  Алгебра ", object(), db))
    assert result["name"] == "Алгебра"
    assert result["grade"] == 8
    db.commit.assert_awaited_once()
