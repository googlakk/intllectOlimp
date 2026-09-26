"""Prepare lesson narration for human-sounding text-to-speech."""

from __future__ import annotations

import re
from typing import Any

MAX_NARRATION_CHARS = 4800


def _word_set(value: Any) -> set[str]:
    return {
        word for word in re.findall(r"[\wа-яё]+", spoken_text(value).casefold())
        if len(word) > 2
    }


def is_screen_duplicate(script: Any, visible_values: list[Any], *, threshold: float = 0.72) -> bool:
    """Detect narration that mostly reads visible copy verbatim."""
    spoken = spoken_text(script)
    if len(spoken) < 24:
        return False
    visible = spoken_text(" ".join(value for value in visible_values if isinstance(value, str)))
    if not visible:
        return False
    normalized_script = spoken.casefold()
    normalized_visible = visible.casefold()
    if normalized_script in normalized_visible or normalized_visible in normalized_script:
        return True
    script_words = _word_set(spoken)
    visible_words = _word_set(visible)
    return bool(script_words) and len(script_words & visible_words) / len(script_words) >= threshold


def _verbalize_math(value: str) -> str:
    text = re.sub(r"\\(?:dfrac|tfrac)", r"\\frac", value)
    text = re.sub(r"\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}", r"дробь \1, делённая на \2", text)
    text = re.sub(r"\\sqrt\s*\[3\]\s*\{([^{}]+)\}", r"кубический корень из \1", text)
    text = re.sub(r"\\sqrt\s*\{([^{}]+)\}", r"квадратный корень из \1", text)
    text = re.sub(r"sqrt\s*\(([^()]+)\)", r"квадратный корень из \1", text, flags=re.IGNORECASE)
    text = re.sub(r"√\s*\(?\s*([^),.;]+)\s*\)?", r"квадратный корень из \1", text)
    text = re.sub(r"\^\s*\{?2\}?", " в квадрате", text)
    text = re.sub(r"\^\s*\{?3\}?", " в кубе", text)
    text = re.sub(r"\^\s*\{?([^{}\s]+)\}?", r" в степени \1", text)
    for pattern, replacement in {
        r"\\(?:times|cdot)|×|·": " умножить на ",
        r"\\div|÷": " разделить на ",
        r"\\pm|±": " плюс-минус ",
        r"\\geq?|≥": " больше или равно ",
        r"\\leq?|≤": " меньше или равно ",
        r"\\neq|≠": " не равно ",
        r"=": " равно ",
        r"\+": " плюс ",
    }.items():
        text = re.sub(pattern, replacement, text)
    text = re.sub(r"(^|\s)-(?=\s|\d)", r"\1 минус ", text)
    text = re.sub(r"[{}()\[\]]", " ", text)
    text = re.sub(r"\\(?:left|right|mathrm|text|operatorname)", " ", text)
    return re.sub(r"\\[A-Za-z]+", " ", text)


def spoken_text(value: Any, *, limit: int = MAX_NARRATION_CHARS) -> str:
    """Strip visual markup and verbalize common school mathematics for TTS."""
    if not isinstance(value, str):
        return ""
    text = _verbalize_math(value)
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\$+|\*\*|__|~~", " ", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", text, flags=re.MULTILINE)
    text = text.replace("|", ". ")
    text = re.sub(r"[<>*_#]", " ", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()[:limit].rstrip()


def fallback_avatar_script(component: str, content: dict[str, Any]) -> str:
    """Build a concise coaching cue when an older lesson has no authored narration."""
    if component == "Presentation":
        point = spoken_text(content.get("learning_point"), limit=700)
        heading = spoken_text(content.get("heading"), limit=180)
        idea = point or heading
        if idea:
            return spoken_text(f"Скажу проще. {idea}. Не запоминай это механически: проверь идею на примере со слайда и подумай, почему она работает.")
        return "Посмотри на пример и сначала найди связь между данными и выводом. Затем объясни эту связь своими словами."
    if component == "ShortExplanation":
        concepts = content.get("key_concepts") if isinstance(content.get("key_concepts"), list) else []
        idea = next((spoken_text(item, limit=650) for item in concepts if spoken_text(item)), "")
        if not idea:
            idea = spoken_text(content.get("callout") or content.get("text"), limit=650)
        return spoken_text(f"Разберём смысл простыми словами. {idea}. Свяжи эту мысль с конкретным примером и проверь, можешь ли объяснить её без подсказки.")
    if component == "MasteryCheck":
        return "Теперь проверь себя самостоятельно. Не спеши: сначала выбери способ решения, затем проверь ответ."
    if component in {"RetrievalCheck", "GuidedPractice", "IndependentProblem", "PredictionLab"}:
        return "Сначала определи, какое правило здесь подходит. Затем выполни первый шаг и проверь, согласуется ли ответ с условием."
    coaching = {
        "KeyConcept": "Не пытайся запомнить определение дословно. Найди главный признак понятия и сравни пример с контрпримером.",
        "WorkedExample": "Следи не только за вычислениями, но и за причиной каждого шага. После разбора попробуй восстановить решение без подсказок.",
        "GeneratedMedia": "Используй визуализацию как доказательство: найди на ней деталь, которая объясняет основную связь.",
        "SortAndClassify": "Для каждого элемента сначала назови признак, а уже потом выбирай группу. Так классификация не превратится в угадывание.",
        "ProcessBuilder": "Ищи причинную связь между соседними шагами: что должно произойти раньше и что становится возможным после этого.",
        "HotspotInvestigation": "Сначала осмотри схему целиком, затем связывай каждую активную область с её функцией.",
        "ArgumentMap": "Проверяй каждую связь вопросом: действительно ли это доказательство поддерживает тезис и объяснено ли почему.",
        "MisconceptionDebugger": "Ищи первый шаг, после которого вывод перестаёт следовать из предыдущего. Исправляй причину, а не только итоговый ответ.",
        "PhysicsSandbox": "Меняй только один параметр за раз. Тогда будет видно, какая именно причина изменила результат.",
        "BranchingScenario": "Перед выбором спрогнозируй последствие каждого решения и сопоставь его с целью ситуации.",
        "DataInvestigation": "Сначала опиши закономерность в данных словами, затем проверь, подтверждает ли её каждая важная точка графика.",
        "ChronologyLine": "Расставь события по времени: сначала вспомни, что было раньше, а что позже, и только потом уточняй годы.",
        "CauseEffectMap": "Отличай причину от повода: причина готовит событие долго, повод лишь запускает его. Потом подумай, что из события вышло.",
        "StepSolver": "Пиши решение строка за строкой: одно преобразование на строку, и сразу видно, где ошибка.",
        "CodeBlocksLab": "Собирай алгоритм по шагам и после каждого блока мысленно проверяй, каким станет состояние программы.",
        "Reflection": "Не оценивай себя по ощущению. Вспомни конкретное действие, которое уже можешь выполнить без подсказки.",
    }
    return coaching.get(component, "Сосредоточься на связи между условием, действием и результатом. Попробуй объяснить эту связь своими словами.")
