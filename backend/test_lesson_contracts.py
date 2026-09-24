import unittest

from lesson_contracts import (
    adapt_legacy_blocks,
    flatten_lesson_document,
    normalize_lesson_document,
    synchronize_teaching_beats,
    validate_lesson_document,
)


class LessonContractTests(unittest.TestCase):
    def setUp(self):
        self.blocks = [
            {"component": "RetrievalCheck", "content": {
                "question": "Что помнишь?", "objective_ids": ["o1"], "evidence_stage": "diagnostic",
            }},
            {"component": "ShortExplanation", "content": {
                "title": "Идея", "text": "Короткое объяснение", "objective_ids": ["o1"], "evidence_stage": "explanation",
            }},
            {"component": "GuidedPractice", "content": {
                "question": "Попробуй", "objective_ids": ["o1"], "evidence_stage": "practice",
            }},
            {"component": "MasteryCheck", "content": {
                "questions": [], "objective_ids": ["o1"], "evidence_stage": "assessment",
            }},
            {"component": "Reflection", "content": {"prompt": "Что получилось?"}},
        ]
        self.metadata = {
            "topic_name": "Тема",
            "content_language": "ru",
            "objectives": [{"id": "o1", "text": "Понять идею"}],
            "topic_contract": {"volume": "standard", "hours": 1},
        }

    def test_adapter_builds_semantic_episodes_and_avatar_cues(self):
        document = adapt_legacy_blocks(self.blocks, self.metadata)
        self.assertEqual(document["schema_version"], 2)
        self.assertEqual([episode["phase"] for episode in document["episodes"]], [
            "activate", "explain", "practice", "assess", "reflect",
        ])
        explanation = document["episodes"][1]["scenes"][0]
        self.assertIn("Разберём смысл простыми словами", explanation["avatar_cues"][0]["script"])
        self.assertNotEqual(explanation["avatar_cues"][0]["script"], "Короткое объяснение")
        self.assertEqual(validate_lesson_document(document), [])

    def test_flatten_round_trips_original_blocks(self):
        document = adapt_legacy_blocks(self.blocks, self.metadata)
        self.assertEqual(flatten_lesson_document(document), self.blocks)

    def test_empty_v2_document_falls_back_to_legacy_adapter(self):
        document = normalize_lesson_document(
            {"schema_version": 2, "episodes": [], "legacy_blocks": self.blocks},
            self.blocks,
            self.metadata,
        )
        self.assertTrue(document["episodes"])

    def test_validator_rejects_duplicate_episode_ids(self):
        document = adapt_legacy_blocks(self.blocks, self.metadata)
        document["episodes"][1]["id"] = document["episodes"][0]["id"]
        self.assertTrue(any("повторяющийся" in error for error in validate_lesson_document(document)))

    def test_presentation_creates_one_synchronised_beat_and_cue_per_slide(self):
        blocks = [{"component": "Presentation", "content": {
            "title": "Делимость",
            "objective_ids": ["o1"],
            "slides": [
                {"heading": "На 2", "body": "Смотрим на последнюю цифру", "learning_point": "Чётная последняя цифра", "avatar_script": "Последняя цифра экономит нам вычисления."},
                {"id": "check", "heading": "Проверка", "body": "Делится ли 204?", "avatar_script": "Сначала проверь признак, затем ответ."},
            ],
        }}]
        document = adapt_legacy_blocks(blocks, self.metadata)
        scene = document["episodes"][0]["scenes"][0]

        self.assertEqual([beat["id"] for beat in scene["teaching_beats"]], ["slide-1", "check"])
        self.assertEqual([cue["beat_id"] for cue in scene["avatar_cues"]], ["slide-1", "check"])
        self.assertEqual(scene["avatar_cues"][0]["script"], "Последняя цифра экономит нам вычисления.")
        self.assertEqual(validate_lesson_document(document), [])

    def test_validator_rejects_broken_beat_to_cue_reference(self):
        document = adapt_legacy_blocks(self.blocks, self.metadata)
        scene = document["episodes"][1]["scenes"][0]
        scene["teaching_beats"][0]["avatar_cue_ids"] = ["missing-cue"]
        self.assertTrue(any("неизвестную реплику" in error for error in validate_lesson_document(document)))

    def test_existing_v2_presentation_is_upgraded_without_regeneration(self):
        legacy = adapt_legacy_blocks([{"component": "Presentation", "content": {
            "title": "Тема", "slides": [{"heading": "Шаг", "body": "Объяснение"}],
        }}], self.metadata)
        legacy["episodes"][0]["scenes"][0].pop("teaching_beats")
        legacy["episodes"][0]["scenes"][0]["avatar_cues"] = [{
            "id": "old", "script": "несколько слайдов сразу", "trigger": "scene_start", "fallback_text": "old",
        }]
        upgraded = synchronize_teaching_beats(legacy)
        scene = upgraded["episodes"][0]["scenes"][0]
        self.assertEqual(scene["teaching_beats"][0]["id"], "slide-1")
        self.assertEqual(scene["avatar_cues"][0]["beat_id"], "slide-1")

    def test_future_duplicate_avatar_script_is_replaced_by_coaching(self):
        blocks = [{"component": "GuidedPractice", "content": {
            "question": "Найдите квадратный корень из шестидесяти четырёх.",
            "avatar_script": "Найдите квадратный корень из шестидесяти четырёх.",
            "objective_ids": ["o1"], "evidence_stage": "practice",
        }}]
        document = adapt_legacy_blocks(blocks, self.metadata)
        script = document["episodes"][0]["scenes"][0]["avatar_cues"][0]["script"]
        self.assertNotIn("шестидесяти четырёх", script)
        self.assertIn("какое правило", script)


if __name__ == "__main__":
    unittest.main()
