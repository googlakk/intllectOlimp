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
# Только номер телефона: с кодом страны или ведущим нулём — числа из решения не трогаем.
_PHONE = re.compile(r"(?:\+\d{1,3}|(?<![\d.,])0)[\s\-()]*\d{3}(?:[\s\-()]*\d{2,4}){2,3}(?!\d)")
_HANDLE = re.compile(r"(?<!\w)@\w{3,}")

# Требуют проверки носителем языка (ky) — список расширяется по реальным диалогам.
_DISTRESS = (
    "не хочу жить", "покончить с собой", "убить себя", "умереть хочу", "хочу умереть", "меня бьют",
    "меня обижают", "суицид", "самоубий", "порежу себя",
    "жашагым келбейт", "өлгүм келет", "өзүмдү өлтүрөм", "мени сабашат", "мени кордошот",
)
_ANSWER_CUES = re.compile(r"(ответ|получится|получаем|получим|итого|равн|жооп|барабар|=)", re.IGNORECASE)
_DIGIT_CUES = re.compile(r"(цифр|после запятой|разряд|сан[ыи]|үтүрдөн кийин)", re.IGNORECASE)
_NUMBER_START = re.compile(r"(?<![\w.,])[−–+-]?\d")
_FRAC = re.compile(r"\\[dt]?frac\{\s*([−–-]?\d+(?:[.,]\d+)?)\s*\}\{\s*([−–-]?\d+(?:[.,]\d+)?)\s*\}")
_OPTION_LETTERS = ("АБВГ", "ABCD")
_ORDINALS = ("перв", "втор", "трет", "четв")
_PLAIN_FRACTION = re.compile(r"(?<![\w.,])([−–-]?\d+)\s*/\s*(\d+)(?![\d.,])")
_LETTER_CUE = r"(?:ответ\w*|правильн\w*|верн\w*|вариант\w*|жооп\w*|туура\w*)"
# Маленькое целое (0–9) встречается в любом объяснении («шаг 2», «умножь на 2»):
# для такого ответа утечка — только число рядом со словом «ответ», «=», «получится».
SMALL_INTEGER = Decimal(10)


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
    for match in _PLAIN_FRACTION.finditer(plain):
        numerator, denominator = Decimal(match.group(1).replace("−", "-").replace("–", "-")), Decimal(match.group(2))
        if denominator != 0:
            found.append(numerator / denominator)
    for match in _NUMBER_START.finditer(plain):
        quantity = parse_quantity(plain[match.start():])
        if quantity is not None:
            found.append(quantity[0])
    return found


def _digit_runs(text: str) -> list[str]:
    return re.findall(r"\d+", _latex_plain(text))


def _spelled_by_digits(reply: str, target: str) -> bool:
    """Ответ по цифрам: «первая цифра 8, после запятой 9» при ответе 8.9.

    Только одиночные цифры и только рядом со словами «цифра», «после запятой»:
    иначе «шаг 1, потом шаг 2» совпало бы с ответом 12.
    """
    digits = re.sub(r"\D", "", target).lstrip("0")
    if len(digits) < 2 or not _DIGIT_CUES.search(reply):
        return False
    runs = [run for run in _digit_runs(reply) if len(run) == 1]
    return any("".join(runs[start:end]) == digits for start in range(len(runs)) for end in range(start + 2, len(runs) + 1))


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
    current: bool = True,
) -> bool:
    """True — реплика называет итоговый ответ раньше, чем ученик до него дошёл.

    current=False — ответ другого (итогового) задания урока: его ключевые слова
    и числа тьютору нужны для объяснения, поэтому утечкой считается только
    ответ, прямо названный ответом («ответ …», «= …»), без проверки букв вариантов.
    """
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
            if _spelled_by_digits(reply, str(correct)) and not _spelled_by_digits(known, str(correct)):
                return True
            if not any(abs(value - target[0]) <= tolerance for value in _numbers(reply)):
                continue
            already_known = any(abs(value - target[0]) <= tolerance for value in _numbers(known))
            small = (target[2] <= 0 and abs(target[0]) < SMALL_INTEGER) or not current
            # Известное ученику или маленькое целое число — утечка, только если его прямо назвали ответом.
            if not (already_known or small) or _near_answer_cue(reply, target[0], tolerance):
                return True
        return False

    normalized_reply = _normalize(reply)
    normalized_known = _normalize(known)
    for correct in correct_values:
        answer = _normalize(correct)
        if not answer:
            continue
        # Короткий ответ («12», «да», «Б») — только целым словом, иначе совпадёт с чем угодно.
        pattern = rf"(?<!\w){re.escape(answer)}(?!\w)"
        if re.search(pattern, normalized_reply) and (len(answer) < 3 or not re.search(pattern, normalized_known)):
            if (len(answer) >= 3 and current) or re.search(rf"{_LETTER_CUE}\W{{0,12}}{re.escape(answer)}(?!\w)", normalized_reply):
                return True
    if not current:
        return False
    options = spec.get("options") or []
    for correct in correct_values:
        if correct not in options:
            continue
        index = options.index(correct)
        for letters in _OPTION_LETTERS:
            if index < len(letters) and re.search(rf"{_LETTER_CUE}\W{{0,12}}[«\"(]?{letters[index]}(?!\w)", reply, re.IGNORECASE):
                return True
        if index < len(_ORDINALS) and re.search(rf"{_ORDINALS[index]}\w*\s+(?:вариант|ответ)|(?:вариант|ответ)\w*\W{{0,5}}{_ORDINALS[index]}", reply, re.IGNORECASE):
            return True
    return False
