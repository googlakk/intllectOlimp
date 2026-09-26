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
        # Фирменные блоки — единственный вариант в своём шаге: из списка модель берёт привычный блок, а не новый.
        "chronology": ["ChronologyLine"],
        "signature_practice": ["CauseEffectMap"],
        "practice": ["SortAndClassify", "TextEvidencePicker"],
        # Лёгкий блок: тяжёлый бюджет урока уже заняли «Лента событий» и «Причины и следствия».
        "apply": ["ArgumentBuilder"],
    },
    # Урок с одной целью вмещает один тяжёлый интерактив — он и становится заданием на применение:
    # цель про причины/итоги → «Причины и следствия», иначе → «Лента событий».
    "single_objective_apply": (
        (re.compile(r"причин|последств|следстви|итог|значени|почему|привел|привело|привели|влия|роль|себеп|натыйжа", re.IGNORECASE), ["CauseEffectMap"]),
        (None, ["ChronologyLine"]),
    ),
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
            # Блок причин и следствий засчитывается сам по себе, без поиска слов.
            "satisfied_by": {"CauseEffectMap"},
            "text": re.compile(r"причин|последств|следстви|из-за|поэтому|привел|привело|привели|себеп|натыйжа", re.IGNORECASE),
            "message": "В уроке истории нет задания на причины и последствия",
        },
    ),
}

# Алгебра и школьная математика — разобранные примеры с постепенным убиранием шагов
# (Sweller 1985; Renkl & Atkinson 2003), перемешанная практика (Rohrer & Taylor 2007),
# разбор ошибок (Booth et al. 2013). Геометрия — отдельный профиль: чертёж и доказательство.
MATH: dict[str, Any] = {
    "id": "math",
    "label": "Математика",
    "keywords": (re.compile(r"(?<![а-яё])(математ|алгебр|арифмет)"),),
    "core": "понимать, почему преобразование верно, и уверенно выполнять его, различая типы задач",
    "route": (
        "задача-крючок (зачем это нужно) → правило с объяснением «почему» (сначала на числах, потом в общем виде) "
        "→ разобранный пример → ученик решает по шагам сам → разбор типичной ошибки → самостоятельная задача "
        "вперемешку с прошлым типом → проверка ответа подстановкой или оценкой"
    ),
    "show_path": (
        "что дано и что нужно получить → раскрой запись (степень — это умножение, дробь — деление на части) → какое правило подходит "
        "и почему → одно преобразование на шаг с его названием "
        "→ ограничения (знаменатель не равен нулю, под корнем неотрицательное число) → ответ → проверка подстановкой"
    ),
    "rules": (
        "Определения, формулы и обозначения — только как в учебнике.",
        "Примеры и задачи — такие же, как в учебнике, или их аналоги: тот же тип задачи, то же число действий и такие же "
        "«красивые» ответы; меняй только числа и буквы. Не придумывай задачи другого вида, чем в учебнике.",
        "Каждое правило сначала покажи на числах, потом запиши в общем виде.",
        "Один шаг решения — одно преобразование, у шага есть название («выносим множитель из-под корня»).",
        "Называй ограничения: знаменатель не равен нулю, под знаком корня — неотрицательное число.",
        "В разобранном примере покажи проверку ответа подстановкой или оценкой.",
        "Все формулы записывай в LaTeX между $…$.",
        "Хотя бы одно задание «найди ошибку» (MisconceptionDebugger) на типичное заблуждение.",
    ),
    "misconceptions": (
        "√(a+b) = √a + √b",
        "(a+b)² = a² + b²",
        "в дроби сокращают слагаемые, а не множители",
        "−x всегда отрицательно",
        "√(x²) = x при любом x",
        "при умножении или делении неравенства на отрицательное число знак не меняют",
        "делят уравнение на выражение с переменной и теряют корень",
    ),
    "plan": {
        "explain": ["Presentation", "ShortExplanation"],
        "model": ["WorkedExample"],
        # Фирменный шаг — один допустимый блок, иначе модель выбирает привычный.
        "first_practice": ["GuidedPractice"],
        "signature_practice": ["MisconceptionDebugger"],
        "practice": ["GuidedPractice", "SortAndClassify"],
        "apply": ["IndependentProblem"],
    },
    "actions": {
        "model": "Разобрать пример как в учебнике: одно преобразование на шаг, с названием и проверкой",
        "practice": "Решить аналог примера по шагам и найти типичную ошибку",
        "apply": "Самостоятельно решить задачу учебника другого вида вперемешку с прошлыми",
    },
    # Темы про функции — задание на график, иначе — самостоятельная задача.
    "single_objective_apply": (
        (re.compile(r"функци|график", re.IGNORECASE), ["InteractiveGraph"]),
        (None, ["IndependentProblem"]),
    ),
    "check_lesson_types": ("study", None, ""),
    # Тема привязана к параграфу — у каждого примера и задачи должна быть ссылка на учебник (source_ref).
    # «Найди ошибку» строится на заблуждении, а не на задаче книги — его не проверяем.
    "textbook_sourced": frozenset({"WorkedExample", "GuidedPractice", "IndependentProblem"}),
    "checks": (
        {
            "code": "math_without_worked_example",
            "components": {"WorkedExample"},
            "message": "В уроке математики нет разобранного примера по шагам",
        },
        {
            "code": "math_without_step_practice",
            "components": {"GuidedPractice"},
            "message": "В уроке математики нет задания, где ученик сам решает по шагам",
        },
        {
            "code": "math_without_error_analysis",
            "components": None,
            "satisfied_by": {"MisconceptionDebugger"},
            # В уроке с одной целью отдельного шага «найди ошибку» нет — бюджет урока не вмещает.
            "min_objectives": 2,
            "text": re.compile(r"найди(те)? ошибк|где ошибк|ошибся|ошиблась|неверно решил", re.IGNORECASE),
            "message": "В уроке математики нет задания на разбор типичной ошибки",
        },
        {
            "code": "math_without_check",
            # Проверку ответа показывают в разобранном примере; «проверь себя» в заданиях не в счёт.
            "components": {"WorkedExample"},
            "text": re.compile(r"подстав|проверка|проверим", re.IGNORECASE),
            "message": "В уроке математики нет проверки ответа подстановкой или оценкой",
        },
    ),
}

SUBJECT_PROFILES: tuple[dict[str, Any], ...] = (HISTORY, MATH)


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
    "ProcessBuilder", "ArgumentMap", "BranchingScenario", "MisconceptionDebugger", "MasteryCheck", "ChronologyLine", "CauseEffectMap",
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
    objective_count = len({objective for block in blocks if isinstance(block, dict) and isinstance(block.get("content"), dict)
                           for objective in block["content"].get("objective_ids") or []})
    for check in profile["checks"]:
        pattern = check.get("text")
        if objective_count < check.get("min_objectives", 0):
            continue
        components = check["components"] or _TASK_COMPONENTS
        found = any(block.get("component") in check.get("satisfied_by", ()) for block in blocks if isinstance(block, dict)) or any(
            block.get("component") in components
            and (pattern is None or any(pattern.search(text) for text in _texts(block.get("content"))))
            for block in blocks if isinstance(block, dict)
        )
        if not found:
            warnings.append({"code": check["code"], "message": check["message"]})
    return warnings


def _has_textbook_ref(block: dict[str, Any]) -> bool:
    ref = block.get("content", {}).get("source_ref") if isinstance(block.get("content"), dict) else None
    if not isinstance(ref, dict):
        return False
    # Разобранный пример может идти по тексту параграфа, без отдельного элемента.
    return ref.get("item_id") is not None or (block.get("component") == "WorkedExample" and ref.get("kind") == "section")


def textbook_source_warnings(blocks: list[dict[str, Any]], subject_name: str | None,
                             context: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Примеры и задачи не по учебнику — одним предупреждением. Проверяем, только если у темы есть
    параграф с разобранными задачами: иначе учителю нечем исправить."""
    components = (subject_profile(subject_name) or {}).get("textbook_sourced")
    has_items = any(section.get("items") for section in (context or {}).get("sections") or [])
    if not components or not has_items:
        return []
    missing = [index for index, block in enumerate(blocks)
               if isinstance(block, dict) and block.get("component") in components and not _has_textbook_ref(block)]
    if not missing:
        return []
    return [{"code": "task_without_textbook_source", "blocks": missing,
             "message": f"Без ссылки на учебник: {len(missing)} из примеров и задач — замените задачами книги или их аналогами"}]
