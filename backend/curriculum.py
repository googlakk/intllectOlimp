"""KTP structure rules: quarters, merged multi-row topics, lesson parts, Drive video links."""

import re

QUARTER_WEEKS = (8, 7, 8, 11)
MAX_LESSON_PARTS = 4

# Rows like these repeat in every chapter but are never "the same topic".
_GENERIC_TITLE = re.compile(
    r"^(итоговая\s+)?(контрольная|самостоятельная|проверочная)|^закреплени|^повторени|^обобщени|^ключевые идеи|^входная",
    re.IGNORECASE,
)


def quarter_for(position_hours: float, total_hours: float) -> int:
    """Quarter of a topic that starts after `position_hours` of `total_hours` (school weeks 8/7/8/11)."""
    if total_hours <= 0:
        return 1
    share, bound = position_hours / total_hours, 0.0
    for number, weeks in enumerate(QUARTER_WEEKS, start=1):
        bound += weeks / sum(QUARTER_WEEKS)
        if share < bound:
            return number
    return 4


def merge_key(name: str) -> str | None:
    """Key under which KTP rows of one section are merged into one learning topic; None = never merge."""
    normalized = re.sub(r"\s+", " ", name.casefold().replace("ё", "е")).strip(" .")
    if not normalized or _GENERIC_TITLE.search(normalized):
        return None
    return normalized


def lesson_parts(total_hours: int) -> list[str]:
    """Short 10-minute parts for a topic that spans `total_hours` class hours."""
    if total_hours <= 1:
        return ["understand_apply"]
    if total_hours == 2:
        return ["understand", "apply_consolidate"]
    if total_hours == 3:
        return ["understand", "apply", "consolidate"]
    return ["understand", "apply", "extend", "consolidate"]


PART_GOALS = {
    "understand_apply": "понять суть, разобрать пример, решить типовые задачи и пройти проверку освоения",
    "understand": "понять суть: ключевое понятие и разобранный пример, 1–2 простые задачи",
    "apply": "применить: типовые задачи с подсказкой при ошибке",
    "apply_consolidate": "применить и закрепить: типовые задачи, смешанные задачи и проверка освоения",
    "extend": "усложнить: нестандартные задачи и разбор типичных ошибок",
    "consolidate": "закрепить: смешанные задачи вместе с прошлыми темами и проверка освоения",
}

_DRIVE_PATTERNS = (
    re.compile(r"drive\.google\.com/file/d/([A-Za-z0-9_-]{10,})"),
    re.compile(r"drive\.google\.com/(?:open|uc)\?(?:.*&)?id=([A-Za-z0-9_-]{10,})"),
)


def drive_file_id(url: str | None) -> str | None:
    if not isinstance(url, str):
        return None
    for pattern in _DRIVE_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1)
    return None
