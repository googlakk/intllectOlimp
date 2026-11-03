"""Student answer capture is independent from grading and the tutor."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import asyncio
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

from routes.progress import ProgressInput
from services.progress import save_progress_record, restart_progress_record, snapshot_attempt


def payload(**values):
    return ProgressInput(student_id=2, topic_id=3, status="in_progress", **values)


@pytest.mark.parametrize("details", [
    {"2_q0": {"value": "42 кг", "outcome": "wrong_unit", "questionIndex": 0}},
    {"0": {"value": "A → Б; B → В", "outcome": "correct"}},
])
def test_response_input_accepts_values_without_replacing_raw_control_responses(details):
    request = payload(response_details=details, responses={"0": "42"})
    assert request.responses == {"0": "42"}
    assert request.response_details[next(iter(details))].value == details[next(iter(details))]["value"]


def test_old_clients_omit_details_and_invalid_keys_are_rejected():
    assert payload().response_details is None
    with pytest.raises(ValidationError):
        payload(response_details={"bad-key": {"value": "x", "outcome": "correct"}})


@pytest.mark.parametrize("details", [None, {"0": {"value": "17", "outcome": "incorrect"}}])
def test_save_preserves_omitted_details_but_records_new_submission(details):
    asyncio.run(save_preserves_omitted_details_but_records_new_submission(details))


async def save_preserves_omitted_details_but_records_new_submission(details):
    request = payload(**({"response_details": details} if details is not None else {}))
    row = SimpleNamespace(id=1, student_id=2, topic_id=3, status="in_progress")
    lesson = SimpleNamespace(id=5, status="published", blocks=[], published_version_id=None)
    db = SimpleNamespace(scalar=AsyncMock(side_effect=[2, None, lesson, row]), commit=AsyncMock())
    topic = SimpleNamespace(archived_at=None, lesson_type="study", learning_objectives=None)
    with patch("services.progress.require_topic_access", AsyncMock(return_value=topic)):
        await save_progress_record(request, db)
    statement = db.scalar.await_args_list[-1].args[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    update_sql = str(compiled).split("DO UPDATE SET", 1)[1]
    if details is None:
        assert "ELSE progress.response_details" in update_sql
    else:
        assert details in compiled.params.values()
    assert "WHEN (progress.status =" in update_sql


def test_completed_attempt_does_not_accept_new_details():
    asyncio.run(completed_attempt_does_not_accept_new_details())


async def completed_attempt_does_not_accept_new_details():
    row = SimpleNamespace(status="completed", response_details={"0": {"value": "original"}})
    db = SimpleNamespace(scalar=AsyncMock(side_effect=[2, row]), commit=AsyncMock())
    with patch("services.progress.require_topic_access", AsyncMock()):
        result = await save_progress_record(payload(response_details={"0": {"value": "new", "outcome": "correct"}}), db)
    assert result.response_details["0"]["value"] == "original"
    assert db.scalar.await_count == 2


def test_restart_clears_response_maps_and_snapshot_keeps_previous_answers():
    asyncio.run(restart_clears_response_maps_and_snapshot_keeps_previous_answers())


async def restart_clears_response_maps_and_snapshot_keeps_previous_answers():
    row = SimpleNamespace(status="completed", response_details={"0": {"value": "old"}})
    lesson = SimpleNamespace(status="published", published_version_id=8)
    fresh = SimpleNamespace(status="in_progress", response_details={})
    db = SimpleNamespace(scalar=AsyncMock(side_effect=[2, row, lesson, fresh]), commit=AsyncMock())
    with patch("services.progress.require_topic_access", AsyncMock(return_value=SimpleNamespace(archived_at=None))), \
         patch("services.progress.snapshot_attempt", AsyncMock()) as snapshot:
        await restart_progress_record(2, 3, db)
    snapshot.assert_awaited_once_with(row, db)
    compiled = db.scalar.await_args_list[-1].args[0].compile(dialect=postgresql.dialect())
    assert compiled.params["response_details"] == {}
    assert compiled.params["responses"] == {}


def test_attempt_snapshot_contains_saved_details():
    asyncio.run(attempt_snapshot_contains_saved_details())


async def attempt_snapshot_contains_saved_details():
    details = {"2_q0": {"value": "A", "outcome": "incorrect"}}
    row = SimpleNamespace(student_id=2, topic_id=3, attempts=1, lesson_version_id=7, completed_at=None)
    db = SimpleNamespace(scalar=AsyncMock(return_value=1))
    with patch("services.progress.serialize_progress", return_value={"response_details": details}):
        await snapshot_attempt(row, db)
    compiled = db.scalar.await_args.args[0].compile(dialect=postgresql.dialect())
    assert compiled.params["snapshot"]["response_details"] == details


def test_control_work_metadata_is_derived_from_raw_response_without_changing_the_grade():
    from services.assessment import assessment_outcomes, grade_assessment
    blocks = [{"component": "IndependentProblem", "content": {"question": "Длина", "type": "numeric", "correct_answer": "5", "answer_unit": "м"}}]
    assert assessment_outcomes(blocks, {"0": "5 см"}) == {"0": "wrong_unit"}
    assert grade_assessment(blocks, {"0": "5 см"}) == ({"0": False}, 0)
    asyncio.run(control_metadata_is_canonical(blocks))


async def control_metadata_is_canonical(blocks):
    request = ProgressInput(student_id=2, topic_id=3, status="completed", responses={"0": "5 см"},
                            response_details={"0": {"value": "spoofed answer", "outcome": "correct"}})
    row = SimpleNamespace(id=1, student_id=2, topic_id=3, status="completed")
    lesson = SimpleNamespace(id=5, status="published", blocks=blocks, published_version_id=None)
    topic = SimpleNamespace(archived_at=None, lesson_type="assessment", learning_objectives=None)
    db = SimpleNamespace(scalar=AsyncMock(side_effect=[2, None, lesson, row]), commit=AsyncMock())
    with patch("services.progress.require_topic_access", AsyncMock(return_value=topic)), \
         patch("services.progress.snapshot_attempt", AsyncMock(return_value=False)):
        await save_progress_record(request, db)
    assert request.answers == {"0": False}
    assert request.score == 0
    compiled = db.scalar.await_args_list[-1].args[0].compile(dialect=postgresql.dialect())
    assert compiled.params["response_details"] == {"0": {"value": "5 см", "outcome": "wrong_unit"}}
