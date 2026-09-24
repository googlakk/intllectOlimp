import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from errors import ApplicationError
from models import GeneratedLesson, Section, Topic
from routes.topics import TopicCreate, TopicUpdate
from services.topics import _apply_scope, set_topic_archived
from topic_semantics import infer_lesson_type


@pytest.mark.parametrize(('name', 'expected'), [
    ('Анализ контрольной работы', 'reflection'), ('Работа над ошибками', 'reflection'),
    ('Ключевые идеи Пересмотр', 'review'), ('Повторение', 'review'),
    ('Контрольная работа № 1', 'assessment'), ('Проект', 'project'), ('Квадратные корни', 'study'),
])
def test_purpose_recognized(name, expected):
    assert infer_lesson_type(name) == expected


def test_update_rejects_null_required_values_and_blank_title():
    for payload in ({'hours': None}, {'name': '   '}, {'lesson_type': None}, {'covered_topic_ids': None}):
        with pytest.raises(ValidationError):
            TopicUpdate(**payload)
    assert TopicUpdate(source_assessment_topic_id=None).model_dump(exclude_unset=True) == {'source_assessment_topic_id': None}
    assert TopicCreate(name='  Корни  ').name == 'Корни'


def topic(identifier, kind='study', **kwargs):
    return Topic(id=identifier, name='Тема', section_id=1, sort_order=identifier,
                 lesson_type=kind, covered_topic_ids=[], **kwargs)


class TopicLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_scope_defaults_and_rejects_foreign_or_future_topics(self):
        study, assessment, reflection = topic(1), topic(2, 'assessment'), topic(3, 'reflection')
        db = SimpleNamespace(scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: [study, assessment, reflection])))
        section = Section(id=1, subject_id=1)
        await _apply_scope(assessment, {}, section, db, creating=True)
        assert assessment.covered_topic_ids == [1]
        await _apply_scope(reflection, {}, section, db, creating=True)
        assert reflection.source_assessment_topic_id == 2
        assert reflection.covered_topic_ids == [1]
        for ids in ([3], [99]):
            with pytest.raises(ApplicationError):
                await _apply_scope(assessment, {'covered_topic_ids': ids}, section, db)


    async def test_empty_scope_requires_teacher_review(self):
        assessment = topic(1, 'assessment')
        db = SimpleNamespace(scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: [assessment])))
        await _apply_scope(assessment, {}, Section(id=1, subject_id=1), db)
        assert assessment.review_required


    async def test_archive_preserves_lesson_and_restore_withdraws_publication(self):
        item = topic(1)
        lesson = GeneratedLesson(id=4, topic_id=1, status='published', blocks=[{'text': 'retain'}])
        db = SimpleNamespace(scalar=AsyncMock(return_value=lesson))
        with patch('services.topics.require_topic_management', AsyncMock(return_value=item)), \
             patch('services.topics.require_section_management', AsyncMock(return_value=Section(id=1, subject_id=2))), \
             patch('services.topics._finish', AsyncMock(return_value={})):
            await set_topic_archived(1, True, object(), db)
            assert item.archived_at is not None
            assert lesson.status == 'published'
            await set_topic_archived(1, False, object(), db)
            assert item.archived_at is None
            assert lesson.status == 'draft'
            assert lesson.published_version_id is None
            assert lesson.blocks == [{'text': 'retain'}]
            assert item.review_required


    async def test_denied_management_does_not_mutate_topic(self):
        db = SimpleNamespace(scalar=AsyncMock())
        with patch('services.topics.require_topic_management', AsyncMock(side_effect=ApplicationError(403, 'Denied'))):
            with pytest.raises(ApplicationError):
                await set_topic_archived(1, True, object(), db)
        db.scalar.assert_not_awaited()


class ArchivedScopeTests(unittest.IsolatedAsyncioTestCase):
    async def test_existing_archived_assessment_link_survives_edit(self):
        from datetime import datetime, timezone
        study, assessment, reflection = topic(1), topic(2, 'assessment', archived_at=datetime.now(timezone.utc)), topic(3, 'reflection')
        reflection.source_assessment_topic_id = 2
        reflection.covered_topic_ids = [1]
        db = SimpleNamespace(scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: [study, assessment, reflection])))
        await _apply_scope(reflection, {'source_assessment_topic_id': 2}, Section(id=1, subject_id=1), db)
        self.assertEqual(reflection.source_assessment_topic_id, 2)
        other = topic(4, 'reflection')
        db.scalars.return_value = SimpleNamespace(all=lambda: [study, assessment, reflection, other])
        with self.assertRaises(ApplicationError):
            await _apply_scope(other, {'source_assessment_topic_id': 2}, Section(id=1, subject_id=1), db)


class ExplicitScopeTests(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_null_is_general_reflection_on_create_and_edit(self):
        study, assessment, reflection = topic(1), topic(2, 'assessment'), topic(3, 'reflection')
        assessment.covered_topic_ids = [1]
        db = SimpleNamespace(scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: [study, assessment, reflection])))
        section = Section(id=1, subject_id=1)
        await _apply_scope(reflection, {'source_assessment_topic_id': None}, section, db, creating=True)
        self.assertIsNone(reflection.source_assessment_topic_id)
        await _apply_scope(reflection, {}, section, db)
        self.assertIsNone(reflection.source_assessment_topic_id)
        reflection.covered_topic_ids = []
        await _apply_scope(reflection, {}, section, db)
        self.assertEqual(reflection.covered_topic_ids, [])
        self.assertTrue(reflection.review_required)
        await _apply_scope(reflection, {'covered_topic_ids': [1]}, section, db)
        self.assertFalse(reflection.review_required)

    async def test_scope_change_refreshes_derived_goals_but_preserves_authored_goals(self):
        from services.topics import update_topic
        for authored in (False, True):
            item = topic(3, 'assessment')
            item.skills = ['Вычислять корни']
            item.learning_objectives = 'Обосновывать ответ с помощью модели' if authored else 'Вычислять корни'
            item.covered_topic_ids = [1]
            first, second = topic(1), topic(2)
            db = SimpleNamespace(scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: [first, second, item])))
            with patch('services.topics.require_topic_management', AsyncMock(return_value=item)), \
                 patch('services.topics.require_section_management', AsyncMock(return_value=Section(id=1, subject_id=1))), \
                 patch('services.topics._finish', AsyncMock(return_value={})):
                await update_topic(3, {'covered_topic_ids': [2], 'learning_objectives': item.learning_objectives}, object(), db)
            self.assertEqual(item.learning_objectives, 'Обосновывать ответ с помощью модели' if authored else '')

    def test_create_request_preserves_explicit_null_source(self):
        values = TopicCreate(name='Разбор', lesson_type='reflection', source_assessment_topic_id=None).model_dump(exclude_unset=True)
        self.assertIn('source_assessment_topic_id', values)
        self.assertIsNone(values['source_assessment_topic_id'])
