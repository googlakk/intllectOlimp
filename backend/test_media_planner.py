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
        plan = build_lesson_media_plan(blocks, {"subject_name": "Биология", "topic_name": "Фотосинтез", "lesson_shape": "extended"})
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


if __name__ == "__main__":
    unittest.main()
