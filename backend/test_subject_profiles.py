import asyncio
import unittest
from unittest.mock import patch

from ai.planner import build_topic_contract
from ai.subject_profiles import subject_profile, subject_warnings
from objectives import STAGE_COMPONENTS

OBJECTIVES = "Объяснять причины завоевания Южного Кыргызстана. Работать с историческим источником."


def history_plan():
    return build_topic_contract(topic_name="Завоевание южного Кыргызстана Кокандским ханством", subject_name="История Кыргызстана",
                                learning_objectives=OBJECTIVES, skills=None, resources=None, grade=8, hours=1, lesson_type="study")


class ProfileTests(unittest.TestCase):
    def test_history_subjects_are_recognised(self):
        for name in ("История Кыргызстана", "Всемирная история", "Кыргызстан тарыхы"):
            self.assertEqual(subject_profile(name)["id"], "history")
        for name in ("Литература", "Физика", "Праистория", None):
            self.assertIsNone(subject_profile(name))

    def test_history_plan_uses_timeline_chronology_source_and_decision(self):
        plan = history_plan()
        self.assertEqual(plan["topic_contract"]["subject_profile"], "history")
        steps = plan["component_plan"]
        explain = next(step for step in steps if step["role"] == "explain")
        self.assertIn("Timeline", explain["allowed_components"])
        self.assertTrue(any("по времени" in step["cognitive_action"] for step in steps))
        first_practice = next(step for step in steps if step["role"] == "practice" and "источник" in step["cognitive_action"])
        self.assertEqual(first_practice["allowed_components"], ["TextEvidencePicker"])
        apply = next(step for step in steps if step["role"] == "apply")
        self.assertEqual(apply["allowed_components"], ["ArgumentBuilder"])
        # Каждый предложенный блок допустим на своём этапе — иначе проверка урока выдаст ошибку.
        for step in steps:
            if step["evidence_stage"]:
                self.assertTrue(set(step["allowed_components"]) <= STAGE_COMPONENTS[step["evidence_stage"]], step)

    def test_single_objective_plan_fits_the_budget(self):
        plan = build_topic_contract(topic_name="Кокандское ханство", subject_name="История Кыргызстана",
                                    learning_objectives="Объяснять причины возвышения ханства", skills=None, resources=None,
                                    grade=8, hours=1, lesson_type="study")
        self.assertLessEqual(len(plan["component_plan"]), plan["topic_contract"]["block_budget"]["max"])
        # Фирменный блок есть и при одной цели: цель про причины → «Причины и следствия».
        apply = next(step for step in plan["component_plan"] if step["role"] == "apply")
        self.assertEqual(apply["allowed_components"][0], "CauseEffectMap")
        dates = build_topic_contract(topic_name="Кокандское ханство", subject_name="История Кыргызстана",
                                     learning_objectives="Знать основные события правления Худояр-хана", skills=None,
                                     resources=None, grade=8, hours=1, lesson_type="study")
        apply = next(step for step in dates["component_plan"] if step["role"] == "apply")
        self.assertEqual(apply["allowed_components"][0], "ChronologyLine")

    def test_other_subjects_keep_family_plan(self):
        plan = build_topic_contract(topic_name="Лирика", subject_name="Литература", learning_objectives="Анализировать стихотворение",
                                    skills=None, resources=None, grade=8, hours=1, lesson_type="study")
        self.assertNotIn("subject_profile", plan["topic_contract"])

    def test_history_rules_reach_the_generator_prompt(self):
        from ai.generator import generate_lesson
        from llm import ToolResult
        from llm.base import STOP_TOOL

        prompts = []

        async def fake_call_tool(task, **kwargs):
            prompts.append(kwargs["user"])
            return ToolResult(data={"blocks": [{"component": "ShortExplanation", "content": {"objective_ids": ["obj-1"]}}]}, stop_reason=STOP_TOOL)

        with patch("llm.call_tool", fake_call_tool):
            asyncio.run(generate_lesson("Кокандское ханство", "История Кыргызстана", OBJECTIVES, None, None, grade=8))
        self.assertIn("Профиль предмета «История»", prompts[0])
        self.assertIn("Различай причину и повод", prompts[0])
        self.assertIn("когда и где", prompts[0])


class WarningsTests(unittest.TestCase):
    def test_missing_history_supports_are_flagged(self):
        blocks = [{"component": "Presentation", "content": {"slides": []}}]
        self.assertEqual([w["code"] for w in subject_warnings(blocks, "История Кыргызстана")],
                         ["history_without_chronology", "history_without_source", "history_without_causation"])

    def test_complete_history_lesson_passes(self):
        blocks = [
            {"component": "Timeline", "content": {"events": []}},
            {"component": "TextEvidencePicker", "content": {"source": "Летопись"}},
            {"component": "ArgumentMap", "content": {"title": "Причины и последствия похода"}},
        ]
        self.assertEqual(subject_warnings(blocks, "История Кыргызстана"), [])
        self.assertEqual(subject_warnings(blocks[:1], "Физика"), [])

    def test_tests_and_reviews_are_not_checked(self):
        blocks = [{"component": "MasteryCheck", "content": {"questions": []}}]
        self.assertEqual(subject_warnings(blocks, "История Кыргызстана", "assessment"), [])
        self.assertEqual(subject_warnings(blocks, "История Кыргызстана", "review"), [])

    def test_causation_found_by_causal_wording_in_any_task(self):
        blocks = [
            {"component": "Timeline", "content": {"events": []}},
            {"component": "TextEvidencePicker", "content": {"source": "Летопись"}},
            {"component": "ProcessBuilder", "content": {"steps": [{"text": "Набеги коканцев привели к восстанию"}]}},
        ]
        self.assertEqual(subject_warnings(blocks, "История Кыргызстана"), [])


if __name__ == "__main__":
    unittest.main()


class ChronologyContractTests(unittest.TestCase):
    def test_prompt_lists_every_generation_component(self):
        import re
        from ai.generator import SYSTEM_PROMPT
        from objectives import GENERATION_COMPONENTS
        header = int(re.search(r"Допустимы только следующие (\d+) компонент", SYSTEM_PROMPT).group(1))
        numbered = re.findall(r"^(\d+)\. ([A-Za-z]+):", SYSTEM_PROMPT, re.MULTILINE)
        self.assertEqual(header, len(GENERATION_COMPONENTS))
        self.assertEqual([int(number) for number, _ in numbered], list(range(1, len(numbered) + 1)))
        self.assertIn("ChronologyLine", {name for _, name in numbered})

    def test_bad_chronology_data_is_flagged(self):
        from objectives import component_content_warnings
        good = {"component": "ChronologyLine", "content": {"events": [{"id": str(i), "label": "x", "year": 1700 + i} for i in range(4)]}}
        bad = {"component": "ChronologyLine", "content": {"events": [{"id": "a", "label": "x", "year": "1709"}, {"id": "a", "label": "y", "year": 1762}]}}
        self.assertEqual(component_content_warnings([good]), [])
        self.assertEqual([w["code"] for w in component_content_warnings([good, bad])], ["chronology_line_invalid"])


class CauseEffectTests(unittest.TestCase):
    def test_cause_effect_map_satisfies_causation_and_is_validated(self):
        from objectives import component_content_warnings
        good = {"component": "CauseEffectMap", "content": {"event": {"label": "Восстание"}, "factors": [
            {"id": "a", "label": "Налоги", "role": "cause"}, {"id": "b", "label": "Поход", "role": "trigger"},
            {"id": "c", "label": "Война", "role": "consequence"}, {"id": "d", "label": "Чай", "role": "unrelated"}]}}
        blocks = [{"component": "Timeline", "content": {}}, {"component": "TextEvidencePicker", "content": {}}, good]
        self.assertEqual(subject_warnings(blocks, "История Кыргызстана"), [])
        self.assertEqual(component_content_warnings([good]), [])
        spelled = {"component": "CauseEffectMap", "content": {"event": "Восстание 1916 года", "factors": [
            {"id": "a", "label": "Налоги", "role": "Причина"}, {"id": "b", "label": "Поход", "role": " trigger "},
            {"id": "c", "label": "Война", "role": "последствие"}, {"id": "d", "label": "Чай", "role": "unrelated"}]}}
        self.assertEqual(component_content_warnings([spelled]), [])
        bad = {"component": "CauseEffectMap", "content": {"event": {"label": "X"}, "factors": [{"id": "a", "label": "Y", "role": "trigger"}]}}
        self.assertEqual([w["code"] for w in component_content_warnings([bad])], ["cause_effect_map_invalid"])


class ContentErrorsTests(unittest.TestCase):
    def test_broken_interactive_blocks_publishing(self):
        from objectives import quality_report
        bad = {"component": "ChronologyLine", "content": {"objective_ids": ["obj-1"], "evidence_stage": "practice", "events": [{"id": "a", "label": "x", "year": "1709"}]}}
        report = quality_report([bad], "Знать хронологию")["quality_report"]
        self.assertIn("chronology_line_invalid", [error["code"] for error in report["errors"]])
        self.assertFalse(report["publishable"])


def math_plan(objectives="Выносить множитель из-под знака корня. Вносить множитель под знак корня."):
    return build_topic_contract(topic_name="Преобразование выражений с квадратными корнями", subject_name="Алгебра",
                                learning_objectives=objectives, skills=None, resources=None, grade=8, hours=1, lesson_type="study")


class MathProfileTests(unittest.TestCase):
    def test_math_subjects_are_recognised_but_not_geometry(self):
        for name in ("Алгебра", "Математика", "Алгебра и начала анализа"):
            self.assertEqual(subject_profile(name)["id"], "math")
        self.assertIsNone(subject_profile("Геометрия"))

    def test_math_plan_has_worked_example_step_practice_and_error_analysis(self):
        plan = math_plan()
        self.assertEqual(plan["topic_contract"]["subject_profile"], "math")
        steps = plan["component_plan"]
        self.assertTrue(any(step["allowed_components"] == ["WorkedExample"] for step in steps))
        practices = [step["allowed_components"] for step in steps if step["role"] == "practice"]
        self.assertEqual(practices[:2], [["GuidedPractice"], ["MisconceptionDebugger"]])
        self.assertTrue(all("источник" not in step["cognitive_action"] for step in steps))
        for step in steps:
            if step["evidence_stage"]:
                self.assertTrue(set(step["allowed_components"]) <= STAGE_COMPONENTS[step["evidence_stage"]], step)
        self.assertLessEqual(len(steps), plan["topic_contract"]["block_budget"]["max"])

    def test_function_topic_applies_on_a_graph(self):
        plan = math_plan("Строить график функции y = √x")
        apply = next(step for step in plan["component_plan"] if step["role"] == "apply")
        self.assertEqual(apply["allowed_components"], ["InteractiveGraph"])

    def test_math_warnings(self):
        blocks = [{"component": "Presentation", "content": {"slides": [], "objective_ids": ["a", "b"]}}]
        self.assertEqual([w["code"] for w in subject_warnings(blocks, "Алгебра")],
                         ["math_without_worked_example", "math_without_step_practice",
                          "math_without_error_analysis", "math_without_check"])
        complete = [
            {"component": "WorkedExample", "content": {"objective_ids": ["a"], "steps": [{"description": "Проверка: подставим x = 4"}]}},
            {"component": "GuidedPractice", "content": {"question": "Вынесите множитель: $\\sqrt{12}$"}},
            {"component": "MisconceptionDebugger", "content": {"objective_ids": ["b"], "claim": "√(9+16) = 7"}},
        ]
        self.assertEqual(subject_warnings(complete, "Алгебра"), [])
        # Одна цель: без «найди ошибку» не ругаем — в таком уроке нет для него шага.
        single = [complete[0], complete[1]]
        self.assertEqual(subject_warnings(single, "Алгебра"), [])

    def test_tasks_must_come_from_the_textbook_when_linked(self):
        from ai.subject_profiles import textbook_source_warnings
        blocks = [
            {"component": "WorkedExample", "content": {"source_ref": {"kind": "section", "page": 12}}},
            {"component": "GuidedPractice", "content": {"question": "?"}},
            {"component": "IndependentProblem", "content": {"source_ref": {"kind": "analog", "item_id": 7}}},
            {"component": "MisconceptionDebugger", "content": {}},
        ]
        context = {"sections": [{"items": [{"id": 7}]}]}
        self.assertEqual([w["blocks"] for w in textbook_source_warnings(blocks, "Алгебра", context)], [[1]])
        # Задачи из параграфа не извлечены — учителю нечем исправить, молчим.
        self.assertEqual(textbook_source_warnings(blocks, "Алгебра", {"sections": [{"items": []}]}), [])
        self.assertEqual(textbook_source_warnings(blocks, "Алгебра", None), [])
        self.assertEqual(textbook_source_warnings(blocks, "История Кыргызстана", context), [])

    def test_math_rules_reach_the_generator_prompt(self):
        from ai.generator import generate_lesson
        from llm import ToolResult
        from llm.base import STOP_TOOL

        prompts = []

        async def fake_call_tool(task, **kwargs):
            prompts.append(kwargs["user"])
            return ToolResult(data={"blocks": [{"component": "ShortExplanation", "content": {"objective_ids": ["obj-1"]}}]}, stop_reason=STOP_TOOL)

        with patch("llm.call_tool", fake_call_tool):
            asyncio.run(generate_lesson("Квадратные корни", "Алгебра", "Вычислять квадратные корни", None, None, grade=8))
        self.assertIn("Профиль предмета «Математика»", prompts[0])
        self.assertIn("меняй только числа и буквы", prompts[0])
