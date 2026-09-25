import unittest
from copy import deepcopy
import hashlib
import re
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from models import GeneratedLesson, Section, Student, Subject, Teacher, Topic
from objectives import (
    calculate_objective_mastery,
    decompose_objectives,
    normalize_lesson_blocks,
    quality_report,
)
from services.lessons import (
    LessonServiceError,
    delete_lesson_record,
    generate_lesson_draft,
    get_lesson_by_topic,
    get_lesson_quality,
    publish_lesson,
    update_lesson_blocks,
    unpublish_lesson,
)
from services.progress import derive_canonical_mastery


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
        self.student = Student(id=9, name="Ученик", grade=7)
        self.section = Section(id=topic.section_id, subject_id=70, name="Раздел", sort_order=1, total_hours=1)
        self.subject = Subject(
            id=70,
            name="Математика",
            grade=7,
            hours_per_week=4,
            hours_per_year=136,
            source_info=None,
            instruction_language="ru",
        )
        self.commits = 0
        self.deleted = []
        self.get_calls = []

    async def get(self, model, row_id):
        self.get_calls.append((model, row_id))
        if model is Teacher and row_id == self.teacher.id:
            return self.teacher
        if model is GeneratedLesson and row_id == self.lesson.id:
            return self.lesson
        if model is Topic and row_id == self.topic.id:
            return self.topic
        if model is Student and row_id == self.student.id:
            return self.student
        if model is Section and row_id == self.section.id:
            return self.section
        if model is Subject and row_id == self.subject.id:
            return self.subject
        return None

    async def execute(self, _statement):
        return SimpleNamespace(first=lambda: None)

    async def scalar(self, _statement):
        return self.lesson

    async def commit(self):
        self.commits += 1

    async def refresh(self, _row):
        return None

    async def delete(self, row):
        self.deleted.append(row)


class _FakeExecuteResult:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class FakeGenerateSession:
    def __init__(self, teacher, topic, section, subject, lesson=None):
        self.teacher = teacher
        self.topic = topic
        self.section = section
        self.subject = subject
        self.lesson = lesson
        self.added = []
        self.commits = 0

    async def get(self, model, row_id):
        if model is Teacher and self.teacher is not None and row_id == self.teacher.id:
            return self.teacher
        return None

    async def execute(self, _statement):
        if self.topic is None:
            return _FakeExecuteResult(None)
        return _FakeExecuteResult((self.topic, self.section, self.subject))

    async def scalar(self, _statement):
        return self.lesson

    def add(self, row):
        self.added.append(row)
        self.lesson = row

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

    def test_conjunction_does_not_split_objective(self):
        # Союз «и» внутри предложения — часть формулировки КТП, а не граница цели.
        objectives = decompose_objectives("Складывать и вычитать целые числа; понимать связь квадратов и корней")
        self.assertEqual([item["text"] for item in objectives], [
            "Складывать и вычитать целые числа", "понимать связь квадратов и корней"
        ])

    def test_sentences_become_separate_objectives(self):
        raw = (
            "Оценивать, складывать и вычитать целые числа, распознавая обобщения. "
            "Помните, что скобки, положительные индексы и операции следуют определенному порядку."
        )
        objectives = decompose_objectives(raw)
        self.assertEqual([item["text"] for item in objectives], [
            "Оценивать, складывать и вычитать целые числа, распознавая обобщения.",
            "Помните, что скобки, положительные индексы и операции следуют определенному порядку.",
        ])

    def test_abbreviation_dot_does_not_split_objective(self):
        objectives = decompose_objectives("Разобрать задачи из учебника стр. 12 и записать вывод.")
        self.assertEqual(len(objectives), 1)

    def test_comma_and_also_keep_one_objective(self):
        raw = (
            "Понять связь между квадратами и соответствующими квадратными корнями, "
            "а также кубами и соответствующими кубическими корнями."
        )
        objectives = decompose_objectives(raw)
        self.assertEqual(len(objectives), 1)
        self.assertIn("кубическими корнями", objectives[0]["text"])

    def test_comma_keeps_one_objective(self):
        objectives = decompose_objectives("Складывать числа, вычитать числа")
        self.assertEqual(
            [item["text"] for item in objectives],
            ["Складывать числа, вычитать числа"],
        )

    def test_existing_comma_objective_ids_remain_valid(self):
        # Уроки, сгенерированные до перехода на предложения, ссылаются на ID
        # обрывков до и после запятой — они должны переноситься на одну цель.
        objectives = decompose_objectives("Складывать числа, вычитать числа")
        self.assertEqual(len(objectives), 1)
        blocks = [
            {"component": "RetrievalCheck", "content": {
                "objective_ids": [persisted_objective_id("Складывать числа")],
                "evidence_stage": "diagnostic",
                "type": "multiple_choice",
                "options": ["1", "2", "3", "4"],
                "correct_answer": "1",
            }},
            {"component": "RetrievalCheck", "content": {
                "objective_ids": [persisted_objective_id("вычитать числа")],
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
        for block in report["normalized_blocks"]:
            self.assertEqual(block["content"]["objective_ids"], [objectives[0]["id"]])

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

    def test_interactive_engine_components_can_cover_lesson_contract(self):
        objective = decompose_objectives("Объяснять круговорот воды")[0]
        blocks = [
            {"component": "RetrievalCheck", "content": {
                "objective_ids": [objective["id"]],
                "evidence_stage": "diagnostic",
                "type": "multiple_choice",
                "question": "Что запускает испарение?",
                "options": ["Солнце", "Луна", "Гром", "Снег"],
                "correct_answer": "Солнце",
                "explanation": "Солнечная энергия нагревает воду.",
            }},
            {"component": "PredictionLab", "content": {
                "objective_ids": [objective["id"]],
                "evidence_stage": "explanation",
                "title": "Прогноз",
                "question": "Что будет с водой при нагревании?",
                "options": [{"id": "evaporates", "label": "Испарится"}],
                "correct_prediction": "evaporates",
                "observation_title": "Наблюдение",
                "observations": [{"label": "Температура", "value": "выше"}],
                "explanation": "Вода испаряется.",
            }},
            {"component": "ProcessBuilder", "content": {
                "objective_ids": [objective["id"]],
                "evidence_stage": "practice",
                "title": "Цикл",
                "instruction": "Соберите этапы",
                "steps": [{"id": "a", "label": "Испарение"}, {"id": "b", "label": "Осадки"}],
                "correct_edges": [{"from": "a", "to": "b"}],
                "explanation": "Этапы связаны.",
            }},
            {"component": "SortAndClassify", "content": {
                "objective_ids": [objective["id"]],
                "evidence_stage": "assessment",
                "title": "Проверка",
                "instruction": "Распределите",
                "groups": [{"id": "water", "label": "Вода"}],
                "items": [{"id": "rain", "label": "Дождь", "correct_group": "water"}],
                "explanation": "Дождь относится к воде.",
            }},
            {"component": "MasteryCheck", "content": {"questions": [{
                "objective_ids": [objective["id"]],
                "dimension": objective["id"],
                "question": "Какой этап возвращает воду на поверхность?",
                "type": "multiple_choice",
                "options": ["Осадки", "Сжатие", "Плавление", "Трение"],
                "correct_answer": "Осадки",
                "explanation": "Осадки возвращают воду.",
            }]}},
        ]

        report = quality_report(blocks, "Объяснять круговорот воды")

        self.assertTrue(report["quality_report"]["publishable"])
        self.assertFalse(report["quality_report"]["errors"])

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


def complete_single_objective_blocks(raw_objective):
    objective = decompose_objectives(raw_objective)[0]
    return [
        {"component": "RetrievalCheck", "content": {
            "objective_ids": [objective["id"]],
            "evidence_stage": "diagnostic",
            "type": "multiple_choice",
            "question": "Диагностика",
            "options": ["1", "2", "3", "4"],
            "correct_answer": "1",
            "explanation": "Проверка перед объяснением.",
        }},
        {"component": "ShortExplanation", "content": {
            "objective_ids": [objective["id"]],
            "evidence_stage": "explanation",
            "title": "Объяснение",
            "text": "Короткое объяснение.",
            "key_concepts": ["идея"],
        }},
        {"component": "GuidedPractice", "content": {
            "objective_ids": [objective["id"]],
            "evidence_stage": "practice",
            "question": "Практика",
            "hints": ["Подсказка"],
            "input_type": "numeric",
            "correct_answer": "1",
            "explanation": "Разбор.",
        }},
        {"component": "MasteryCheck", "content": {
            "objective_ids": [objective["id"]],
            "evidence_stage": "assessment",
            "questions": [{
                "objective_ids": [objective["id"]],
                "question": "Итог",
                "type": "numeric",
                "correct_answer": "1",
                "explanation": "Ответ.",
                "dimension": objective["id"],
            }],
        }},
        {"component": "Reflection", "content": {
            "prompt": "Что получилось?",
            "scale_question": "Насколько уверенно?",
            "scale_labels": ["1", "2", "3", "4"],
        }},
    ]


class LessonGenerateServiceTests(unittest.IsolatedAsyncioTestCase):
    def _context(self, lesson=None):
        teacher = Teacher(id=3, name="Генератор")
        subject = Subject(
            id=11,
            name="Математика",
            grade=7,
            hours_per_week=2,
            hours_per_year=68,
            source_info=None,
            instruction_language="ru",
        )
        section = Section(
            id=12,
            subject_id=subject.id,
            name="Числа",
            sort_order=1,
            total_hours=8,
        )
        topic = Topic(
            id=13,
            section_id=section.id,
            ktp_number="1",
            name="Сложение",
            hours=1,
            lesson_type="study",
            learning_objectives="Складывать числа",
            skills=["вычисления"],
            resources="учебник",
        )
        return teacher, topic, section, subject, FakeGenerateSession(
            teacher, topic, section, subject, lesson=lesson,
        )

    async def test_generate_creates_draft_with_quality_metadata(self):
        teacher, topic, _section, _subject, db = self._context()

        async def fake_generator(**kwargs):
            self.assertEqual(kwargs["topic_name"], topic.name)
            self.assertEqual(kwargs["subject_name"], "Математика")
            return complete_single_objective_blocks(topic.learning_objectives)

        lesson = await generate_lesson_draft(
            topic_id=topic.id,
            teacher_id=teacher.id,
            db=db,
            lesson_generator=fake_generator,
        )

        self.assertEqual(db.commits, 1)
        self.assertEqual(db.added, [lesson])
        self.assertEqual(lesson.topic_id, topic.id)
        self.assertEqual(lesson.status, "draft")
        self.assertIsNone(lesson.published_at)
        self.assertIsNone(lesson.published_by)
        self.assertEqual(lesson.lesson_metadata["teacher_id"], teacher.id)
        self.assertEqual(lesson.lesson_metadata["subject_family"], "mathematical")
        self.assertEqual(lesson.lesson_metadata["topic_contract"]["volume"], "micro")
        self.assertEqual(lesson.lesson_metadata["lesson_shape"], "procedure_mastery")
        self.assertEqual(lesson.lesson_metadata["block_budget"]["min"], 5)
        self.assertTrue(lesson.lesson_metadata["component_plan"])
        self.assertIn("quality_report", lesson.lesson_metadata)

    async def test_generate_uses_selected_model_and_records_it(self):
        teacher, topic, _section, _subject, db = self._context()
        seen = {}

        async def fake_generator(**kwargs):
            seen.update(kwargs)
            return complete_single_objective_blocks(topic.learning_objectives)

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "sk-or-test"}):
            lesson = await generate_lesson_draft(
                topic_id=topic.id,
                teacher_id=teacher.id,
                db=db,
                lesson_generator=fake_generator,
                model_choice="openrouter:openai/gpt-6-sol",
            )

        self.assertEqual(seen["model_route"].model, "openai/gpt-6-sol")
        self.assertEqual(
            lesson.lesson_metadata["generation_model"],
            {"provider": "openrouter", "model": "openai/gpt-6-sol"},
        )

    async def test_generate_rejects_unlisted_model_before_calling_provider(self):
        teacher, topic, _section, _subject, db = self._context()

        async def fake_generator(**_kwargs):
            raise AssertionError("провайдер не должен вызываться")

        with self.assertRaises(LessonServiceError) as rejected:
            await generate_lesson_draft(
                topic_id=topic.id,
                teacher_id=teacher.id,
                db=db,
                lesson_generator=fake_generator,
                model_choice="openrouter:evil/any-model",
            )

        self.assertEqual(rejected.exception.status_code, 422)
        self.assertEqual(db.commits, 0)

    async def test_generate_reuses_existing_lesson_row(self):
        teacher, topic, _section, _subject, db = self._context(
            lesson=GeneratedLesson(
                id=20,
                topic_id=13,
                blocks=[],
                lesson_metadata={"old": True},
                status="published",
            )
        )

        async def fake_generator(**_kwargs):
            return complete_single_objective_blocks(topic.learning_objectives)

        lesson = await generate_lesson_draft(
            topic_id=topic.id,
            teacher_id=teacher.id,
            db=db,
            lesson_generator=fake_generator,
        )

        self.assertEqual(lesson.id, 20)
        self.assertEqual(db.added, [])
        self.assertEqual(lesson.status, "published")
        self.assertIsNone(lesson.published_by)

    async def test_generate_failure_is_reported_as_provider_failure(self):
        teacher, topic, _section, _subject, db = self._context()

        async def broken_generator(**_kwargs):
            raise RuntimeError("лимит модели")

        with self.assertRaises(LessonServiceError) as rejected:
            await generate_lesson_draft(
                topic_id=topic.id,
                teacher_id=teacher.id,
                db=db,
                lesson_generator=broken_generator,
            )

        self.assertEqual(rejected.exception.status_code, 502)
        self.assertIn("лимит модели", str(rejected.exception.detail))
        self.assertEqual(db.commits, 0)


class LessonManagementServiceTests(unittest.IsolatedAsyncioTestCase):
    def _context(self, *, status="published", blocks=None, metadata=None):
        teacher = Teacher(id=5, name="Методист")
        topic = Topic(
            id=21,
            section_id=1,
            ktp_number="3",
            name="Сложение",
            hours=1,
            lesson_type="study",
            learning_objectives="Складывать числа",
            skills=[],
            resources=None,
        )
        lesson = GeneratedLesson(
            id=31,
            topic_id=topic.id,
            blocks=deepcopy(blocks if blocks is not None else complete_single_objective_blocks(topic.learning_objectives)),
            lesson_metadata=deepcopy(metadata if metadata is not None else {}),
            status=status,
            published_at="published",
            published_by=teacher.id,
            model_used="test-model",
        )
        return lesson, FakeLessonSession(teacher, lesson, topic)

    async def test_get_lesson_by_topic_refreshes_quality_contract_without_commit(self):
        lesson, db = self._context(metadata={"legacy": True})

        found = await get_lesson_by_topic(topic_id=lesson.topic_id, role="teacher", db=db)

        self.assertIs(found, lesson)
        self.assertEqual(db.commits, 0)
        self.assertTrue(found.lesson_metadata["legacy"])
        self.assertIn("objectives", found.lesson_metadata)
        self.assertIn("quality_report", found.lesson_metadata)

    async def test_get_lesson_by_topic_reuses_current_quality_contract(self):
        metadata = {
            "objectives": [{"id": "obj-current", "text": "Складывать числа"}],
            "quality_report": {"publishable": True},
        }
        lesson, db = self._context(metadata=metadata)

        found = await get_lesson_by_topic(topic_id=lesson.topic_id, role="teacher", db=db)

        self.assertIs(found, lesson)
        self.assertEqual(found.lesson_metadata, metadata)
        self.assertNotIn((Topic, lesson.topic_id), db.get_calls)

    async def test_get_lesson_by_topic_uses_student_not_ready_message(self):
        lesson, db = self._context()
        db.lesson = None

        with self.assertRaises(LessonServiceError) as rejected:
            await get_lesson_by_topic(
                topic_id=lesson.topic_id,
                role="student",
                db=db,
                student_id=db.student.id,
            )

        self.assertEqual(rejected.exception.status_code, 404)
        self.assertEqual(rejected.exception.detail, "Опубликованный урок пока не готов")

    async def test_update_lesson_blocks_preserves_publication_and_persists_draft_quality(self):
        lesson, db = self._context()
        new_blocks = complete_single_objective_blocks("Складывать числа")

        updated = await update_lesson_blocks(lesson.id, new_blocks, db)

        self.assertIs(updated, lesson)
        self.assertEqual(db.commits, 1)
        self.assertEqual(updated.status, "published")
        self.assertEqual(updated.published_at, "published")
        self.assertEqual(updated.published_by, 5)
        self.assertTrue(updated.lesson_metadata["quality_report"]["publishable"])

    async def test_lesson_quality_reports_current_contract(self):
        lesson, db = self._context()

        report = await get_lesson_quality(lesson.id, db)

        self.assertEqual(len(report["objectives"]), 1)
        self.assertTrue(report["quality_report"]["publishable"])

    async def test_unpublish_lesson_resets_publication_fields(self):
        lesson, db = self._context()

        unpublished = await unpublish_lesson(lesson.id, db)

        self.assertIs(unpublished, lesson)
        self.assertEqual(db.commits, 1)
        self.assertEqual(unpublished.status, "draft")
        self.assertIsNone(unpublished.published_at)
        self.assertIsNone(unpublished.published_by)

    async def test_delete_lesson_record_deletes_and_returns_api_message(self):
        lesson, db = self._context(status="draft")
        db.scalar = AsyncMock(return_value=False)

        result = await delete_lesson_record(lesson.id, db)

        self.assertEqual(result, {"message": "Урок удалён"})
        self.assertEqual(db.deleted, [lesson])
        self.assertEqual(db.commits, 1)


class LessonPublishServiceTests(unittest.IsolatedAsyncioTestCase):
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

        with self.assertRaises(LessonServiceError) as rejected:
            await publish_lesson(
                lesson_id=lesson.id,
                teacher_id=teacher.id,
                acknowledge_warnings=False,
                db=db,
            )
        self.assertEqual(rejected.exception.status_code, 422)
        self.assertEqual(db.commits, 0)

        published = await publish_lesson(
            lesson_id=lesson.id,
            teacher_id=teacher.id,
            acknowledge_warnings=True,
            db=db,
        )
        self.assertEqual(published.status, "published")
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

        published = await publish_lesson(
            lesson_id=lesson.id,
            teacher_id=teacher.id,
            acknowledge_warnings=True,
            db=db,
        )
        canonical_id = published.lesson_metadata["objectives"][0]["id"]
        self.assertEqual(published.status, "published")
        self.assertEqual(len(published.lesson_metadata["objectives"]), 1)
        self.assertEqual(
            published.blocks[1]["content"]["objective_ids"],
            [canonical_id],
        )
        subsequent = quality_report(published.blocks, raw_objective)
        self.assertTrue(subsequent["quality_report"]["publishable"])
        self.assertFalse(subsequent["quality_report"]["errors"])


if __name__ == "__main__":
    unittest.main()
