import unittest
from copy import deepcopy
import hashlib
import re

from fastapi import HTTPException

from models import GeneratedLesson, Teacher, Topic
from objectives import (
    calculate_objective_mastery,
    decompose_objectives,
    normalize_lesson_blocks,
    quality_report,
)
from routes.lessons import PublishInput, publish
from routes.progress import derive_canonical_mastery


def without_service_metadata(value):
    if isinstance(value, dict):
        return {
            key: without_service_metadata(item)
            for key, item in value.items()
            if key not in {"objective_ids", "objective_id", "evidence_stage"}
        }
    if isinstance(value, list):
        return [without_service_metadata(item) for item in value]
    return value


def persisted_objective_id(text):
    normalized = re.sub(
        r"\s+",
        " ",
        text.casefold().replace("ё", "е"),
    ).strip(" \t\r\n-–—•.;:")
    return f"obj-{hashlib.sha1(normalized.encode('utf-8')).hexdigest()[:12]}"


class FakeLessonSession:
    def __init__(self, teacher, lesson, topic):
        self.teacher = teacher
        self.lesson = lesson
        self.topic = topic
        self.commits = 0

    async def get(self, model, row_id):
        if model is Teacher and row_id == self.teacher.id:
            return self.teacher
        if model is GeneratedLesson and row_id == self.lesson.id:
            return self.lesson
        if model is Topic and row_id == self.topic.id:
            return self.topic
        return None

    async def commit(self):
        self.commits += 1

    async def refresh(self, _row):
        return None


class ObjectiveQualityTests(unittest.TestCase):
    def test_decomposition_is_stable_and_deduplicates(self):
        raw = "1) Складывать числа; 2) Вычитать числа; 1) Складывать числа"
        first = decompose_objectives(raw)
        second = decompose_objectives(raw)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 2)
        self.assertTrue(first[0]["id"].startswith("obj-"))

    def test_compound_action_verbs_are_split_without_splitting_nouns(self):
        objectives = decompose_objectives("Складывать и вычитать целые числа; понимать связь квадратов и корней")
        self.assertEqual([item["text"] for item in objectives], [
            "Складывать целые числа", "вычитать целые числа", "понимать связь квадратов и корней"
        ])

    def test_comma_and_also_keep_one_objective(self):
        raw = (
            "Понять связь между квадратами и соответствующими квадратными корнями, "
            "а также кубами и соответствующими кубическими корнями."
        )
        objectives = decompose_objectives(raw)
        self.assertEqual(len(objectives), 1)
        self.assertIn("кубическими корнями", objectives[0]["text"])

    def test_comma_separates_independent_action_objectives(self):
        objectives = decompose_objectives("Складывать числа, вычитать числа")
        self.assertEqual(
            [item["text"] for item in objectives],
            ["Складывать числа", "вычитать числа"],
        )

    def test_existing_comma_objective_ids_remain_valid(self):
        objectives = decompose_objectives("Складывать числа, вычитать числа")
        self.assertEqual(objectives[0]["id"], persisted_objective_id("Складывать числа"))
        self.assertEqual(objectives[1]["id"], persisted_objective_id("вычитать числа"))
        blocks = [
            {"component": "RetrievalCheck", "content": {
                "objective_ids": [objectives[0]["id"]],
                "evidence_stage": "diagnostic",
                "type": "multiple_choice",
                "options": ["1", "2", "3", "4"],
                "correct_answer": "1",
            }},
            {"component": "RetrievalCheck", "content": {
                "objective_ids": [objectives[1]["id"]],
                "evidence_stage": "diagnostic",
                "type": "multiple_choice",
                "options": ["1", "2", "3", "4"],
                "correct_answer": "1",
            }},
        ]
        report = quality_report(blocks, "Складывать числа, вычитать числа")
        self.assertFalse(any(
            error["code"] == "unknown_objective"
            for error in report["quality_report"]["errors"]
        ))

    def test_prior_comma_split_ids_are_migrated_when_merge_is_unambiguous(self):
        raw = (
            "Понять связь между квадратами и соответствующими квадратными корнями, "
            "а также кубами и соответствующими кубическими корнями."
        )
        old_first = persisted_objective_id(
            "Понять связь между квадратами и соответствующими квадратными корнями"
        )
        old_second = persisted_objective_id(
            "а также кубами и соответствующими кубическими корнями"
        )
        blocks = [
            {"component": "RetrievalCheck", "content": {
                "objective_ids": [old_first],
                "evidence_stage": "diagnostic",
                "type": "multiple_choice",
                "options": ["1", "2", "3", "4"],
                "correct_answer": "1",
            }},
            {"component": "ShortExplanation", "content": {
                "objective_ids": [old_first, old_second],
                "evidence_stage": "explanation",
            }},
            {"component": "GuidedPractice", "content": {
                "objective_ids": [old_first, old_second],
                "evidence_stage": "practice",
            }},
            {"component": "MasteryCheck", "content": {
                "objective_ids": [old_second],
                "evidence_stage": "assessment",
                "questions": [{
                    "objective_ids": [old_second],
                    "type": "numeric",
                    "correct_answer": "2",
                }],
            }},
        ]
        report = quality_report(blocks, raw)
        canonical_id = report["objectives"][0]["id"]
        self.assertTrue(report["quality_report"]["publishable"])
        self.assertFalse(any(
            error["code"] == "unknown_objective"
            for error in report["quality_report"]["errors"]
        ))
        self.assertEqual(
            report["normalized_blocks"][1]["content"]["objective_ids"],
            [canonical_id],
        )
        self.assertEqual(
            report["normalized_blocks"][3]["content"]["questions"][0]["objective_ids"],
            [canonical_id],
        )

    def test_canonical_lesson_still_requires_diagnostic_before_teaching(self):
        objective = decompose_objectives("Складывать числа")[0]
        blocks = [
            {"component": "ShortExplanation", "content": {
                "objective_ids": [objective["id"]],
                "evidence_stage": "explanation",
            }},
            {"component": "RetrievalCheck", "content": {
                "objective_ids": [objective["id"]],
                "evidence_stage": "diagnostic",
                "type": "multiple_choice",
                "options": ["1", "2", "3", "4"],
                "correct_answer": "1",
            }},
            {"component": "GuidedPractice", "content": {
                "objective_ids": [objective["id"]],
                "evidence_stage": "practice",
            }},
            {"component": "MasteryCheck", "content": {
                "objective_ids": [objective["id"]],
                "evidence_stage": "assessment",
                "questions": [{
                    "objective_ids": [objective["id"]],
                    "type": "numeric",
                    "correct_answer": "2",
                }],
            }},
        ]
        report = quality_report(blocks, "Складывать числа")
        self.assertFalse(report["quality_report"]["publishable"])
        self.assertTrue(any(
            error["code"] == "diagnostic_after_teaching"
            for error in report["quality_report"]["errors"]
        ))

    def test_single_objective_legacy_metadata_is_restored_without_content_changes(self):
        objective = decompose_objectives("Вычислять кубические корни")[0]
        blocks = [
            {"component": "ShortExplanation", "content": {"text": "Содержание"}},
            {"component": "RetrievalCheck", "content": {
                "question": "Чему равен кубический корень из 8?",
                "type": "multiple_choice",
                "options": ["1", "2", "3", "4"],
                "correct_answer": "2",
            }},
            {"component": "MasteryCheck", "content": {"questions": [{
                "question": "Чему равен кубический корень из 27?",
                "dimension": "Кубические корни",
                "type": "numeric",
                "correct_answer": "3",
                "explanation": "3 в кубе равно 27",
            }]}},
        ]
        normalized, warnings = normalize_lesson_blocks(blocks, [objective])
        self.assertEqual(blocks[0]["content"], {"text": "Содержание"})
        self.assertEqual(normalized[0]["content"]["text"], "Содержание")
        self.assertEqual(normalized[0]["content"]["evidence_stage"], "explanation")
        self.assertEqual(normalized[1]["content"]["evidence_stage"], "diagnostic")
        self.assertEqual(normalized[2]["content"]["evidence_stage"], "assessment")
        self.assertEqual(normalized[2]["content"]["questions"][0]["objective_ids"], [objective["id"]])
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]["code"], "legacy_metadata_restored")

    def test_legacy_single_objective_mastery_is_derived_after_normalization(self):
        objective = decompose_objectives("Вычислять кубические корни")[0]
        blocks = [
            {"component": "RetrievalCheck", "content": {
                "question": "Чему равен кубический корень из 8?",
                "type": "multiple_choice",
                "options": ["1", "2", "3", "4"],
                "correct_answer": "2",
            }},
            {"component": "MasteryCheck", "content": {"questions": [{
                "question": "Чему равен кубический корень из 27?",
                "dimension": "Кубические корни",
                "type": "numeric",
                "correct_answer": "3",
                "explanation": "3 в кубе равно 27",
            }]}},
        ]
        mastery, evidence, overall = calculate_objective_mastery(
            blocks,
            [objective],
            {"0": True, "1_q0": True},
            {"0": 1, "1": 1},
            lesson_completed=True,
        )
        self.assertEqual(overall, "mastered")
        self.assertEqual(mastery[objective["id"]]["status"], "mastered")
        self.assertEqual(len(evidence[objective["id"]]), 2)

    def test_unmapped_multi_objective_legacy_mastery_keeps_route_fallback(self):
        derived = derive_canonical_mastery(
            [
                {"component": "RetrievalCheck", "content": {
                    "question": "Диагностический вопрос",
                    "type": "multiple_choice",
                    "options": ["1", "2", "3", "4"],
                    "correct_answer": "1",
                }},
                {"component": "MasteryCheck", "content": {"questions": [{
                    "question": "Итоговый вопрос",
                    "type": "numeric",
                    "correct_answer": "2",
                }]}},
            ],
            "Складывать числа; Вычитать числа",
            {"0": True, "1_q0": True},
            {"0": 1, "1": 1},
            lesson_completed=True,
        )
        self.assertIsNone(derived)

    def test_coverage_requires_all_three_evidence_stages(self):
        objective = decompose_objectives("Складывать числа")[0]
        blocks = [
            {"component": "RetrievalCheck", "content": {"objective_ids": [objective["id"]], "evidence_stage": "diagnostic", "type": "multiple_choice", "options": ["да", "нет", "не знаю", "иногда"], "correct_answer": "да"}},
            {"component": "ShortExplanation", "content": {"objective_ids": [objective["id"]], "evidence_stage": "explanation"}},
            {"component": "GuidedPractice", "content": {"objective_ids": [objective["id"]], "evidence_stage": "practice"}},
            {
                "component": "MasteryCheck",
                "content": {"evidence_stage": "assessment", "questions": [{"objective_ids": [objective["id"]], "type": "numeric", "correct_answer": "да"}]},
            },
        ]
        report = quality_report(blocks, "Складывать числа")
        self.assertTrue(report["quality_report"]["publishable"])
        self.assertEqual(report["quality_report"]["gaps"], [])
        mastery, _evidence, overall = calculate_objective_mastery(
            blocks,
            [objective],
            {"0": True, "3_q0": True},
            {"0": 1, "3": 1},
            lesson_completed=True,
        )
        self.assertEqual(mastery[objective["id"]]["status"], "mastered")
        self.assertEqual(overall, "mastered")

    def test_incomplete_legacy_lesson_is_normalized_but_not_publishable(self):
        report = quality_report(
            [{"component": "ShortExplanation", "content": {"title": "Теория"}}],
            "Складывать числа",
        )
        self.assertFalse(report["quality_report"]["publishable"])
        self.assertTrue(any(
            warning["code"] == "legacy_metadata_restored"
            for warning in report["quality_report"]["warnings"]
        ))
        self.assertTrue(report["quality_report"]["gaps"])

    def test_invalid_multiple_choice_answer_is_critical(self):
        objective = decompose_objectives("Складывать числа")[0]
        report = quality_report(
            [
                {"component": "ShortExplanation", "content": {"objective_ids": [objective["id"]]}},
                {"component": "IndependentProblem", "content": {
                    "objective_ids": [objective["id"]], "type": "multiple_choice",
                    "options": ["1", "2", "3", "4"], "correct_answer": "5",
                }},
                {"component": "MasteryCheck", "content": {
                    "questions": [{"objective_ids": [objective["id"]], "type": "numeric", "correct_answer": "1"}],
                }},
            ],
            "Складывать числа",
        )
        self.assertFalse(report["quality_report"]["publishable"])
        self.assertTrue(any(item["code"] == "answer_not_in_options" for item in report["quality_report"]["errors"]))

    def test_latex_arithmetic_mismatch_is_critical(self):
        objective = decompose_objectives("Вычислять выражения")[0]
        report = quality_report(
            [
                {"component": "RetrievalCheck", "content": {
                    "objective_ids": [objective["id"]], "evidence_stage": "diagnostic",
                    "type": "multiple_choice", "options": ["1", "2", "3", "4"], "correct_answer": "1",
                }},
                {"component": "ShortExplanation", "content": {
                    "objective_ids": [objective["id"]], "evidence_stage": "explanation",
                }},
                {"component": "IndependentProblem", "content": {
                    "objective_ids": [objective["id"]], "evidence_stage": "practice",
                    "type": "numeric",
                    "question": r"Вычисли: $(-5)^2 + (-3) \times 6 - (2 - 10)$",
                    "correct_answer": "9",
                }},
                {"component": "MasteryCheck", "content": {
                    "evidence_stage": "assessment",
                    "questions": [{
                        "objective_ids": [objective["id"]], "dimension": objective["id"],
                        "type": "numeric", "correct_answer": "15",
                    }],
                }},
            ],
            "Вычислять выражения",
        )
        self.assertFalse(report["quality_report"]["publishable"])
        self.assertTrue(any(
            item["code"] == "arithmetic_answer_mismatch"
            for item in report["quality_report"]["errors"]
        ))

    def test_mastery_block_tag_does_not_replace_question_mapping(self):
        objectives = decompose_objectives("Складывать числа; Вычитать числа")
        first, second = objectives
        blocks = [
            {"component": "RetrievalCheck", "content": {
                "objective_ids": [first["id"], second["id"]],
                "evidence_stage": "diagnostic",
                "type": "multiple_choice", "options": ["1", "2", "3", "4"], "correct_answer": "1",
            }},
            {"component": "ShortExplanation", "content": {
                "objective_ids": [first["id"], second["id"]], "evidence_stage": "explanation",
            }},
            {"component": "GuidedPractice", "content": {
                "objective_ids": [first["id"], second["id"]], "evidence_stage": "practice",
            }},
            {"component": "MasteryCheck", "content": {
                "objective_ids": [first["id"], second["id"]],
                "evidence_stage": "assessment",
                "questions": [{
                    "objective_ids": [first["id"]], "dimension": first["id"],
                    "type": "numeric", "correct_answer": "2",
                }],
            }},
        ]
        report = quality_report(blocks, "Складывать числа; Вычитать числа")
        second_gap = next(
            gap for gap in report["quality_report"]["gaps"]
            if gap["objective_id"] == second["id"]
        )
        self.assertIn("assessment", second_gap["missing"])

    def test_mastery_is_derived_per_question(self):
        objectives = decompose_objectives("Складывать числа; Вычитать числа")
        first, second = objectives
        blocks = [
            {"component": "RetrievalCheck", "content": {
                "objective_ids": [first["id"]], "evidence_stage": "diagnostic",
            }},
            {"component": "RetrievalCheck", "content": {
                "objective_ids": [second["id"]], "evidence_stage": "diagnostic",
            }},
            {"component": "MasteryCheck", "content": {
                "evidence_stage": "assessment",
                "questions": [
                    {"objective_ids": [first["id"]], "dimension": first["id"]},
                    {"objective_ids": [second["id"]], "dimension": second["id"]},
                ],
            }},
        ]
        mastery, evidence, overall = calculate_objective_mastery(
            blocks,
            objectives,
            {"0": True, "1": False, "2_q0": True, "2_q1": False},
            {"0": 1, "1": 1, "2": 1},
            lesson_completed=True,
        )
        self.assertEqual(mastery[first["id"]]["status"], "mastered")
        self.assertEqual(mastery[second["id"]]["status"], "needs_practice")
        self.assertEqual(overall, "needs_practice")
        self.assertEqual(evidence[first["id"]][-1]["question_index"], 0)

    def test_explanation_cannot_claim_final_assessment_coverage(self):
        objective = decompose_objectives("Складывать числа")[0]
        report = quality_report(
            [
                {"component": "RetrievalCheck", "content": {
                    "objective_ids": [objective["id"]], "evidence_stage": "diagnostic",
                    "type": "multiple_choice", "options": ["1", "2", "3", "4"], "correct_answer": "1",
                }},
                {"component": "ShortExplanation", "content": {
                    "objective_ids": [objective["id"]], "evidence_stage": "assessment",
                }},
                {"component": "GuidedPractice", "content": {
                    "objective_ids": [objective["id"]], "evidence_stage": "practice",
                }},
            ],
            "Складывать числа",
        )
        self.assertFalse(report["quality_report"]["publishable"])
        self.assertTrue(any(
            item["code"] == "stage_component_mismatch"
            for item in report["quality_report"]["errors"]
        ))

    def test_reflection_never_counts_as_objective_evidence(self):
        objective = decompose_objectives("Складывать числа")[0]
        blocks = [
            {"component": "RetrievalCheck", "content": {
                "objective_ids": [objective["id"]], "evidence_stage": "diagnostic",
                "type": "multiple_choice", "options": ["1", "2", "3", "4"], "correct_answer": "1",
            }},
            {"component": "ShortExplanation", "content": {
                "objective_ids": [objective["id"]], "evidence_stage": "explanation",
            }},
            {"component": "GuidedPractice", "content": {
                "objective_ids": [objective["id"]], "evidence_stage": "practice",
            }},
            {"component": "Reflection", "content": {
                "objective_ids": [objective["id"]], "evidence_stage": "assessment",
            }},
        ]
        report = quality_report(blocks, "Складывать числа")
        self.assertFalse(report["quality_report"]["publishable"])
        gap = report["quality_report"]["gaps"][0]
        self.assertIn("assessment", gap["missing"])

    def test_practice_answer_cannot_replace_final_evidence(self):
        objective = decompose_objectives("Складывать числа")[0]
        blocks = [
            {"component": "RetrievalCheck", "content": {
                "objective_ids": [objective["id"]], "evidence_stage": "diagnostic",
            }},
            {"component": "GuidedPractice", "content": {
                "objective_ids": [objective["id"]], "evidence_stage": "practice",
            }},
            {"component": "MasteryCheck", "content": {
                "evidence_stage": "assessment",
                "questions": [{"objective_ids": [objective["id"]], "dimension": objective["id"]}],
            }},
        ]
        mastery, evidence, overall = calculate_objective_mastery(
            blocks,
            [objective],
            {"0": True, "1": True, "2_q0": False},
            {"0": 1, "1": 1, "2": 1},
            lesson_completed=True,
        )
        self.assertEqual(mastery[objective["id"]]["status"], "needs_practice")
        self.assertEqual(overall, "needs_practice")
        self.assertFalse(any(item["block_index"] == 1 for item in evidence[objective["id"]]))

    def test_one_question_cannot_prove_multiple_objectives(self):
        objectives = decompose_objectives("Складывать числа; Вычитать числа")
        first, second = objectives
        blocks = [
            {"component": "RetrievalCheck", "content": {
                "objective_ids": [first["id"], second["id"]],
                "evidence_stage": "diagnostic",
                "type": "multiple_choice", "options": ["1", "2", "3", "4"], "correct_answer": "1",
            }},
            {"component": "ShortExplanation", "content": {
                "objective_ids": [first["id"], second["id"]], "evidence_stage": "explanation",
            }},
            {"component": "GuidedPractice", "content": {
                "objective_ids": [first["id"], second["id"]], "evidence_stage": "practice",
            }},
            {"component": "MasteryCheck", "content": {
                "evidence_stage": "assessment",
                "questions": [{
                    "objective_ids": [first["id"], second["id"]],
                    "type": "numeric",
                    "correct_answer": "2",
                }],
            }},
        ]
        report = quality_report(blocks, "Складывать числа; Вычитать числа")
        self.assertFalse(report["quality_report"]["publishable"])
        self.assertTrue(any(
            item["code"] == "ambiguous_objective_evidence"
            for item in report["quality_report"]["errors"]
        ))
        mastery, evidence, overall = calculate_objective_mastery(
            blocks,
            objectives,
            {"0": True, "3_q0": True},
            {"0": 1, "3": 1},
            lesson_completed=True,
        )
        self.assertEqual(overall, "needs_practice")
        self.assertFalse(evidence[first["id"]])
        self.assertFalse(evidence[second["id"]])


class LessonPublishRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_complete_legacy_lesson_requires_ack_and_persists_metadata_only(self):
        raw_objective = "Вычислять кубические корни"
        original_blocks = [
            {"component": "RetrievalCheck", "content": {
                "question": "Чему равен кубический корень из 8?",
                "type": "multiple_choice",
                "options": ["1", "2", "3", "4"],
                "correct_answer": "2",
            }},
            {"component": "ShortExplanation", "content": {"text": "Кубический корень обращает возведение в куб."}},
            {"component": "GuidedPractice", "content": {"question": "Найди кубический корень из 64."}},
            {"component": "MasteryCheck", "content": {"questions": [{
                "question": "Чему равен кубический корень из 27?",
                "dimension": "Кубические корни",
                "type": "numeric",
                "correct_answer": "3",
                "explanation": "3 в кубе равно 27",
            }]}},
        ]
        teacher = Teacher(id=7, name="Проверяющий преподаватель")
        topic = Topic(
            id=6,
            section_id=1,
            ktp_number="1",
            name="Кубические корни",
            hours=1,
            lesson_type="study",
            learning_objectives=raw_objective,
            skills=[],
            resources=None,
        )
        lesson = GeneratedLesson(
            id=4,
            topic_id=topic.id,
            blocks=deepcopy(original_blocks),
            lesson_metadata={},
            status="draft",
            published_at=None,
            published_by=None,
            model_used="legacy",
        )
        db = FakeLessonSession(teacher, lesson, topic)

        with self.assertRaises(HTTPException) as rejected:
            await publish(
                lesson.id,
                PublishInput(teacher_id=teacher.id, acknowledge_warnings=False),
                db,
            )
        self.assertEqual(rejected.exception.status_code, 422)
        self.assertEqual(db.commits, 0)

        response = await publish(
            lesson.id,
            PublishInput(teacher_id=teacher.id, acknowledge_warnings=True),
            db,
        )
        self.assertEqual(response["status"], "published")
        self.assertEqual(db.commits, 1)
        self.assertEqual(
            without_service_metadata(lesson.blocks),
            without_service_metadata(original_blocks),
        )
        subsequent = quality_report(lesson.blocks, raw_objective)
        self.assertTrue(subsequent["quality_report"]["publishable"])
        self.assertEqual(subsequent["quality_report"]["warnings"], [])

    async def test_publish_migrates_prior_comma_split_ids_to_canonical_objective(self):
        raw_objective = (
            "Понять связь между квадратами и соответствующими квадратными корнями, "
            "а также кубами и соответствующими кубическими корнями."
        )
        old_first = persisted_objective_id(
            "Понять связь между квадратами и соответствующими квадратными корнями"
        )
        old_second = persisted_objective_id(
            "а также кубами и соответствующими кубическими корнями"
        )
        blocks = [
            {"component": "RetrievalCheck", "content": {
                "objective_ids": [old_first],
                "evidence_stage": "diagnostic",
                "type": "multiple_choice",
                "options": ["1", "2", "3", "4"],
                "correct_answer": "1",
            }},
            {"component": "ShortExplanation", "content": {
                "objective_ids": [old_first, old_second],
                "evidence_stage": "explanation",
            }},
            {"component": "GuidedPractice", "content": {
                "objective_ids": [old_first, old_second],
                "evidence_stage": "practice",
            }},
            {"component": "MasteryCheck", "content": {
                "objective_ids": [old_second],
                "evidence_stage": "assessment",
                "questions": [{
                    "objective_ids": [old_second],
                    "type": "numeric",
                    "correct_answer": "2",
                }],
            }},
        ]
        teacher = Teacher(id=8, name="Преподаватель совместимости")
        topic = Topic(
            id=8,
            section_id=1,
            ktp_number="2",
            name="Корни",
            hours=1,
            lesson_type="study",
            learning_objectives=raw_objective,
            skills=[],
            resources=None,
        )
        lesson = GeneratedLesson(
            id=8,
            topic_id=topic.id,
            blocks=deepcopy(blocks),
            lesson_metadata={"objectives": [
                {"id": old_first, "text": "Квадратные корни"},
                {"id": old_second, "text": "Кубические корни"},
            ]},
            status="draft",
            published_at=None,
            published_by=None,
            model_used="legacy",
        )
        db = FakeLessonSession(teacher, lesson, topic)

        response = await publish(
            lesson.id,
            PublishInput(teacher_id=teacher.id, acknowledge_warnings=True),
            db,
        )
        canonical_id = response["lesson_metadata"]["objectives"][0]["id"]
        self.assertEqual(response["status"], "published")
        self.assertEqual(len(response["lesson_metadata"]["objectives"]), 1)
        self.assertEqual(
            response["blocks"][1]["content"]["objective_ids"],
            [canonical_id],
        )
        subsequent = quality_report(response["blocks"], raw_objective)
        self.assertTrue(subsequent["quality_report"]["publishable"])
        self.assertFalse(subsequent["quality_report"]["errors"])


if __name__ == "__main__":
    unittest.main()