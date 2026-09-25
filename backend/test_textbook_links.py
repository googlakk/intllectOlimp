import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from services.textbook_links import set_topic_links, suggest_links
from services.textbooks import TextbookServiceError
from textbooks.matching import SectionInfo
from textbooks.models import TopicTextbookLink

USER = SimpleNamespace(organization_id=5, profile_id=9, role="teacher")
BOOK = SimpleNamespace(id=1, subject_id=3, page_offset=1)
SECTIONS = [
    (SimpleNamespace(id=11), SectionInfo(11, "§ 5", "Буллинг", 31, 41, "Травля в школе")),
    (SimpleNamespace(id=12), SectionInfo(12, "§ 6", "Структура общества", 42, 48, "Социальные группы")),
]


def topic(id, name, lesson_type="study", resources=None):
    return SimpleNamespace(id=id, name=name, learning_objectives="", resources=resources, lesson_type=lesson_type)


class Result:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class Db:
    """Очередь ответов на scalars/execute в порядке запросов сервиса."""

    def __init__(self, *answers, subject_id=3):
        self.answers, self.added, self.executed = list(answers), [], []
        self.subject_id = subject_id

    async def get(self, model, key):
        return SimpleNamespace(id=key, subject_id=self.subject_id)

    async def scalars(self, statement):
        return Result(self.answers.pop(0))

    async def execute(self, statement):
        self.executed.append(statement)

    def add(self, row):
        self.added.append(row)

    async def commit(self):
        pass


def run(coro):
    return asyncio.run(coro)


class SuggestTests(unittest.TestCase):
    def test_only_topics_without_links_get_suggestions(self):
        topics = [
            topic(1, "Травля в школе и как её остановить"),
            topic(2, "Социальные группы", resources="Учебник § 6"),
            topic(3, "Уже привязанная тема"),
            topic(4, "Контрольная работа", lesson_type="assessment"),
            topic(5, "Экономика семьи"),
        ]
        db = Db([3])  # у темы 3 уже есть связь — её решение не трогаем
        with patch("services.textbook_links._book_with_subject", AsyncMock(return_value=BOOK)), \
             patch("services.textbook_links._subject_topics", AsyncMock(return_value=topics)), \
             patch("services.textbook_links._book_sections", AsyncMock(return_value=SECTIONS)):
            counts = run(suggest_links(1, db, user=USER))
        self.assertEqual(counts, {"confirmed": 1, "suggested": 1, "not_found": 1, "skipped": 2})
        by_topic = {link.topic_id: link for link in db.added}
        self.assertEqual((by_topic[1].section_id, by_topic[1].status), (11, "suggested"))
        self.assertEqual((by_topic[2].section_id, by_topic[2].status, by_topic[2].source), (12, "confirmed", "ktp"))
        self.assertNotIn(3, by_topic)

    def test_book_without_sections_is_refused(self):
        with patch("services.textbook_links._book_with_subject", AsyncMock(return_value=BOOK)), \
             patch("services.textbook_links._subject_topics", AsyncMock(return_value=[])), \
             patch("services.textbook_links._book_sections", AsyncMock(return_value=[])):
            with self.assertRaises(TextbookServiceError) as refused:
                run(suggest_links(1, Db(), user=USER))
        self.assertEqual(refused.exception.status_code, 409)


class SetLinksTests(unittest.TestCase):
    def patches(self):
        return (patch("services.textbook_links._book_with_subject", AsyncMock(return_value=BOOK)),
                patch("services.textbook_links.require_topic_management", AsyncMock(return_value=SimpleNamespace(id=7, section_id=40))))

    def test_teacher_choice_becomes_confirmed_and_other_links_are_rejected(self):
        old = TopicTextbookLink(topic_id=7, section_id=12, status="suggested", source="match")
        db = Db([11, 12], [old])
        first, second = self.patches()
        with first, second:
            result = run(set_topic_links(1, 7, [11], db, user=USER))
        self.assertEqual(result["section_ids"], [11])
        self.assertEqual(old.status, "rejected")  # решение запомнено — подбор его не вернёт
        chosen = db.added[0]
        self.assertEqual((chosen.section_id, chosen.status, chosen.role, chosen.confirmed_by_profile_id), (11, "confirmed", "primary", 9))

    def test_topic_of_another_subject_is_refused(self):
        first, second = self.patches()
        with first, second:
            with self.assertRaises(TextbookServiceError) as refused:
                run(set_topic_links(1, 7, [11], Db([11, 12], [], subject_id=99), user=USER))
        self.assertEqual(refused.exception.status_code, 422)

    def test_section_of_another_book_is_rejected(self):
        first, second = self.patches()
        with first, second:
            with self.assertRaises(TextbookServiceError):
                run(set_topic_links(1, 7, [99], Db([11, 12], []), user=USER))


if __name__ == "__main__":
    unittest.main()
