import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from models import Progress, LessonVersion
from routes.progress import ProgressInput
from services.progress import save_progress_record, restart_progress_record, ProgressServiceError
from services.assessment import equal_answer, grade_assessment
from lesson_contracts import adapt_legacy_blocks
from objectives import decompose_objectives


def fixture():
    goal = 'Вычислять квадратный корень'
    objective_id = decompose_objectives(goal)[0]['id']
    blocks = [{'component': 'RetrievalCheck', 'content': {
        'question': 'Корень из 9?', 'options': ['3', '9'], 'correct_answer': '3', 'explanation': '3 × 3 = 9',
        'objective_ids': [objective_id], 'evidence_stage': 'assessment'}}]
    lesson = SimpleNamespace(id=4, topic_id=3, published_version_id=10, active_version_id=11, status='published', blocks=[])
    version = LessonVersion(id=10, lesson_id=4, version_number=1, blueprint={'lesson_type': 'assessment', 'learning_objectives': goal}, lesson_document=adapt_legacy_blocks(blocks, {'learning_objectives': goal}))
    topic = SimpleNamespace(id=3, archived_at=None, lesson_type='assessment', learning_objectives=goal)
    row = Progress(id=1, student_id=2, topic_id=3, status='completed', attempts=1, lesson_version_id=10,
                   answers={'0': True}, objective_mastery={}, objective_evidence={}, responses={'0': '3'}, score=100)
    return lesson, version, topic, row


def run_save(payload, db, topic):
    with patch('services.progress.require_topic_access', AsyncMock(return_value=topic)), \
         patch('services.progress.require_curriculum_topic_access', AsyncMock()), \
         patch('services.progress.update_topic_skill_mastery', AsyncMock()) as skills, \
         patch('services.progress.refresh_student_access', AsyncMock(return_value=[])):
        result = asyncio.run(save_progress_record(payload, db))
        return result, skills


def test_submission_grades_raw_responses_against_published_version():
    lesson, version, topic, row = fixture()
    db = AsyncMock()
    db.scalar.side_effect = [2, None, lesson, row, 1]
    db.get.return_value = version
    payload = ProgressInput(student_id=2, topic_id=3, lesson_version_id=10,
                            responses={'0': '9'}, answers={'0': True}, score=100)
    _, skills = run_save(payload, db, topic)
    assert payload.answers == {'0': False}
    assert payload.score == 0
    assert skills.await_count == 1
    evidence = skills.call_args.kwargs['evidence']
    assert evidence['objective_evidence']
    assert all(item['score'] == 0 for item in evidence['objective_mastery'].values())


def test_duplicate_completed_save_does_not_add_evidence_or_snapshot():
    _, _, topic, row = fixture()
    db = AsyncMock()
    db.scalar.side_effect = [2, row]
    result, skills = run_save(ProgressInput(student_id=2, topic_id=3), db, topic)
    assert result is row
    assert db.scalar.await_count == 2
    skills.assert_not_awaited()


def test_snapshot_conflict_does_not_duplicate_skill_evidence():
    lesson, version, topic, row = fixture()
    db = AsyncMock()
    db.scalar.side_effect = [2, None, lesson, row, None]
    db.get.return_value = version
    _, skills = run_save(ProgressInput(student_id=2, topic_id=3, responses={'0': '3'}), db, topic)
    skills.assert_not_awaited()


def test_in_progress_save_does_not_reveal_correctness():
    lesson, version, topic, row = fixture()
    row.status = 'in_progress'
    db = AsyncMock()
    db.scalar.side_effect = [2, None, lesson, row]
    db.get.return_value = version
    payload = ProgressInput(student_id=2, topic_id=3, status='in_progress', responses={'0': '3'})
    _, skills = run_save(payload, db, topic)
    assert payload.answers == {} and payload.score is None
    skills.assert_not_awaited()


def test_new_attempt_on_archived_topic_is_rejected():
    _, _, topic, _ = fixture()
    topic.archived_at = '2026-09-24'
    db = AsyncMock()
    db.scalar.side_effect = [2, None]
    with pytest.raises(ProgressServiceError, match='убран'):
        run_save(ProgressInput(student_id=2, topic_id=3), db, topic)


def test_foreign_or_draft_version_cannot_be_submitted():
    lesson, version, topic, row = fixture()
    db = AsyncMock()
    db.scalar.side_effect = [2, None, lesson]
    with pytest.raises(ProgressServiceError, match='изменилась'):
        run_save(ProgressInput(student_id=2, topic_id=3, lesson_version_id=11), db, topic)


def test_numeric_grading_is_finite_and_accepts_decimal_comma():
    assert equal_answer(' 3,0 ', '3')
    assert not equal_answer('NaN', 'NaN')
    assert not equal_answer('', '')
    answers, score = grade_assessment([{'component':'MasteryCheck','content':{'questions':[
        {'correct_answer':'2'}, {'correct_answer':'4'}]}}], {'0_q0':'2', '0_q1':'3'})
    assert answers == {'0_q0':True, '0_q1':False} and score == 50
