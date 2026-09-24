import unittest

from ai.planner import build_topic_contract
from objectives import quality_report


def plan(**overrides):
    data = {
        "topic_name": "Сложение чисел",
        "subject_name": "Математика",
        "learning_objectives": "Складывать числа",
        "skills": ["вычисления"],
        "resources": "учебник",
        "grade": 7,
        "hours": 1,
        "lesson_type": "study",
        "content_language": "ru",
    }
    data.update(overrides)
    return build_topic_contract(**data)


class PlannerTests(unittest.TestCase):
    def test_one_hour_single_objective_is_micro(self):
        result = plan()
        contract = result["topic_contract"]

        self.assertEqual(contract["volume"], "micro")
        self.assertEqual(contract["lesson_shape"], "procedure_mastery")
        self.assertEqual(contract["block_budget"], {"min": 5, "max": 7, "heavy_max": 1})
        self.assertTrue(result["component_plan"])

    def test_two_hours_two_objectives_is_standard_not_extended(self):
        result = plan(
            hours=2,
            learning_objectives="Складывать числа. Вычитать числа.",
        )

        self.assertEqual(result["topic_contract"]["volume"], "standard")
        self.assertEqual(result["topic_contract"]["block_budget"]["min"], 8)

    def test_math_argumentation_skill_does_not_turn_procedure_into_source_lesson(self):
        result = plan(
            hours=2,
            topic_name="Множители и множители",
            learning_objectives="Понимать, что такое наименьшее общее кратное и наибольший общий делитель.",
            skills=["Убеждение /аргументация", "Обобщение"],
        )

        self.assertEqual(result["topic_contract"]["learning_focus"], "procedure")
        self.assertEqual(result["topic_contract"]["lesson_shape"], "procedure_mastery")

    def test_three_objectives_becomes_extended(self):
        result = plan(
            hours=3,
            learning_objectives="Найти органоиды. Объяснить функции. Сравнить клетки.",
            subject_name="Биология",
            topic_name="Строение клетки",
        )

        self.assertEqual(result["topic_contract"]["volume"], "extended")
        self.assertEqual(result["topic_contract"]["lesson_shape"], "process_inquiry")
        self.assertEqual(result["topic_contract"]["media_policy"], "suggested")

    def test_four_hours_becomes_unit_part(self):
        result = plan(hours=4, learning_objectives="Понять большую тему")

        self.assertEqual(result["topic_contract"]["volume"], "unit")
        self.assertEqual(result["topic_contract"]["lesson_shape"], "unit_part")
        self.assertEqual(result["topic_contract"]["module_part_index"], 1)
        self.assertGreaterEqual(result["topic_contract"]["module_total_parts"], 2)

    def test_lesson_type_overrides_shape(self):
        self.assertEqual(plan(lesson_type="assessment")["topic_contract"]["lesson_shape"], "assessment_only")
        self.assertEqual(plan(lesson_type="project")["topic_contract"]["lesson_shape"], "project_or_practical")


class ContractQualityTests(unittest.TestCase):
    def test_short_standard_lesson_is_not_publishable(self):
        contract = plan(hours=2, learning_objectives="Складывать числа. Вычитать числа.")["topic_contract"]
        blocks = [
            {"component": "RetrievalCheck", "content": {"objective_ids": [], "evidence_stage": "diagnostic"}},
        ]

        report = quality_report(blocks, "Складывать числа. Вычитать числа.", topic_contract=contract)

        self.assertFalse(report["quality_report"]["publishable"])
        self.assertTrue(any(
            item["code"] == "lesson_too_short_for_topic_volume"
            for item in report["quality_report"]["errors"]
        ))

    def test_missing_optional_media_does_not_block_publication(self):
        contract = plan(
            subject_name="Биология",
            topic_name="Строение клетки",
            learning_objectives="Определять части клетки",
        )["topic_contract"]
        objective_id = quality_report([], "Определять части клетки")["objectives"][0]["id"]
        blocks = [
            {"component": "RetrievalCheck", "content": {
                "objective_ids": [objective_id],
                "evidence_stage": "diagnostic",
                "type": "multiple_choice",
                "options": ["Ядро", "Стол", "Книга", "Парта"],
                "correct_answer": "Ядро",
                "explanation": "Ядро — часть клетки.",
            }},
            {"component": "ShortExplanation", "content": {
                "objective_ids": [objective_id],
                "evidence_stage": "explanation",
                "title": "Клетка",
                "text": "Клетка имеет части.",
                "key_concepts": ["ядро"],
            }},
            {"component": "GuidedPractice", "content": {
                "objective_ids": [objective_id],
                "evidence_stage": "practice",
                "question": "Назовите часть клетки.",
                "hints": ["В центре клетки"],
                "input_type": "text",
                "correct_answer": "ядро",
                "explanation": "Ядро управляет клеткой.",
            }},
            {"component": "IndependentProblem", "content": {
                "objective_ids": [objective_id],
                "evidence_stage": "practice",
                "question": "Что относится к клетке?",
                "type": "multiple_choice",
                "options": ["Ядро", "Парта", "Линейка", "Мел"],
                "correct_answer": "Ядро",
                "explanation": "Ядро — органоид.",
                "difficulty": "basic",
            }},
            {"component": "MasteryCheck", "content": {
                "evidence_stage": "assessment",
                "questions": [{
                    "objective_ids": [objective_id],
                    "question": "Какая структура есть в клетке?",
                    "type": "multiple_choice",
                    "options": ["Ядро", "Парта", "Доска", "Ручка"],
                    "correct_answer": "Ядро",
                    "explanation": "Ядро — структура клетки.",
                    "dimension": objective_id,
                }],
            }},
            {"component": "Reflection", "content": {
                "prompt": "Что понял?",
                "scale_question": "Насколько уверенно?",
                "scale_labels": ["1", "2", "3", "4"],
            }},
        ]

        report = quality_report(blocks, "Определять части клетки", topic_contract=contract)

        self.assertTrue(report["quality_report"]["publishable"])


if __name__ == "__main__":
    unittest.main()
