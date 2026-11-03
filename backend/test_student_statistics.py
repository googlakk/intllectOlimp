import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from errors import ApplicationError
from services.dashboard import get_student_lesson_report
from services.student_statistics import build_attempt_detail, lesson_row, summarize_lessons


def document(*blocks):
    return {"objectives": [{"id": "O1", "text": "Сложить дроби"}],
            "episodes": [{"scenes": [{"block": block} for block in blocks]}]}


def row(topic_id=1, *, status="completed", score=90, grade=7, published=True, archived=False,
        latest=None, mastery="mastered", level="Уверенный"):
    topic = SimpleNamespace(id=topic_id, name="Дроби", archived_at="2026-01-01" if archived else None)
    subject = SimpleNamespace(id=12, name="Математика", grade=grade)
    progress = None if status == "not_started" else SimpleNamespace(
        status=status, score=score, mastery_status=mastery, mastery_level=level, elapsed_time_sec=60,
        answers={"0": score != 0})
    return lesson_row(topic, subject, published, progress, latest, 7)


class StatisticsCalculationsTests(unittest.TestCase):
    def test_zero_is_a_grade_but_missing_and_unassessed_are_not(self):
        summary = summarize_lessons([row(1, score=0), row(2, score=100), row(3, score=None),
                                     row(4, score=0, level="Не оценено"), row(5, status="in_progress", score=30)])
        self.assertEqual(summary["completed"], 4)
        self.assertEqual(summary["in_progress"], 1)
        self.assertEqual(summary["average_score"], 50)

    def test_retry_keeps_completed_result_without_counting_twice(self):
        latest = {"status": "completed", "score": 75, "mastery_status": "needs_practice",
                  "completed_at": "2026-01-01T00:00:00Z", "elapsed_time_sec": 120, "answers": {"0": False}}
        lesson = row(status="in_progress", score=None, latest=latest)
        summary = summarize_lessons([lesson])
        self.assertTrue(lesson["retrying"])
        self.assertEqual(summary["completed"], 1)
        self.assertEqual(summary["in_progress"], 1)
        self.assertEqual(summary["needs_practice"], 1)
        self.assertEqual(summary["average_score"], 75)

    def test_archive_other_grade_and_unpublished_are_historical(self):
        lessons = [row(1), row(2, archived=True), row(3, grade=8), row(4, published=False),
                   row(5, status="not_started")]
        summary = summarize_lessons(lessons)
        self.assertEqual(summary["completed"], 1)
        self.assertEqual(summary["total_published"], 2)
        self.assertEqual(summary["completed_published"], 1)
        self.assertEqual(summary["progress_percent"], 50)
        self.assertEqual(sum(lesson["historical"] for lesson in lessons), 3)

    def test_empty_subject_has_no_grade_and_no_division_by_zero(self):
        summary = summarize_lessons([])
        self.assertIsNone(summary["average_score"])
        self.assertEqual(summary["total_published"], 0)
        self.assertEqual(summary["progress_percent"], 0)

    def test_saved_zero_without_any_assessment_evidence_is_not_a_grade(self):
        from services.student_statistics import assessed_score
        self.assertIsNone(assessed_score({"status": "completed", "score": 0}))
        self.assertEqual(assessed_score({"status": "completed", "score": 0, "answers": {"0": False}}), 0)


class LessonBreakdownTests(unittest.TestCase):
    def test_saved_response_and_grade_are_read_without_regrading(self):
        lesson = document({"component": "IndependentProblem", "content": {
            "question": "1/2 + 1/2?", "correct_answer": "1", "explanation": "Две половины — целое.",
            "evidence_stage": "assessment"}})
        snapshot = {"status": "completed", "score": 0, "answers": {"0": False},
                    "response_details": {"0": {"value": "3", "outcome": "incorrect"}},
                    "attempts_by_step": {"0": 2}, "objective_mastery": {"O1": {"status": "needs_practice", "score": 0}}}
        detail = build_attempt_detail(snapshot, lesson)
        self.assertEqual(detail["score"], 0)
        self.assertEqual(detail["objectives"][0]["status"], "needs_practice")
        self.assertEqual(detail["questions"][0], {
            "key": "0", "block_index": 0, "question_index": None, "component": "IndependentProblem",
            "stage": "assessment", "prompt": "1/2 + 1/2?", "response": "3", "outcome": "incorrect",
            "expected": "1", "explanation": "Две половины — целое.", "attempts": 2, "variant": None})

    def test_raw_control_responses_are_supported_and_zero_is_not_lost(self):
        lesson = document({"component": "MasteryCheck", "content": {"questions": [
            {"question": "Сколько?", "correct_answer": "0"}, {"question": "Единицы?", "correct_answer": "2 м"}]}})
        detail = build_attempt_detail({"status": "completed", "responses": {"0_q0": "0"},
            "answers": {"0_q0": True}, "response_details": {"0_q1": {"value": "2 с", "outcome": "wrong_unit"}}}, lesson)
        first, second = detail["questions"]
        self.assertEqual(first["response"], "0")
        self.assertEqual(first["outcome"], "correct")
        self.assertEqual(second["outcome"], "wrong_unit")

    def test_legacy_boolean_does_not_invent_the_student_answer(self):
        lesson = document({"component": "RetrievalCheck", "content": {"question": "Выбери", "correct_answer": "А"}})
        question = build_attempt_detail({"answers": {"0": False}}, lesson)["questions"][0]
        self.assertIsNone(question["response"])
        self.assertEqual(question["outcome"], "incorrect")

    def test_missing_pinned_version_never_uses_current_lesson_content(self):
        result = build_attempt_detail({"status": "completed", "score": 80, "lesson_version_id": 42,
                                      "answers": {"0": False}, "response_details": {"0": {"value": "старый ответ", "outcome": "incorrect"}}}, None)
        self.assertFalse(result["version_available"])
        self.assertEqual(result["questions"][0]["prompt"], "Версия задания недоступна")
        self.assertEqual(result["questions"][0]["response"], "старый ответ")
        self.assertIsNone(result["questions"][0]["expected"])
        self.assertEqual(result["questions"][0]["stage"], "unknown")
        self.assertEqual(result["score"], 80)

    def test_learning_path_selects_saved_variant_question(self):
        lesson = document({"component": "LearningPath", "content": {"checkpoints": [{"label": "Остановка",
            "support": {"question": "Простой вопрос", "options": ["А", "Б"], "correct_index": 0},
            "challenge": {"question": "Сложный вопрос", "options": ["В", "Г"], "correct_index": 1}}]}})
        question = build_attempt_detail({"response_details": {"0_q0": {"value": "В", "variant": "challenge", "outcome": "incorrect"}}}, lesson)["questions"][0]
        self.assertEqual(question["prompt"], "Сложный вопрос\n\nВ\nГ")
        self.assertEqual(question["expected"], "Г")
        self.assertEqual(question["variant"], "challenge")

    def test_text_evidence_condition_includes_passage(self):
        lesson = document({"component": "TextEvidencePicker", "content": {"claim": "Докажи", "passage": "Сам текст", "correct_segments": ["цитата"]}})
        question = build_attempt_detail({}, lesson)["questions"][0]
        self.assertIn("Сам текст", question["prompt"])
        self.assertEqual(question["expected"], "цитата")

    def test_server_graded_control_ignores_spoofed_answer_metadata(self):
        lesson = document({"component": "RetrievalCheck", "content": {"question": "Выбери", "correct_answer": "А"}})
        snapshot = {"status": "completed", "answers": {"0": False}, "responses": {"0": "Б"},
                    "response_details": {"0": {"value": "А", "outcome": "correct"}}}
        question = build_attempt_detail(snapshot, lesson, server_graded=True)["questions"][0]
        self.assertEqual(question["response"], "Б")
        self.assertEqual(question["outcome"], "incorrect")

    def test_control_with_no_raw_response_never_falls_back_to_client_metadata(self):
        lesson = document({"component": "RetrievalCheck", "content": {"question": "Выбери", "correct_answer": "А"}})
        snapshot = {"status": "completed", "answers": {"0": False}, "responses": {},
                    "response_details": {"0": {"value": "А", "outcome": "correct"}}}
        question = build_attempt_detail(snapshot, lesson, server_graded=True)["questions"][0]
        self.assertIsNone(question["response"])
        self.assertEqual(question["outcome"], "incorrect")
        missing_version = build_attempt_detail(snapshot, None, server_graded=True)["questions"][0]
        self.assertIsNone(missing_version["response"])
        self.assertEqual(missing_version["outcome"], "incorrect")

    def test_unfinished_control_metadata_is_not_a_server_verdict(self):
        lesson = document({"component": "RetrievalCheck", "content": {"question": "Выбери", "correct_answer": "А"}})
        snapshot = {"status": "in_progress", "answers": {}, "responses": {"0": "Б"},
                    "response_details": {"0": {"value": "А", "outcome": "correct"}}}
        question = build_attempt_detail(snapshot, lesson, server_graded=True)["questions"][0]
        self.assertEqual(question["response"], "Б")
        self.assertIsNone(question["outcome"])

    def test_missing_version_ignores_oversized_legacy_response_keys(self):
        result = build_attempt_detail({"response_details": {"9" * 5000: {"value": "x", "outcome": "correct"}}}, None)
        self.assertEqual(result["questions"], [])

    def test_control_unit_error_is_derived_from_raw_response_not_client_claim(self):
        lesson = document({"component": "IndependentProblem", "content": {
            "question": "Найди длину", "type": "numeric", "correct_answer": "2", "answer_unit": "м"}})
        snapshot = {"status": "completed", "answers": {"0": False}, "responses": {"0": "2 с"},
                    "response_details": {"0": {"value": "2 м", "outcome": "correct"}}}
        question = build_attempt_detail(snapshot, lesson, server_graded=True)["questions"][0]
        self.assertEqual(question["response"], "2 с")
        self.assertEqual(question["outcome"], "wrong_unit")
        snapshot["responses"]["0"] = "ошибочный текст"
        snapshot["response_details"]["0"]["outcome"] = "wrong_unit"
        question = build_attempt_detail(snapshot, lesson, server_graded=True)["questions"][0]
        self.assertEqual(question["outcome"], "incorrect")

    def test_saved_control_failure_is_not_regraded_when_current_checker_accepts_answer(self):
        lesson = document({"component": "IndependentProblem", "content": {"question": "Найди", "correct_answer": "2"}})
        snapshot = {"status": "completed", "answers": {"0": False}, "responses": {"0": "2"}}
        question = build_attempt_detail(snapshot, lesson, server_graded=True)["questions"][0]
        self.assertEqual(question["outcome"], "incorrect")


class LessonReportAccessTests(unittest.IsolatedAsyncioTestCase):
    async def test_invisible_student_is_denied_before_reading_lesson(self):
        db = SimpleNamespace(scalar=AsyncMock(return_value=None), execute=AsyncMock())
        with self.assertRaises(ApplicationError) as denied:
            await get_student_lesson_report(2, 31, db, user=SimpleNamespace(role="teacher", teacher_id=5))
        self.assertEqual(denied.exception.status_code, 404)
        self.assertEqual(db.scalar.await_count, 1)
        db.execute.assert_not_awaited()

    async def test_foreign_subject_is_denied_before_progress_read(self):
        assignments = MagicMock(); assignments.all.return_value = [(12,)]
        db = SimpleNamespace(scalar=AsyncMock(side_effect=[SimpleNamespace(id=2), None]),
                             execute=AsyncMock(return_value=assignments))
        with self.assertRaises(ApplicationError):
            await get_student_lesson_report(2, 31, db, user=SimpleNamespace(role="teacher", teacher_id=5, organization_id=1))
        query = str(db.scalar.await_args_list[-1].args[0].compile(compile_kwargs={"literal_binds": True}))
        self.assertIn("sections.subject_id IN (12)", query)
        self.assertEqual(db.scalar.await_count, 2)

    async def test_unstarted_lesson_has_no_invented_attempt(self):
        empty = MagicMock(); empty.scalars.return_value.all.return_value = []
        db = SimpleNamespace(scalar=AsyncMock(side_effect=[SimpleNamespace(id=2), SimpleNamespace(name="Дроби"), None]),
                             execute=AsyncMock(return_value=empty))
        report = await get_student_lesson_report(2, 31, db, user=SimpleNamespace(role="admin"))
        self.assertIsNone(report["current"])
        self.assertIsNone(report["last_completed"])

    async def test_retry_uses_each_pinned_version_not_latest_published_blocks(self):
        progress = SimpleNamespace(status="in_progress", lesson_version_id=43)
        attempt = SimpleNamespace(topic_id=31, lesson_version_id=42, completed_at=None,
                                  snapshot={"status": "completed", "score": 0, "answers": {"0": False}})
        attempt_result, version_result = MagicMock(), MagicMock()
        attempt_result.scalars.return_value.all.return_value = [attempt]
        def version(number, answer):
            return SimpleNamespace(id=number, lesson_document=document({"component": "IndependentProblem", "content": {
                "question": f"Вопрос версии {number}", "correct_answer": answer}}))
        version_result.scalars.return_value.all.return_value = [version(42, "старый"), version(43, "новый")]
        db = SimpleNamespace(scalar=AsyncMock(side_effect=[SimpleNamespace(id=2), SimpleNamespace(name="Дроби"), progress]),
                             execute=AsyncMock(side_effect=[attempt_result, version_result]))
        result = await get_student_lesson_report(2, 31, db, user=SimpleNamespace(role="admin"))
        self.assertEqual(result["current"]["questions"][0]["expected"], "новый")
        self.assertEqual(result["last_completed"]["questions"][0]["expected"], "старый")
        version_query = str(db.execute.await_args_list[-1].args[0].compile(compile_kwargs={"literal_binds": True}))
        self.assertIn("generated_lessons.topic_id = 31", version_query)

    async def test_pinned_control_type_takes_priority_over_changed_topic_type(self):
        progress = SimpleNamespace(status="completed", lesson_version_id=42, score=0,
            answers={"0": False}, responses={"0": "Б"}, response_details={"0": {"value": "А", "outcome": "correct"}})
        empty, version_result = MagicMock(), MagicMock()
        empty.scalars.return_value.all.return_value = []
        version_result.scalars.return_value.all.return_value = [SimpleNamespace(id=42, blueprint={"lesson_type": "assessment"},
            lesson_document=document({"component": "RetrievalCheck", "content": {"question": "Выбери", "correct_answer": "А"}}))]
        db = SimpleNamespace(scalar=AsyncMock(side_effect=[SimpleNamespace(id=2), SimpleNamespace(name="Дроби", lesson_type="study"), progress]),
                             execute=AsyncMock(side_effect=[empty, version_result]))
        result = await get_student_lesson_report(2, 31, db, user=SimpleNamespace(role="admin"))
        self.assertEqual(result["current"]["questions"][0]["response"], "Б")
        self.assertEqual(result["current"]["questions"][0]["outcome"], "incorrect")


class ReportTaskWordingTests(unittest.TestCase):
    def test_solver_condition_contains_the_actual_equation_and_prediction_uses_label(self):
        from services.student_statistics import question_prompt, expected_answer
        self.assertIn("2x+3=7", question_prompt("StepSolver", {"instruction": "Реши", "start": "2x+3=7"}))
        self.assertEqual(expected_answer("PredictionLab", {"correct_prediction": "yes", "options": [{"id": "yes", "label": "Ускорится"}]}), "Ускорится")
