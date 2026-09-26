"""Профили предметов: чему в первую очередь учит предмет и как строить его урок.

Семейство предмета (generator.SUBJECT_FAMILY_PROFILES) задаёт общий сценарий:
история, литература и ЧиО попадают в одно «гуманитарное». Профиль уточняет
его для конкретного предмета. Нет профиля — работает семейство, как раньше.

История — по исследованиям исторического мышления: хронология, причины и
следствия, работа с источником (sourcing, контекст, сопоставление) —
Seixas «Big Six»; Wineburg 2001; Reisman 2012 «Reading Like a Historian».
"""

from __future__ import annotations

import re
from typing import Any

HISTORY: dict[str, Any] = {
    "id": "history",
    "label": "История",
    # По началу слова: «История Кыргызстана», «Кыргыз тарыхы» — но не «Праистория».
    "keywords": (re.compile(r"(?<![а-яё])истори"), re.compile(r"(?<![а-яё])тарых")),
    "core": "хронология, причины и следствия, работа с историческим источником",
    "route": (
        "контекст на ленте времени (когда, где, что было до) → исторический источник → причины → ход событий "
        "→ последствия → значение события и разные точки зрения"
    ),
    "show_path": (
        "когда и где → кто действовал и чего добивался → причины (политические, экономические, социальные) "
        "→ что произошло → последствия → почему это важно; каждый вывод опирай на факт или источник"
    ),
    "rules": (
        "Каждое событие привязывай к времени: год или век и место. Даты, имена и названия — только из учебника или материала урока.",
        "Покажи событие на ленте времени рядом с тем, что было до и после (блок Timeline в объяснении).",
        "Причины называй по видам: политические, экономические, социальные, внешние; у события почти всегда больше одной причины.",
        "Различай причину и повод, последствия ближайшие и долгосрочные.",
        "Работа с источником: кто автор, когда и зачем создан источник, чему в нём можно доверять — и только потом вывод.",
        "Не оценивай прошлое мерками сегодняшнего дня: объясняй поступки людей условиями их времени.",
        "Хотя бы одно задание на порядок событий (ChronologyLine — ученик сам ставит события на ленту) и одно — на связь причин и следствий.",
    ),
    "misconceptions": (
        "история — это только даты и имена, а не причины и связи",
        "у события одна причина",
        "повод принимают за причину",
        "люди прошлого думали и поступали как мы сегодня",
        "путают века: XIX век — это 1800-е годы, а не 1900-е",
        "источник говорит правду, потому что он старый",
    ),
    # Шаги урока по ролям: какие блоки подходят истории (все — из существующих).
    # Лёгкие блоки — первыми (модель обычно берёт первый): тяжёлых интерактивов не больше бюджета урока.
    "plan": {
        "explain": ["Presentation", "Timeline"],
        "model": ["WorkedExample"],
        "source": ["TextEvidencePicker"],
        "chronology": ["ChronologyLine", "SortAndClassify"],
        "practice": ["SortAndClassify", "TextEvidencePicker", "ArgumentMap", "ProcessBuilder"],
        "apply": ["ArgumentBuilder", "BranchingScenario", "ArgumentMap"],
    },
    # Проверки — только для обычных учебных уроков: у контрольной и повторения свой набор блоков.
    "check_lesson_types": ("study", None, ""),
    # Обязательные опоры урока истории — проверяются после генерации.
    "checks": (
        {
            "code": "history_without_chronology",
            "components": {"Timeline", "ChronologyLine", "ProcessBuilder"},
            "message": "В уроке истории нет ленты времени или задания на порядок событий",
        },
        {
            "code": "history_without_source",
            "components": {"TextEvidencePicker", "ArgumentBuilder"},
            "message": "В уроке истории нет работы с историческим источником",
        },
        {
            # Причины и последствия — в любом задании с причинными словами.
            "code": "history_without_causation",
            "components": None,
            "text": re.compile(r"причин|последств|следстви|из-за|поэтому|привел|привело|привели|себеп|натыйжа", re.IGNORECASE),
            "message": "В уроке истории нет задания на причины и последствия",
        },
    ),
}

SUBJECT_PROFILES: tuple[dict[str, Any], ...] = (HISTORY,)


def subject_profile(subject_name: str | None) -> dict[str, Any] | None:
    """Профиль по названию предмета: «История Кыргызстана», «Всемирная история», «Кыргызстан тарыхы»."""
    name = (subject_name or "").casefold()
    for profile in SUBJECT_PROFILES:
        if any(keyword.search(name) for keyword in profile["keywords"]):
            return profile
    return None


def subject_prompt(profile: dict[str, Any]) -> str:
    """Раздел промпта генератора: главное в предмете, маршрут, правила, заблуждения."""
    rules = "\n".join(f"- {rule}" for rule in profile["rules"])
    misconceptions = "; ".join(profile["misconceptions"])
    return (
        f"Профиль предмета «{profile['label']}». Главное, чему учим: {profile['core']}.\n"
        f"Маршрут урока: {profile['route']}.\n"
        f"Правила предмета:\n{rules}\n"
        f"Типичные заблуждения учеников (предупреждай и разбирай их в заданиях «найди ошибку»): {misconceptions}."
    )


# Задания — всё, где ученик действует (не объяснение).
_TASK_COMPONENTS = frozenset({
    "GuidedPractice", "IndependentProblem", "RetrievalCheck", "TextEvidencePicker", "ArgumentBuilder", "SortAndClassify",
    "ProcessBuilder", "ArgumentMap", "BranchingScenario", "MisconceptionDebugger", "MasteryCheck", "ChronologyLine",
})


def _texts(value: Any) -> list[str]:
    """Только текстовые значения содержимого блока, без ключей и служебных полей."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _texts(item)]
    if isinstance(value, list):
        return [text for item in value for text in _texts(item)]
    return []


def subject_warnings(blocks: list[dict[str, Any]], subject_name: str | None, lesson_type: str | None = "study") -> list[dict[str, Any]]:
    """Предупреждения учителю: в учебном уроке нет обязательной для предмета опоры."""
    profile = subject_profile(subject_name)
    if not profile or not blocks or lesson_type not in profile.get("check_lesson_types", ("study",)):
        return []
    warnings = []
    for check in profile["checks"]:
        pattern = check.get("text")
        components = check["components"] or _TASK_COMPONENTS
        found = any(
            block.get("component") in components
            and (pattern is None or any(pattern.search(text) for text in _texts(block.get("content"))))
            for block in blocks if isinstance(block, dict)
        )
        if not found:
            warnings.append({"code": check["code"], "message": check["message"]})
    return warnings
