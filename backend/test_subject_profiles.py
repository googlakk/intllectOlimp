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
        self.assertEqual(practices[:2], [["StepSolver"], ["MisconceptionDebugger"]])
        self.assertTrue(all("источник" not in step["cognitive_action"] for step in steps))
        for step in steps:
            if step["evidence_stage"]:
                self.assertTrue(set(step["allowed_components"]) <= STAGE_COMPONENTS[step["evidence_stage"]], step)
        self.assertLessEqual(len(steps), plan["topic_contract"]["block_budget"]["max"])

    def test_function_topic_applies_on_a_graph(self):
        plan = math_plan("Строить график функции y = √x")
        apply = next(step for step in plan["component_plan"] if step["role"] == "apply")
        self.assertEqual(apply["allowed_components"], ["FunctionExplorer"])

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


class StepSolverTests(unittest.TestCase):
    def test_model_solution_is_verified(self):
        from objectives import component_content_warnings

        def block(**content):
            return {"component": "StepSolver", "content": content}

        good = [
            block(kind="equation", start="3(x - 2) = x + 4", final_answer=["x = 5"],
                  steps=[{"hint": "Раскройте скобки", "expected": "3x - 6 = x + 4"}, {"hint": "", "expected": "2x = 10"}],
                  mistakes=[{"wrong": "3x - 6 = x - 4", "message": "Знак"}]),
            block(kind="equation", start="x^2 = 3x", final_answer="x = 0 или x = 3",
                  steps=[{"expected": "x(x - 3) = 0"}], mistakes=[{"wrong": "x = 3", "message": "Потерян корень"}]),
            block(kind="expression", start="√12 + √27", final_answer=["5√3"], steps=[{"expected": "2√3 + 3√3"}],
                  mistakes=[{"wrong": "√39", "message": "Корень суммы"}]),
        ]
        self.assertEqual(component_content_warnings(good), [])
        bad = [
            block(kind="equation", start="2x = 4", final_answer=["x = 3"]),
            block(kind="expression", start="√12", final_answer=["2√3"], steps=[{"expected": "3√2"}]),
            block(kind="expression", start="√12", final_answer=["2√3"], mistakes=[{"wrong": "2√3", "message": "?"}]),
            block(start="", final_answer=["1"]),
        ]
        self.assertEqual([w["block"] for w in component_content_warnings(bad)], [0, 1, 2, 3])

    def test_single_objective_math_plan_practises_by_steps(self):
        steps = math_plan("Выносить множитель из-под знака корня")["component_plan"]
        self.assertEqual(next(step for step in steps if step["role"] == "practice")["allowed_components"], ["StepSolver"])
        self.assertEqual(next(step for step in steps if step["role"] == "apply")["allowed_components"], ["IndependentProblem"])

    def test_tutor_judges_a_solution_line_not_the_final_answer(self):
        from services.math_expression import solver_line_outcome
        content = {"kind": "equation", "start": "3(x - 2) = x + 4", "final_answer": ["x = 5"]}
        self.assertEqual(solver_line_outcome("3x - 6 = x + 4", content), "correct")
        self.assertEqual(solver_line_outcome("3x - 2 = x + 4", content), "incorrect")

    def test_rational_radical_identity_and_complete_roots(self):
        from objectives import component_content_warnings

        def block(**content):
            return {"component": "StepSolver", "content": {"kind": "equation", **content}}

        good = [
            block(start="(x+1)/(x-2) = 2", final_answer=["x = 5"], steps=[{"expected": "x + 1 = 2(x - 2)"}]),
            block(start="√x = 2", final_answer=["x = 4"], steps=[{"expected": "x = 4"}]),
            block(start="2(x + 1) = 2x + 2", final_answer=["любое число"], steps=[{"expected": "0 = 0"}]),
            block(start="x^2 - 5x + 6 = 0", final_answer=["x = 2 или x = 3"], steps=[{"expected": "(x - 2)(x - 3) = 0"}]),
        ]
        self.assertEqual(component_content_warnings(good), [])
        missing_root = [block(start="x^2 = 9", final_answer=["x = 3"])]
        self.assertEqual([w["code"] for w in component_content_warnings(missing_root)], ["step_solver_invalid"])

    def test_step_solver_rejects_tasks_it_cannot_check(self):
        from objectives import component_content_warnings

        def block(**content):
            return {"component": "StepSolver", "content": content}

        unsupported = [
            block(kind="expression", start="y/(y^2 - 5y)", final_answer=["1/(y - 5)"],
                  title="Найди допустимые значения и нули дроби",
                  instruction="Укажите, при каких допустимых значениях y дробь равна нулю."),
            block(kind="expression", start="(x + 2)/(x - 3)", final_answer=["x ≠ 3"], instruction="Запишите ответ."),
        ]
        self.assertEqual([w["block"] for w in component_content_warnings(unsupported)], [0, 1])
        supported = [
            block(kind="expression", start="y/(y^2 - 5y)", final_answer=["1/(y - 5)"], title="Сократите дробь"),
            block(kind="equation", start="x^2 - 4 = 0", final_answer=["x = 2 или x = -2"], title="Найдите нули функции"),
        ]
        self.assertEqual(component_content_warnings(supported), [])

    def test_shared_step_cases_match_the_browser(self):
        import json
        from pathlib import Path
        from services.math_expression import check_solver_step
        cases = json.loads((Path(__file__).parent / "fixtures" / "step_solver_cases.json").read_text(encoding="utf-8"))["cases"]
        for case in cases:
            status, done = check_solver_step(case["line"], kind=case["kind"], start=case["start"],
                                             final_answer=case["final_answer"], answer_mode=case.get("answer_mode", "form"))
            self.assertEqual((status, done), (case["status"], case["done"]), case["note"])


class FunctionExplorerTests(unittest.TestCase):
    def test_graph_task_is_validated(self):
        from objectives import component_content_warnings

        def block(**content):
            base = {"formula": "k*x + b", "params": [{"name": "k", "min": -3, "max": 3, "step": 0.5}, {"name": "b", "min": -4, "max": 4, "step": 1}]}
            return {"component": "FunctionExplorer", "content": {**base, **content}}

        good = block(target={"params": {"k": 2, "b": -1}}, points=[{"x": 2, "y": 3}],
                     prediction={"question": "?", "options": ["вверх", "вниз"], "correct_answer": "вверх"})
        self.assertEqual(component_content_warnings([good]), [])
        bad = [
            block(),  # нет задания
            block(target={"params": {"k": 2, "b": -1}}, points=[{"x": 2, "y": 4}]),  # точка мимо
            block(target={"params": {"k": 2.3, "b": -1}}),  # не на шаге
            block(formula="k*x + c", target={"params": {"k": 1, "b": 0}}),  # неизвестная буква
            block(params=[{"name": "k", "min": -3, "max": 3, "step": 0.5, "default": 2}, {"name": "b", "min": -4, "max": 4, "step": 1, "default": -1}],
                  target={"params": {"k": 2, "b": -1}}),  # решено без действий
            block(target={"params": {"k": 2, "b": -1}}, evidence_stage="assessment"),  # итог без прогноза
        ]
        self.assertEqual([w["block"] for w in component_content_warnings(bad)], [0, 1, 2, 3, 4, 5])

    def test_function_topic_with_two_objectives_applies_on_a_graph(self):
        plan = math_plan("Строить график функции y = kx + b. Определять знак углового коэффициента по графику.")
        steps = plan["component_plan"]
        self.assertEqual(next(step for step in steps if step["role"] == "apply")["allowed_components"], ["FunctionExplorer"])
        self.assertLessEqual(len(steps), plan["topic_contract"]["block_budget"]["max"])
