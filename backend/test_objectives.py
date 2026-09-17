import unittest

from objectives import calculate_objective_mastery, decompose_objectives, quality_report


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

    def test_legacy_lesson_is_not_publishable(self):
        report = quality_report(
            [{"component": "ShortExplanation", "content": {"title": "Теория"}}],
            "Складывать числа",
        )
        self.assertTrue(report["quality_report"]["legacy"])
        self.assertFalse(report["quality_report"]["publishable"])

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


if __name__ == "__main__":
    unittest.main()