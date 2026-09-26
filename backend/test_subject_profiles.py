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
        self.assertIn("BranchingScenario", apply["allowed_components"])
        # Каждый предложенный блок допустим на своём этапе — иначе проверка урока выдаст ошибку.
        for step in steps:
            if step["evidence_stage"]:
                self.assertTrue(set(step["allowed_components"]) <= STAGE_COMPONENTS[step["evidence_stage"]], step)

    def test_single_objective_plan_fits_the_budget(self):
        plan = build_topic_contract(topic_name="Кокандское ханство", subject_name="История Кыргызстана",
                                    learning_objectives="Объяснять причины возвышения ханства", skills=None, resources=None,
                                    grade=8, hours=1, lesson_type="study")
        self.assertLessEqual(len(plan["component_plan"]), plan["topic_contract"]["block_budget"]["max"])

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
