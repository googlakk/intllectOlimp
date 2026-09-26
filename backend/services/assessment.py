"""Deterministic, server-side grading for self-check assessments."""
from __future__ import annotations
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from services.math_expression import same_form, same_math


# Те же правила, что у проверки ответа в браузере
# (artifacts/intellect-learning-platform/src/features/interactiveEngines/scoring.ts);
# общие случаи — backend/fixtures/answer_check_cases.json.
_NUMBER_PREFIX = re.compile(r"^[+-]?(?:\d{1,3}(?:[   ]\d{3})+|\d+)(?:[.,]\d+)?(?:e[+-]?\d+)?", re.IGNORECASE)
_NOT_A_NUMBER = re.compile(r"^[+-]?(nan|inf|infinity)$", re.IGNORECASE)
# Хвост после числа похож на продолжение выражения, а не на единицу: «1/2», «2x+1», «= 5».
_NOT_A_UNIT = re.compile(r"[=+]|^/\d|^[xyz]$")
_SUPERSCRIPTS = str.maketrans({"²": "2", "³": "3", "¹": "1", "⁻": "-"})
# Степень десяти после числа («·10^-3», «×10⁻³») — часть числа, а не единица.
_POWER_OF_TEN = re.compile(r"^\s*[·*×⋅xх]\s*10\s*(?:\^\s*\(?\s*([+-]?\d+)\s*\)?|([⁻⁺]?[⁰¹²³⁴⁵⁶⁷⁸⁹]+))")
_SUPERSCRIPT_DIGITS = str.maketrans({"⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4", "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9", "⁻": "-", "⁺": "+"})
_LATIN_UNITS = {
    "kg": "кг", "g": "г", "mg": "мг", "t": "т", "m": "м", "km": "км", "cm": "см", "mm": "мм", "s": "с", "h": "ч", "min": "мин",
    "N": "Н", "kN": "кН", "Pa": "Па", "kPa": "кПа", "MPa": "МПа", "J": "Дж", "kJ": "кДж", "W": "Вт", "kW": "кВт",
    "V": "В", "A": "А", "Ohm": "Ом", "Ω": "Ом", "l": "л", "L": "л", "Hz": "Гц",
}



def _as_text(value: Any) -> str:
    return "" if value is None else str(value)


def normalize_unit(unit: Any) -> str:
    text = _as_text(unit).translate(_SUPERSCRIPTS).replace("^", "")
    text = re.sub(r"[\s.]+", "", text)
    return re.sub(r"[*×⋅·]", "", text)


def _canonical_unit(unit: Any) -> str:
    def token(item: str) -> str:
        match = re.fullmatch(r"([A-Za-zΩ]+)(-?\d*)", item)
        return (_LATIN_UNITS.get(match.group(1), match.group(1)) + match.group(2)) if match else item
    text = _as_text(unit).translate(_SUPERSCRIPTS).replace("^", "")
    return "/".join("".join(token(t) for t in re.split(r"[\s.*×⋅·]+", part) if t) for part in text.split("/"))


def parse_quantity(value: Any) -> tuple[Decimal, str, int] | None:
    source = re.sub(r"[−–]", "-", _as_text(value).strip())
    match = _NUMBER_PREFIX.match(source)
    if not match:
        return None
    raw = re.sub(r"[ \u00a0\u202f]", "", match.group(0)).replace(",", ".").lower()
    mantissa, _, exponent_text = raw.partition("e")
    try:
        exponent = int(exponent_text) if exponent_text else 0
        rest = source[match.end():]
        power = _POWER_OF_TEN.match(rest)
        if power:
            exponent += int(power.group(1) or power.group(2).translate(_SUPERSCRIPT_DIGITS))
            rest = rest[power.end():]
        number = Decimal(mantissa).scaleb(exponent)
    except (InvalidOperation, ValueError):
        return None
    if not number.is_finite():
        return None
    # Точность записи: знаки после запятой в мантиссе с поправкой на степень («1.5e-3» → 4).
    decimals = (len(mantissa.split(".")[1]) if "." in mantissa else 0) - exponent
    return number, rest.strip(), decimals


def _same_unit(left: str, right: str) -> bool:
    if left == right:
        return True
    prefixes = "мМmM"
    if len(left) > 1 and left[1:] == right[1:] and left[0] != right[0] and left[0] in prefixes and right[0] in prefixes:
        return False  # мПа (милли) и МПа (мега) — разные единицы
    return left.casefold() == right.casefold()


def _allowed_error(value: Decimal, decimals: int, tolerance: Any) -> Decimal:
    try:
        explicit = Decimal(_as_text(tolerance)) if tolerance not in (None, "") else None
    except InvalidOperation:
        explicit = None
    if explicit is not None and explicit.is_finite() and Decimal(0) <= explicit <= Decimal("0.5"):
        return max(Decimal("1e-9"), abs(value) * explicit)
    # Половина последнего записанного разряда: «8.9» → ±0.05, «1917» → только 1917.
    return Decimal("0.5") * Decimal(10) ** -decimals + Decimal("1e-9")


def allowed_error(value: Decimal, decimals: int, tolerance: Any = None) -> Decimal:
    """Допуск при сравнении числа с правильным ответом (нужен и тьютору)."""
    return _allowed_error(value, decimals, tolerance)


def _same_text(left: Any, right: Any) -> bool:
    def clean(value: Any) -> str:
        return " ".join(_as_text(value).strip().casefold().split())
    return bool(clean(left)) and clean(left) == clean(right)


def check_answer(
    value: Any,
    expected: Any,
    *,
    numeric: bool = False,
    unit: str | None = None,
    accepted_units: list[str] | None = None,
    tolerance: Any = None,
    mode: str | None = None,
) -> str:
    """'correct', 'wrong_unit' (число верное, единица нет) или 'incorrect'.

    Как число с единицей сравниваются только ответы числовых вопросов; выражения
    сверяются по смыслу (services/math_expression.py), остальное — как текст.
    """
    if _NOT_A_NUMBER.match(_as_text(value).strip()):
        return "incorrect"
    candidates = [_as_text(item) for item in (expected if isinstance(expected, list) else [expected])]
    if any(_same_text(value, candidate) for candidate in candidates):
        return "correct"
    # mode: "choice" — вариант ответа, только точно; "form" (выражения по умолчанию) — та же запись;
    # "equivalent" (числовые по умолчанию, уравнения) — по смыслу: 2√3 = √12, 1/2 = 0,5.
    mode = mode or ("equivalent" if numeric else "form")
    if mode == "choice":
        return "incorrect"
    if mode == "form" and any(same_form(value, candidate) for candidate in candidates):
        return "correct"
    if mode == "equivalent" and not unit and any(same_math(value, candidate, numbers=numeric) for candidate in candidates):
        return "correct"
    if not numeric:
        return "incorrect"
    given = parse_quantity(value)
    if given is None or _NOT_A_UNIT.search(normalize_unit(given[1])):
        return "incorrect"
    unit_mismatch = False
    for candidate in candidates:
        target = parse_quantity(candidate)
        if target is None or _NOT_A_UNIT.search(normalize_unit(target[1])):
            continue
        if abs(given[0] - target[0]) > _allowed_error(target[0], target[2], tolerance):
            continue
        allowed = [u for u in (_canonical_unit(item) for item in [unit or target[1], *(accepted_units or [])]) if u]
        if not given[1] or not allowed or any(_same_unit(_canonical_unit(given[1]), u) for u in allowed):
            return "correct"
        unit_mismatch = True
    return "wrong_unit" if unit_mismatch else "incorrect"


def equal_answer(value: Any, expected: Any, **spec: Any) -> bool:
    # Как и раньше, без явного указания ответ сравнивается и как число.
    spec.setdefault("numeric", True)
    return check_answer(value, expected, **spec) == "correct"


def _answer_spec(item: dict, *, numeric: bool, choice: bool = False) -> dict[str, Any]:
    mode = "choice" if choice else item.get("answer_mode") if item.get("answer_mode") in {"form", "equivalent"} else None
    return {
        "mode": mode,
        "numeric": numeric or bool(item.get("answer_unit")),
        "unit": item.get("answer_unit"),
        "accepted_units": item.get("accepted_units") if isinstance(item.get("accepted_units"), list) else None,
        "tolerance": item.get("tolerance"),
    }


def grade_assessment(blocks: list[dict], responses: dict[str, str]) -> tuple[dict[str, bool], int]:
    answers: dict[str, bool] = {}
    for index, block in enumerate(blocks):
        content = block.get("content") or {}
        if block.get("component") == "MasteryCheck":
            for question_index, question in enumerate(content.get("questions") or []):
                key = f"{index}_q{question_index}"
                answers[key] = equal_answer(
                    responses.get(key, ""), question.get("correct_answer", ""),
                    **_answer_spec(question, numeric=question.get("type") in {"numeric", "number"},
                                   choice=question.get("type") == "multiple_choice"),
                )
        elif block.get("component") in {"RetrievalCheck", "IndependentProblem"}:
            key = str(index)
            # Варианты ответа (RetrievalCheck, multiple_choice) — только точное совпадение.
            numeric = block.get("component") == "IndependentProblem" and content.get("type") in {"numeric", "number"}
            answers[key] = equal_answer(
                responses.get(key, ""), content.get("correct_answer", ""), **_answer_spec(content, numeric=numeric, choice=block.get("component") == "RetrievalCheck" or content.get("type") == "multiple_choice"),
            )
    score = round(100 * sum(answers.values()) / len(answers)) if answers else 0
    return answers, score
