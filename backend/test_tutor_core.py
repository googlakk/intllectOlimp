"""Ядро тьютора: защита от утечки ответа, правила, контекст, характер."""

import unittest

from tutor.context import (
    TurnContext, answer_spec, assessment_mode, authored_hints, lesson_context, nearest_theory_index, turn_prompt,
)
from tutor.guard import detect_answer_leak, detect_distress, scrub_pii
from tutor.policy import BASE_CHARACTER, TUTOR_TOOL, grade_profile, lesson_character, template
from tutor.rules import Decision, RuleState, decide

DENSITY = {"correct": "12", "numeric": True, "unit": "м", "tolerance": None, "options": []}


class AnswerLeakTests(unittest.TestCase):
    def leak(self, reply, spec=DENSITY, **kwargs):
        return detect_answer_leak(reply, spec, **kwargs)

    def test_numeric_answer_in_any_form_is_a_leak(self):
        for reply in ("Ответ 12", "Получится 12,0 м", "Это $\\frac{24}{2}$", "будет 1,2·10^1", "x = 12.0"):
            self.assertTrue(self.leak(reply), reply)

    def test_negative_answer_with_unicode_minus(self):
        self.assertTrue(self.leak("Скорость равна −3 м/с", {**DENSITY, "correct": "-3"}))

    def test_other_numbers_are_fine(self):
        self.assertFalse(self.leak("Раздели 24 на 2 и посмотри, что выйдет."))
        self.assertFalse(self.leak("Сначала найди путь: сколько метров за 2 секунды?"))

    def test_number_from_the_question_is_not_a_leak_unless_called_the_answer(self):
        question = "Верёвку длиной 12 м разрезали пополам. Какова была длина верёвки?"
        self.assertFalse(self.leak("Посмотри на 12 м в условии.", question_text=question))
        self.assertTrue(self.leak("Значит, ответ 12.", question_text=question))

    def test_students_own_number_and_shown_hints_are_fine(self):
        self.assertFalse(self.leak("Ты написал 12 — проверь единицы.", student_value="12 см"))
        self.assertFalse(self.leak("Как в подсказке: 12 делим…", shown_hints=["Подумай, почему 12"]))

    def test_reached_answer_can_be_repeated(self):
        self.assertFalse(self.leak("Да, 12 м — верно!", reached=True))

    def test_text_and_choice_answers(self):
        text = {"correct": "Баласагун", "numeric": False, "options": []}
        self.assertTrue(self.leak("Столица — Баласагун.", text))
        self.assertFalse(self.leak("Вспомни, где правили Караханиды.", text))
        choice = {"correct": "1917", "numeric": False, "options": ["1905", "1917", "1918", "1924"]}
        self.assertTrue(self.leak("Выбери вариант Б.", choice))
        self.assertFalse(self.leak("Посмотри на варианты внимательно.", choice))


class LeakFormatTests(unittest.TestCase):
    """Форматы, которые находил рецензент, и обратные случаи — нормальные подсказки."""

    CHOICE = {"correct": "12", "numeric": False, "options": ["10", "12", "14", "16"]}

    def test_short_choice_answer_and_letters(self):
        self.assertTrue(detect_answer_leak("Правильный ответ 12.", self.CHOICE))
        self.assertTrue(detect_answer_leak("Ответ: Б", self.CHOICE))
        self.assertTrue(detect_answer_leak("Правильный — второй вариант.", self.CHOICE))
        self.assertFalse(detect_answer_leak("Сравни все четыре числа с условием.", self.CHOICE))

    def test_digit_by_digit_and_plain_fraction(self):
        self.assertTrue(detect_answer_leak("Первая цифра 8, после запятой 9", DENSITY | {"correct": "8.9"}))
        self.assertTrue(detect_answer_leak("Это 89/10", DENSITY | {"correct": "8.9"}))

    def test_small_integer_answers_do_not_block_normal_help(self):
        spec = {"correct": "2", "numeric": True, "options": []}
        for reply in ("Шаг 2: раздели обе части на 3.", "Умножь на 2 обе части.", "Сколько частей? Их 2 или больше?"):
            self.assertFalse(detect_answer_leak(reply, spec, question_text="Реши 3x = 6"), reply)
        self.assertTrue(detect_answer_leak("Значит, x = 2.", spec, question_text="Реши 3x = 6"))

    def test_other_items_only_leak_when_named_as_the_answer(self):
        final = {"correct": "фотосинтез", "numeric": False, "options": ["дыхание", "фотосинтез", "испарение", "рост"]}
        self.assertFalse(detect_answer_leak("Вспомни, как идёт фотосинтез в листе.", final, current=False))
        self.assertFalse(detect_answer_leak("Верно, Б — это другое обозначение.", final, current=False))
        self.assertTrue(detect_answer_leak("Ответ: фотосинтез", final, current=False))
        number = {"correct": "25", "numeric": True, "options": []}
        self.assertFalse(detect_answer_leak("Возьми 25 грамм для опыта.", number, current=False))
        self.assertTrue(detect_answer_leak("Там ответ 25.", number, current=False))

    def test_steps_are_not_mistaken_for_digits_of_the_answer(self):
        self.assertFalse(detect_answer_leak("Сначала сделай шаг 1, потом шаг 2.", {"correct": "12", "numeric": True, "options": []}))
        self.assertFalse(detect_answer_leak("Найди 2 множителя: 5 и 5.", {"correct": "25", "numeric": True, "options": []}))

    def test_kyrgyz_local_phone_is_masked_completely(self):
        for phone in ("0555 12 34 56", "0 (555) 12-34-56"):
            self.assertNotIn("56", scrub_pii(f"номер {phone}"), phone)

    def test_numbers_from_the_solution_are_not_masked_as_phones(self):
        self.assertIn("1 234 567", scrub_pii("получилось 1 234 567"))
        self.assertNotIn("555", scrub_pii("звони 0555 123 456"))


class SafetyTests(unittest.TestCase):
    def test_pii_is_scrubbed(self):
        cleaned = scrub_pii("Мой номер +996 555 123 456, почта kid@mail.ru, я @kid_2010, сайт https://x.kg")
        for secret in ("555", "kid@mail.ru", "@kid_2010", "https://x.kg"):
            self.assertNotIn(secret, cleaned)
        self.assertLessEqual(len(scrub_pii("а" * 900)), 500)

    def test_distress_in_russian_and_kyrgyz(self):
        self.assertTrue(detect_distress("Я не хочу жить"))
        self.assertTrue(detect_distress("жашагым келбейт"))
        self.assertFalse(detect_distress("не хочу решать эту задачу"))


class RuleTests(unittest.TestCase):
    def test_correct_answer_is_a_free_template(self):
        self.assertEqual(decide("answer_submitted", RuleState(outcome="correct")), Decision("template", "correct"))

    def test_first_error_is_silent_second_offers_help(self):
        self.assertEqual(decide("answer_submitted", RuleState(outcome="incorrect", consecutive_wrong=1)).kind, "silent")
        second = decide("answer_submitted", RuleState(outcome="incorrect", consecutive_wrong=2))
        self.assertEqual((second.template_key, second.offer), ("offer_help", True))

    def test_young_students_get_help_after_the_first_error(self):
        state = RuleState(outcome="incorrect", consecutive_wrong=1, offer_after_errors=grade_profile(5).offer_after_errors)
        self.assertEqual(decide("answer_submitted", state).template_key, "offer_help")

    def test_wrong_unit_is_left_to_the_block(self):
        self.assertEqual(decide("answer_submitted", RuleState(outcome="wrong_unit", consecutive_wrong=5)).kind, "silent")

    def test_assessment_blocks_are_locked(self):
        self.assertEqual(decide("answer_submitted", RuleState(assessment=True, outcome="incorrect", consecutive_wrong=3)).kind, "silent")
        self.assertEqual(decide("idle", RuleState(assessment=True)).kind, "silent")
        for event in ("message", "hint_requested"):
            decision = decide(event, RuleState(assessment=True))
            self.assertEqual((decision.template_key, decision.action), ("assessment_locked", "open_theory"), event)

    def test_hint_ladder_uses_authored_hints_first(self):
        self.assertEqual(decide("hint_requested", RuleState(hint_level=0, authored_hints=2)), Decision("authored_hint", hint_index=0))
        self.assertEqual(decide("hint_requested", RuleState(hint_level=2, authored_hints=2)).kind, "llm")

    def test_idle_offer_only_once_per_step(self):
        self.assertEqual(decide("idle", RuleState()).template_key, "idle_offer")
        self.assertEqual(decide("idle", RuleState(idle_offered=True)).kind, "silent")

    def test_burst_limit_and_distress(self):
        self.assertEqual(decide("message", RuleState(llm_calls_last_minute=6)).template_key, "burst_limit")
        self.assertEqual(decide("message", RuleState(distress=True)), Decision("template", "distress", action="call_teacher"))


BLOCKS = [
    {"component": "Presentation", "content": {"title": "Плотность", "slides": [{"heading": "Что такое плотность", "body": "ρ = m/V"}]}},
    {"component": "WorkedExample", "content": {"problem": "Найди плотность", "steps": [{"description": "Делим массу на объём"}], "final_answer": "8.9"}},
    {"component": "GuidedPractice", "content": {"question": "Кубик 890 г, 100 см³. Плотность?", "hints": ["ρ = m/V", ""], "input_type": "numeric", "correct_answer": "8.9", "answer_unit": "г/см³", "explanation": "890/100"}},
    {"component": "MasteryCheck", "content": {"questions": [{"question": "Сила 10 Н на 2 м². Давление?", "type": "numeric", "correct_answer": "5", "answer_unit": "Па"}]}},
    {"component": "IndependentProblem", "content": {"question": "?", "type": "multiple_choice", "options": ["a", "b", "c", "d"], "correct_answer": "b", "evidence_stage": "assessment"}},
]


class ContextTests(unittest.TestCase):
    def test_theory_is_the_nearest_block_that_is_not_a_task(self):
        self.assertEqual(nearest_theory_index(BLOCKS, 2), 1)
        self.assertEqual(nearest_theory_index(BLOCKS, 3), 1)
        self.assertIsNone(nearest_theory_index(BLOCKS, 0))

    def test_assessment_mode(self):
        self.assertFalse(assessment_mode(BLOCKS[2]))
        self.assertTrue(assessment_mode(BLOCKS[3]))
        self.assertTrue(assessment_mode(BLOCKS[4]))

    def test_answer_spec_matches_lesson_rules(self):
        self.assertEqual(answer_spec(BLOCKS[2])["unit"], "г/см³")
        self.assertTrue(answer_spec(BLOCKS[2])["numeric"])
        self.assertEqual(answer_spec(BLOCKS[3], 0)["correct"], "5")
        self.assertFalse(answer_spec(BLOCKS[4])["numeric"])
        self.assertEqual(authored_hints(BLOCKS[2]), ["ρ = m/V"])

    def test_lesson_context_has_no_hidden_answers(self):
        context = lesson_context(BLOCKS, {"topic_name": "Плотность", "objectives": [{"text": "Вычислять плотность"}]})
        self.assertIn("Вычислять плотность", context)
        self.assertIn("[2] GuidedPractice", context)
        self.assertNotIn("8.9", context)

    def test_turn_prompt_carries_answer_for_tutor_and_student_attempt(self):
        prompt = turn_prompt(TurnContext(
            block=BLOCKS[2], block_index=2, question_index=None, event="message", student_value="89",
            check_outcome="incorrect", message="не понимаю", hints_shown=["ρ = m/V"],
            recent_turns=[{"role": "ученик", "text": "помоги"}, {"role": "тьютор", "text": "Что дано?"}],
        ))
        for piece in ("ТОЛЬКО для тебя", "\"8.9\" г/см³", "Ответ ученика: 89", "не понимаю", "тьютор: Что дано?"):
            self.assertIn(piece, prompt)


class CharacterTests(unittest.TestCase):
    def test_base_character_has_the_core_rules(self):
        for rule in ("НИКОГДА не называй итоговый ответ", "ровно ОДИН вопрос", "не пиши «неверно»", "safety_flag=\"distress\""):
            self.assertIn(rule, BASE_CHARACTER)
        self.assertEqual(TUTOR_TOOL["name"], "tutor_reply")

    def test_grade_bands(self):
        self.assertEqual(grade_profile(5).offer_after_errors, 1)
        self.assertEqual(grade_profile(8).band, "7–9 класс")
        self.assertIn("точные термины", grade_profile(11).language)
        self.assertIn("кыргызском", lesson_character(8, "физика", "формула → подстановка", "ky"))
        self.assertIn("английском", lesson_character(8, "physics", "formula → substitution", "en"))

    def test_templates_fall_back_to_russian(self):
        self.assertTrue(template("correct", "ky"))
        self.assertTrue(template("correct", "en").startswith("Correct"))
        self.assertEqual(template("correct", "de"), template("correct", "ru"))


if __name__ == "__main__":
    unittest.main()
