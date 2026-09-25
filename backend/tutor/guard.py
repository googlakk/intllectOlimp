"""Защитные проверки тьютора — кодом, не моделью.

Главное: реплика не должна раскрывать итоговый ответ, пока ученик до него
не дошёл. Числа сверяются по тем же правилам, что и ответы урока.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from services.assessment import allowed_error, parse_quantity

MESSAGE_LIMIT = 500

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_PHONE = re.compile(r"\+?\d[\d\s()\-]{7,}\d")
_HANDLE = re.compile(r"(?<!\w)@\w{3,}")

# Требуют проверки носителем языка (ky) — список расширяется по реальным диалогам.
_DISTRESS = (
    "не хочу жить", "покончить с собой", "убить себя", "умереть хочу", "хочу умереть", "меня бьют",
    "меня обижают", "суицид", "самоубий", "порежу себя",
    "жашагым келбейт", "өлгүм келет", "өзүмдү өлтүрөм", "мени сабашат", "мени кордошот",
)
_ANSWER_CUES = re.compile(r"(ответ|получится|получаем|получим|итого|равн|жооп|=)", re.IGNORECASE)
_NUMBER_START = re.compile(r"(?<![\w.,])[−–+-]?\d")
_FRAC = re.compile(r"\\[dt]?frac\{\s*([−–-]?\d+(?:[.,]\d+)?)\s*\}\{\s*([−–-]?\d+(?:[.,]\d+)?)\s*\}")
_OPTION_LETTERS = ("АБВГ", "ABCD")


def scrub_pii(text: str | None) -> str:
    """Убирает телефоны, почту, ссылки и @ники; не длиннее MESSAGE_LIMIT."""
    value = str(text or "")
    for pattern, mask in ((_EMAIL, "[почта]"), (_URL, "[ссылка]"), (_PHONE, "[номер]"), (_HANDLE, "[ник]")):
        value = pattern.sub(mask, value)
    return value.strip()[:MESSAGE_LIMIT]


def detect_distress(text: str | None) -> bool:
    lowered = str(text or "").casefold().replace("ё", "е")
    return any(phrase in lowered for phrase in _DISTRESS)


def _latex_plain(text: str) -> str:
    return (text.replace("\\cdot", "·").replace("\\times", "×").replace("{,}", ",")
            .replace("\\,", "").replace("$", " "))


def _numbers(text: str) -> list[Decimal]:
    """Все числа в тексте, включая дроби \\frac{a}{b} и записи со степенью десяти."""
    plain = _latex_plain(text)
    found: list[Decimal] = []
    for match in _FRAC.finditer(plain):
        numerator, denominator = (Decimal(part.replace(",", ".").replace("−", "-").replace("–", "-")) for part in match.groups())
        if denominator != 0:
            found.append(numerator / denominator)
    for match in _NUMBER_START.finditer(plain):
        quantity = parse_quantity(plain[match.start():])
        if quantity is not None:
            found.append(quantity[0])
    return found


def _near_answer_cue(text: str, target: Decimal, tolerance: Decimal) -> bool:
    plain = _latex_plain(text)
    for match in _NUMBER_START.finditer(plain):
        quantity = parse_quantity(plain[match.start():])
        if quantity is not None and abs(quantity[0] - target) <= tolerance:
            if _ANSWER_CUES.search(plain[max(0, match.start() - 20):match.start()]):
                return True
    return False


def _normalize(text: Any) -> str:
    lowered = str(text or "").casefold().replace("ё", "е")
    return " ".join(re.sub(r"[^\w\s/.,-]", " ", lowered).split())


def detect_answer_leak(
    reply: str,
    spec: dict[str, Any],
    *,
    question_text: str = "",
    student_value: str | None = None,
    shown_hints: list[str] | None = None,
    reached: bool = False,
) -> bool:
    """True — реплика называет итоговый ответ раньше, чем ученик до него дошёл."""
    if reached or not reply:
        return False
    known = " ".join([question_text, student_value or "", *(shown_hints or [])])
    correct_values = spec.get("correct") if isinstance(spec.get("correct"), list) else [spec.get("correct")]

    if spec.get("numeric"):
        for correct in correct_values:
            target = parse_quantity(correct)
            if target is None:
                continue
            tolerance = allowed_error(target[0], target[2], spec.get("tolerance"))
            if not any(abs(value - target[0]) <= tolerance for value in _numbers(reply)):
                continue
            already_known = any(abs(value - target[0]) <= tolerance for value in _numbers(known))
            # Число уже есть в условии или в ответе ученика — утечка, только если его прямо назвали ответом.
            if not already_known or _near_answer_cue(reply, target[0], tolerance):
                return True
        return False

    normalized_reply = _normalize(reply)
    normalized_known = _normalize(known)
    for correct in correct_values:
        answer = _normalize(correct)
        if len(answer) >= 3 and answer in normalized_reply and answer not in normalized_known:
            return True
    options = spec.get("options") or []
    for correct in correct_values:
        if correct in options:
            index = options.index(correct)
            for letters in _OPTION_LETTERS:
                if index < len(letters) and re.search(rf"вариант\w*\s*[«\"(]?{letters[index]}\b", reply, re.IGNORECASE):
                    return True
    return False
