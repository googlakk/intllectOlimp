"""Shared teaching-purpose classification; reflection takes priority over assessment."""
import re
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


# В некоторых КТП в ячейку темы записаны и тема, и все подпункты с практическими
# работами — сотни символов. Такое название не влезает в базу (500 символов),
# а слова из подпунктов («исследовательская работа») путают тип занятия.
TOPIC_TITLE_LIMIT = 200


def split_topic_title(name: str) -> tuple[str, str]:
    """Длинную ячейку темы делит на название (первое предложение) и подробности."""
    text = " ".join(name.split())
    if len(text) <= TOPIC_TITLE_LIMIT:
        return name, ""
    end = re.search(r"[.;](?:\s|$)", text)
    title = text[:end.start()] if end and end.start() >= 3 else text
    if len(title) > TOPIC_TITLE_LIMIT:
        cut = text.rfind(" ", 0, TOPIC_TITLE_LIMIT)
        title = text[:cut if cut > 0 else TOPIC_TITLE_LIMIT]
    details = text[len(title):].strip(" .;:,\u2014\u2013-")
    return title.strip(" .;:,\u2014\u2013-"), details


def join_topic_details(details: str, resources: str) -> str:
    """Подробности темы идут в ресурсы: генератор урока видит их как контекст."""
    return "\n\n".join(part for part in (details, resources) if part)


def ambiguous_lesson_name(name: str) -> bool:
    text = name.casefold()
    return any(word in text for word in ("итог", "резерв", "обзор", "анализ")) and infer_lesson_type(name) == "study"
