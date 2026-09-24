"""Shared teaching-purpose classification; reflection takes priority over assessment."""
from typing import Literal

LessonType = Literal["study", "review", "assessment", "reflection", "project"]
CONSOLIDATION_TYPES = {"review", "assessment", "reflection"}


def infer_lesson_type(name: str) -> LessonType:
    text = name.casefold().replace("ё", "е")
    if any(word in text for word in ("работа над ошиб", "разбор ошиб", "анализ контроль", "разбор контроль", "рефлекси")):
        return "reflection"
    if any(word in text for word in ("контрольн", "проверочн", "зачет", "тест", "сочинени", "изложени", "диктант", "экзамен", "аттестац")):
        return "assessment"
    if any(word in text for word in ("повтор", "ключевые идеи", "пересмотр", "обобщени", "закреплен")):
        return "review"
    if any(word in text for word in ("проект", "исследован")):
        return "project"
    return "study"


def ambiguous_lesson_name(name: str) -> bool:
    text = name.casefold()
    return any(word in text for word in ("итог", "резерв", "обзор", "анализ")) and infer_lesson_type(name) == "study"
