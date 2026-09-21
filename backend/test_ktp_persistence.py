import unittest
from types import SimpleNamespace

from ktp.persistence import KtpPersistenceError, save_ktp_draft
from models import Section, Subject, Topic


def topic(
    name,
    ktp_number="",
    hours=1,
    lesson_type="study",
    learning_objectives="",
    skills=None,
    resources="",
):
    return SimpleNamespace(
        ktp_number=ktp_number,
        name=name,
        hours=hours,
        lesson_type=lesson_type,
        learning_objectives=learning_objectives,
        skills=skills or [],
        resources=resources,
    )


def section(name, total_hours, topics):
    return SimpleNamespace(name=name, total_hours=total_hours, topics=topics)


class FakeSession:
    def __init__(self, fail_on_add_type=None):
        self.fail_on_add_type = fail_on_add_type
        self.rows = []
        self.commits = 0
        self.rollbacks = 0
        self.flushes = 0
        self.refreshed = []
        self._next_id = 100

    def add(self, row):
        if self.fail_on_add_type is not None and isinstance(row, self.fail_on_add_type):
            raise RuntimeError("db insert failed")
        self.rows.append(row)

    async def flush(self):
        self.flushes += 1
        for row in self.rows:
            if getattr(row, "id", None) is None:
                row.id = self._next_id
                self._next_id += 1

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    async def refresh(self, row):
        self.refreshed.append(row)


class KtpPersistenceTests(unittest.IsolatedAsyncioTestCase):
    def _payload(self):
        return SimpleNamespace(
            subject_name="Математика",
            grade=7,
            hours_per_week=4.0,
            hours_per_year=68,
            instruction_language="ru",
            sections=[
                section("Глава 1", 2, [
                    topic("Тема A", ktp_number="1", learning_objectives="Цель A"),
                    topic("Контрольная", ktp_number="2", lesson_type="assessment"),
                ]),
                section("Глава 2", 1, [
                    topic("Тема B", ktp_number="3", skills=["умение"]),
                ]),
            ],
        )

    async def test_save_ktp_draft_persists_subject_sections_and_topics(self):
        db = FakeSession()

        result = await save_ktp_draft(self._payload(), db)

        subjects = [row for row in db.rows if isinstance(row, Subject)]
        sections = [row for row in db.rows if isinstance(row, Section)]
        topics = [row for row in db.rows if isinstance(row, Topic)]
        self.assertEqual(len(subjects), 1)
        self.assertEqual(len(sections), 2)
        self.assertEqual(len(topics), 3)
        self.assertEqual([row.sort_order for row in sections], [1, 2])
        self.assertEqual([row.sort_order for row in topics], [1, 2, 1])
        self.assertEqual(result["section_count"], 2)
        self.assertEqual(result["topic_count"], 3)
        self.assertEqual(result["name"], "Математика")
        self.assertEqual(db.commits, 1)
        self.assertEqual(db.rollbacks, 0)
        self.assertEqual(db.refreshed, subjects)

    async def test_save_ktp_draft_rolls_back_on_failure(self):
        db = FakeSession(fail_on_add_type=Topic)

        with self.assertRaises(KtpPersistenceError):
            await save_ktp_draft(self._payload(), db)

        self.assertEqual(db.commits, 0)
        self.assertEqual(db.rollbacks, 1)


if __name__ == "__main__":
    unittest.main()
