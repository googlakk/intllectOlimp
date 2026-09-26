"""Сверка школьных выражений по смыслу — та же, что в браузере
(src/features/interactiveEngines/mathExpression.ts): 2√3 = √12, x/2 = 0,5x, (a+b)² ≠ a²+b².
Разбор: числа с запятой, латинские переменные, + - * / ^, √ и sqrt, неявное умножение, LaTeX \\frac и \\sqrt.
"""

from __future__ import annotations

import math
import re
from typing import Any

_SUPERSCRIPT_POWERS = {"²": "^2", "³": "^3"}
_SAMPLES = (1.7, 2.3, 3.1, 0.6, 4.4, 1.2, 2.9)


def _preprocess(source: str) -> str:
    text = source.strip().strip("$")
    for _ in range(10):
        following = re.sub(r"\\d?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"((\1)/(\2))", text)
        following = re.sub(r"\\sqrt\s*\{([^{}]*)\}", r"√(\1)", following)
        if following == text:
            break
        text = following
    text = re.sub(r"\\cdot|\\times", "*", text)
    text = re.sub(r"\\left|\\right|\\,|\\!|\\ ", "", text)
    text = re.sub(r"sqrt", "√", text, flags=re.IGNORECASE)
    text = text.replace("{", "(").replace("}", ")")
    text = re.sub(r"[²³]", lambda match: _SUPERSCRIPT_POWERS[match.group(0)], text)
    text = re.sub(r"[−–—]", "-", text)
    text = re.sub(r"[×·⋅∙]", "*", text)
    text = re.sub(r"[:÷]", "/", text)
    return re.sub(r"\s+", "", text)


def _tokenize(text: str) -> list[tuple[str, Any]] | None:
    tokens: list[tuple[str, Any]] = []
    index = 0
    while index < len(text):
        number = re.match(r"\d+(?:[.,]\d+)?", text[index:])
        if number:
            tokens.append(("num", float(number.group(0).replace(",", "."))))
            index += len(number.group(0))
            continue
        char = text[index]
        if re.fullmatch(r"[a-zA-Z]", char):
            tokens.append(("var", char))
        elif char in "+-*/^()√":
            tokens.append(("op", char))
        else:
            return None
        index += 1
    return tokens


class _Parser:
    def __init__(self, tokens: list[tuple[str, Any]]):
        self.tokens = tokens
        self.position = 0

    def parse(self) -> Any:
        node = self.sum()
        return node if node is not None and self.position == len(self.tokens) else None

    def peek(self) -> tuple[str, Any] | None:
        return self.tokens[self.position] if self.position < len(self.tokens) else None

    def is_op(self, value: str) -> bool:
        return self.peek() == ("op", value)

    def sum(self) -> Any:
        left = self.product()
        while left is not None and (self.is_op("+") or self.is_op("-")):
            op = self.tokens[self.position][1]
            self.position += 1
            right = self.product()
            if right is None:
                return None
            left = ("bin", op, left, right)
        return left

    def product(self) -> Any:
        left = self.unary()
        while left is not None:
            if self.is_op("*") or self.is_op("/"):
                op = self.tokens[self.position][1]
                self.position += 1
                right = self.unary()
                if right is None:
                    return None
                left = ("bin", op, left, right)
                continue
            token = self.peek()
            if not token or (token[0] == "op" and token[1] not in "(√"):
                break
            right = self.power()
            if right is None:
                return None
            left = ("bin", "*", left, right)
        return left

    def unary(self) -> Any:
        if self.is_op("-"):
            self.position += 1
            arg = self.unary()
            return None if arg is None else ("neg", arg)
        if self.is_op("+"):
            self.position += 1
            return self.unary()
        return self.power()

    def power(self) -> Any:
        base = self.atom()
        if base is not None and self.is_op("^"):
            self.position += 1
            negative = self.is_op("-")
            if negative:
                self.position += 1
            exponent = self.atom()
            if exponent is None:
                return None
            return ("bin", "^", base, ("neg", exponent) if negative else exponent)
        return base

    def atom(self) -> Any:
        token = self.peek()
        if token is None:
            return None
        self.position += 1
        if token[0] in ("num", "var"):
            return token
        if token[1] == "(":
            inner = self.sum()
            if inner is None or not self.is_op(")"):
                return None
            self.position += 1
            return inner
        if token[1] == "√":
            arg = self.power()
            return None if arg is None else ("sqrt", arg)
        return None


def parse_math(source: Any) -> Any:
    """Дерево выражения или None (слова, пусто, уравнение). «x = …» — берём правую часть."""
    text = _preprocess("" if source is None else str(source))
    assignment = re.fullmatch(r"[a-zA-Z](?:_?\d)?=(.+)", text)
    if assignment:
        text = assignment.group(1)
    # Только буквы («ab», «ba») — это подпись или слово, а не выражение: сверяем как текст.
    if not text or "=" in text or (len(text) > 1 and not re.search(r"[\d+\-*/^√()]", text)):
        return None
    tokens = _tokenize(text)
    return _Parser(tokens).parse() if tokens else None


def _evaluate(node: Any, scope: dict[str, float]) -> float:
    kind = node[0]
    if kind == "num":
        return node[1]
    if kind == "var":
        return scope.get(node[1], math.nan)
    if kind == "neg":
        return -_evaluate(node[1], scope)
    if kind == "sqrt":
        value = _evaluate(node[1], scope)
        return math.nan if value < 0 or math.isnan(value) else math.sqrt(value)
    left, right = _evaluate(node[2], scope), _evaluate(node[3], scope)
    op = node[1]
    try:
        if op == "+":
            return left + right
        if op == "-":
            return left - right
        if op == "*":
            return left * right
        if op == "/":
            return math.nan if right == 0 else left / right
        result = left ** right
        return result if isinstance(result, float) or isinstance(result, int) else math.nan
    except (OverflowError, ZeroDivisionError, ValueError):
        return math.nan


def _close(left: float, right: float) -> bool:
    return abs(left - right) <= 1e-7 * max(1.0, abs(left), abs(right))


def _balanced(text: str) -> bool:
    depth = 0
    for char in text:
        depth += 1 if char == "(" else -1 if char == ")" else 0
        if depth < 0:
            return False
    return depth == 0


def same_form(left: Any, right: Any) -> bool:
    """Одна и та же запись: пробелы, знаки умножения, sqrt/√, ², LaTeX и запятая не важны,
    но 2(x+1) и 2x+2 — разные записи (задания «раскройте скобки», «сократите дробь»)."""
    def clean(value: Any) -> str:
        text = _preprocess("" if value is None else str(value)).replace("*", "").casefold()
        # Скобки вокруг одного числа или буквы не меняют запись: √(12) = √12, ((3)/(4)) = 3/4.
        for _ in range(10):
            unwrapped = re.sub(r"\(([\w.,]+)\)", r"\1", text)
            if unwrapped == text:
                break
            text = unwrapped
        # Скобки вокруг всей записи — тоже: \frac{3}{4} даёт (3/4).
        while text.startswith("(") and text.endswith(")") and _balanced(text[1:-1]):
            text = text[1:-1]
        return text
    return bool(clean(left)) and clean(left) == clean(right)


def same_math(left: Any, right: Any, *, numbers: bool = True) -> bool:
    """Равны ли выражения по смыслу: одинаковые значения при нескольких подстановках.
    numbers=False — два простых числа («8,9» и «8.9») по смыслу не сверяем: это решает вопрос."""
    first, second = parse_math(left), parse_math(right)
    if first is None or second is None:
        return False
    if not numbers and first[0] == "num" and second[0] == "num" and "=" not in f"{left}{right}":
        return False
    # Порядок переменных — как в браузере: по первому появлению в первом, затем во втором выражении.
    names = list(dict.fromkeys(_ordered(first) + _ordered(second)))
    compared = 0
    for round_index in range(len(_SAMPLES)):
        scope = {name: _SAMPLES[(round_index + index * 3) % len(_SAMPLES)] for index, name in enumerate(names)}
        x, y = _evaluate(first, scope), _evaluate(second, scope)
        if not math.isfinite(x) and not math.isfinite(y):
            continue
        if not (math.isfinite(x) and math.isfinite(y)) or not _close(x, y):
            return False
        compared += 1
        if not names:
            break
    return compared > 0


def _ordered(node: Any) -> list[str]:
    kind = node[0]
    if kind == "var":
        return [node[1]]
    if kind in ("neg", "sqrt"):
        return _ordered(node[1])
    if kind == "bin":
        return _ordered(node[2]) + _ordered(node[3])
    return []
