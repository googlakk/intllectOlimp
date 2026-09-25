import unittest

from media_planner import LESSON_VISUAL_SYSTEM, build_block_media_plan, build_lesson_media_plan, subject_profile


class MediaPlannerTests(unittest.TestCase):
    def test_literature_uses_source_context_profile(self):
        plan = build_lesson_media_plan(
            [{"component": "Presentation", "content": {"title": "Образ героя", "slides": [
                {"id": "slide-1", "heading": "Выбор Гринёва", "body": "Герой сохраняет честь в момент нравственного выбора.", "learning_point": "Объяснить поступок героя"},
            ]}}],
            {"subject_name": "Русская литература", "topic_name": "Капитанская дочка", "lesson_shape": "standard"},
        )
        self.assertEqual(plan["subject_family"], "humanities")
        self.assertEqual(plan["recommendations"][0]["visual_intent"], "source_context")
        self.assertIn("Герой сохраняет честь", plan["recommendations"][0]["source_context"])
        self.assertIn("literary", plan["recommendations"][0]["visual_form"])

    def test_process_gets_one_video_and_respects_volume_limit(self):
        blocks = [{"component": "ShortExplanation", "content": {
            "title": f"Этап {index}", "text": "Процесс изменяется последовательно: сначала состояние A, затем состояние B.",
        }} for index in range(4)]
        plan = build_lesson_media_plan(blocks, {"subject_name": "Биология", "topic_name": "Фотосинтез", "topic_contract": {"volume": "micro"}})
        self.assertEqual(plan["limit"], 3)
        self.assertEqual(len(plan["recommendations"]), 3)
        self.assertEqual(sum(item["kind"] == "video" for item in plan["recommendations"]), 1)

    def test_existing_slide_media_is_not_recommended_again(self):
        plan = build_lesson_media_plan(
            [{"component": "Presentation", "content": {"slides": [
                {"heading": "Заполнено", "body": "Текст", "media": {"kind": "image", "url": "ready.png"}},
                {"heading": "Нужно", "body": "Точный фрагмент объяснения"},
            ]}}],
            {"subject_name": "Математика", "topic_name": "Дроби"},
        )
        self.assertEqual(len(plan["recommendations"]), 1)
        self.assertEqual(plan["recommendations"][0]["slide_index"], 1)

    def test_unknown_subject_has_general_profile(self):
        self.assertEqual(subject_profile("Музыка")["family"], "general")

    def test_block_plan_targets_requested_presentation_slide_and_kind(self):
        block = {"component": "Presentation", "content": {"title": "Корни", "slides": [
            {"id": "slide-1", "heading": "Квадрат", "body": "Площадь квадрата"},
            {"id": "slide-2", "heading": "Куб", "body": "Куб числа связан с объёмом и третьим измерением"},
        ]}}
        plan = build_block_media_plan(
            block=block, block_index=3, slide_index=1, preferred_kind="video",
            metadata={"subject_name": "Математика", "topic_name": "Степени"}, scene_id="scene-4",
        )
        self.assertEqual(len(plan["recommendations"]), 1)
        recommendation = plan["recommendations"][0]
        self.assertEqual(recommendation["block_index"], 3)
        self.assertEqual(recommendation["slide_index"], 1)
        self.assertEqual(recommendation["slide_id"], "slide-2")
        self.assertEqual(recommendation["kind"], "video")
        self.assertIn(LESSON_VISUAL_SYSTEM, recommendation["style"])


class LessonIllustrationTests(unittest.TestCase):
    META = {"subject_name": "Физика", "topic_name": "Плотность", "topic_contract": {"volume": "standard"}}

    def lesson(self):
        return [
            {"component": "RetrievalCheck", "content": {"question": "Что тяжелее?"}},
            {"component": "IndependentProblem", "content": {"question": "Кубик 27 г, объём 10 см³. Плотность?", "media_slot": {
                "id": "task", "must_show": ["медный кубик на весах"], "must_not_show": ["число на весах"]}}},
            {"component": "Presentation", "content": {"title": "Плотность", "slides": [
                {"id": "s1", "heading": "Загадка", "body": "Два кубика", "media_slot": {"id": "m1", "must_show": ["два кубика"]}},
                {"id": "s2", "heading": "Без картинки", "body": "Текст"},
            ]}},
            {"component": "KeyConcept", "content": {"term": "Плотность", "definition": "Масса единицы объёма", "media_slot": {"id": "kc"}}},
            {"component": "MasteryCheck", "content": {"questions": []}},
            {"component": "Reflection", "content": {"prompt": "Что понял?"}},
        ]

    def test_marked_slots_only_in_priority_order(self):
        plan = build_lesson_media_plan(self.lesson(), self.META, allow_video=False)
        order = [(item["component"], item["media_slot_id"]) for item in plan["recommendations"]]
        self.assertEqual(order, [("Presentation", "m1"), ("KeyConcept", "kc"), ("IndependentProblem", "task")])
        self.assertTrue(all(item["kind"] == "image" for item in plan["recommendations"]))

    def test_task_scene_never_shows_the_answer(self):
        task = build_lesson_media_plan(self.lesson(), self.META)["recommendations"][2]
        self.assertEqual(task["placement"], "block_visual")
        self.assertEqual(task["must_include"], ["медный кубик на весах"])
        self.assertIn("число на весах", task["avoid"])
        self.assertTrue(any("answer" in item for item in task["avoid"]))

    def test_checks_and_reflection_get_no_images(self):
        legacy = [{"component": name, "content": {"question": "?"}} for name in ("RetrievalCheck", "MasteryCheck", "Reflection", "SortAndClassify")]
        self.assertEqual(build_lesson_media_plan(legacy, self.META)["recommendations"], [])

    def test_limit_depends_on_volume(self):
        blocks = [{"component": "ShortExplanation", "content": {"title": f"Понятие {i}", "text": "Текст"}} for i in range(12)]
        for volume, expected in (("micro", 3), ("standard", 6), ("extended", 8)):
            plan = build_lesson_media_plan(blocks, {**self.META, "topic_contract": {"volume": volume}}, allow_video=False)
            self.assertEqual(len(plan["recommendations"]), expected)


if __name__ == "__main__":
    unittest.main()
