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


# ---- «Решаю по шагам» (как stepSolver.ts): проверка образца решения, который собрала модель.

def parse_expression(source: Any) -> Any:
    """Одна часть записи как есть, без «x = …»."""
    text = _preprocess("" if source is None else str(source))
    if not text or "=" in text:
        return None
    tokens = _tokenize(text)
    return _Parser(tokens).parse() if tokens else None


def parse_equation(source: str) -> Any:
    sides = source.split("=")
    if len(sides) != 2:
        return None
    left, right = parse_expression(sides[0]), parse_expression(sides[1])
    return None if left is None or right is None else ("bin", "-", left, right)


_EQUATION_SAMPLES = (1.7, 2.3, 3.1, 0.6, 4.4, 1.2, 2.9, 5.3)


_ROOT_RANGE = 60
_ROOT_GRID = 0.05
_ZERO = 1e-9


def equation_roots(equation: Any) -> list[float] | str | None:
    """Корни уравнения с одной переменной (как equationRoots в stepSolver.ts): рациональные p/q
    и смена знака на сетке. 'all' — тождество, None — переменных больше одной."""
    names = list(dict.fromkeys(_ordered(equation)))
    if len(names) > 1:
        return None
    name = names[0] if names else "x"

    def f(x: float) -> float:
        return _evaluate(equation, {name: x})

    if all(abs(f(x)) < _ZERO for x in _EQUATION_SAMPLES) and abs(f(-_EQUATION_SAMPLES[0])) < _ZERO:
        return "all"
    roots: list[float] = []

    def add(x: float) -> None:
        if not any(abs(root - x) < 1e-6 for root in roots):
            roots.append(x)

    for q in range(1, 13):
        for p in range(-_ROOT_RANGE * q, _ROOT_RANGE * q + 1):
            x = p / q
            value = f(x)
            if math.isfinite(value) and abs(value) < _ZERO:
                add(x)
    steps = int(round(2 * _ROOT_RANGE / _ROOT_GRID))
    previous = f(-_ROOT_RANGE)
    for index in range(1, steps + 1):
        x = -_ROOT_RANGE + index * _ROOT_GRID
        current = f(x)
        if math.isfinite(previous) and math.isfinite(current) and previous * current < 0:
            low, high = x - _ROOT_GRID, x
            for _ in range(60):
                middle = (low + high) / 2
                if f(low) * f(middle) <= 0:
                    high = middle
                else:
                    low = middle
            root = (low + high) / 2
            if math.isfinite(f(root)) and abs(f(root)) < 1e-6:
                add(root)
        previous = current
    return sorted(roots)


def _same_root_set(first: Any, second: Any) -> bool:
    if first is None or second is None:
        return False
    if first == "all" or second == "all":
        return first == second
    return len(first) == len(second) and all(abs(a - b) < 1e-6 for a, b in zip(first, second))


def same_equation(first: Any, second: Any) -> bool:
    """Равносильны: пропорциональны (перенос, деление на число) или у уравнения с одной
    переменной те же корни (умножение на знаменатель, возведение в квадрат без посторонних корней)."""
    if _proportional(first, second):
        return True
    names = set(_ordered(first)) | set(_ordered(second))
    return len(names) <= 1 and _same_root_set(equation_roots(first), equation_roots(second))


def _proportional(first: Any, second: Any) -> bool:
    names = list(dict.fromkeys(_ordered(first) + _ordered(second)))
    ratio: float | None = None
    compared = 0
    for round_index in range(len(_EQUATION_SAMPLES)):
        scope = {name: _EQUATION_SAMPLES[(round_index + index * 3) % len(_EQUATION_SAMPLES)] for index, name in enumerate(names)}
        a, b = _evaluate(first, scope), _evaluate(second, scope)
        if not (math.isfinite(a) and math.isfinite(b)):
            continue
        if abs(a) < 1e-9 or abs(b) < 1e-9:
            if (abs(a) < 1e-9) != (abs(b) < 1e-9):
                return False
            continue
        current = b / a
        if ratio is None:
            ratio = current
        elif abs(current - ratio) > 1e-7 * max(1.0, abs(ratio)):
            return False
        compared += 1
    return compared >= 2 and ratio is not None and abs(ratio) > 1e-12


def parse_roots(source: str) -> list[float] | None:
    """«x = 2», «x = 1 или x = 3», «x₁ = 1; x₂ = 3» → корни; иначе None."""
    parts = [part for part in re.split(r"\s*(?:или|;|,(?=\s*[a-zA-Z]))\s*", source, flags=re.IGNORECASE) if part]
    roots: list[float] = []
    for part in parts:
        match = re.fullmatch(r"\s*[a-zA-Z](?:_?\d|[₁₂])?\s*=\s*(.+)", part)
        node = parse_expression(match.group(1)) if match else None
        if node is None or _ordered(node):
            return None
        value = _evaluate(node, {})
        if not math.isfinite(value):
            return None
        roots.append(value)
    return roots or None


def _roots_match(given: list[float], expected: list[float]) -> bool:
    a = sorted({round(value, 9) for value in given})
    b = sorted({round(value, 9) for value in expected})
    return len(a) == len(b) and all(abs(x - y) < 1e-7 for x, y in zip(a, b))


def _special_answer(answers: list[str]) -> str | None:
    """«любое число» → 'all', «нет корней» → 'none' (как specialAnswer в stepSolver.ts)."""
    text = " ".join(answers).lower()
    if re.search(r"любое|бесконечно много", text):
        return "all"
    if re.search(r"нет корней|корней нет|не имеет корней|решений нет|нет решений", text):
        return "none"
    return None


def check_solver_step(line: str, *, kind: str, start: str, final_answer: list[str], answer_mode: str = "form") -> tuple[str, bool]:
    """('ok'|'wrong'|'unreadable', решено ли). Ошибки из mistakes здесь не различаем — только верность строки."""
    text = line.strip()
    if not text:
        return "unreadable", False
    if kind == "equation":
        special = _special_answer(final_answer)
        start_equation = parse_equation(start)
        if special and start_equation is not None and _special_answer([text]) == special:
            roots = equation_roots(start_equation)
            fits = roots == "all" if special == "all" else isinstance(roots, list) and not roots
            return ("ok", True) if fits else ("wrong", False)
        expected_roots = next((roots for roots in map(parse_roots, final_answer) if roots), None)
        roots = parse_roots(text)
        if roots and expected_roots:
            return ("ok", True) if _roots_match(roots, expected_roots) else ("wrong", False)
        equation = parse_equation(text)
        if start_equation is None or equation is None:
            return "unreadable", False
        if not same_equation(start_equation, equation):
            return "wrong", False
        return "ok", bool(special) and not _ordered(equation)
    if parse_expression(text) is None:
        return "unreadable", False
    if not same_math(text, start):
        return "wrong", False
    compare = same_form if answer_mode != "equivalent" else same_math
    return "ok", any(compare(text, answer) for answer in final_answer)


def _roots_complete(start: str, answer: str) -> bool:
    """Корни ответа — ровно корни уравнения (ни лишних, ни потерянных)."""
    equation, roots = parse_equation(start), parse_roots(answer)
    if equation is None or roots is None:
        return False
    actual = equation_roots(equation)
    if actual is None:
        return True  # несколько переменных — полноту не проверить
    return _same_root_set(actual, sorted({round(root, 9) for root in roots}))


def step_solver_problem(content: dict[str, Any]) -> str | None:
    """Что не так в данных блока StepSolver (None — всё верно)."""
    start = str(content.get("start") or "").strip()
    raw_answer = content.get("final_answer")
    final_answer = [str(item).strip() for item in (raw_answer if isinstance(raw_answer, list) else [raw_answer]) if isinstance(item, str) and item.strip()]
    if not start or not final_answer:
        return "нет задания или ответа"
    kind = content.get("kind") if content.get("kind") in ("expression", "equation") else ("equation" if "=" in start else "expression")
    mode = "equivalent" if content.get("answer_mode") == "equivalent" else "form"
    if (parse_equation(start) if kind == "equation" else parse_expression(start)) is None:
        return "задание не читается как выражение или уравнение"
    spec = {"kind": kind, "start": start, "final_answer": final_answer, "answer_mode": mode}
    if check_solver_step(final_answer[0], **spec) != ("ok", True):
        return "ответ не следует из задания"
    if kind == "equation" and not _special_answer(final_answer) and not _roots_complete(start, final_answer[0]):
        return "в ответе не те корни или не все корни уравнения"
    for step in content.get("steps") or []:
        expected = str(step.get("expected") or "") if isinstance(step, dict) else ""
        if expected and check_solver_step(expected, **spec)[0] != "ok":
            return f"шаг образца «{expected[:40]}» не равносилен заданию"
    for mistake in content.get("mistakes") or []:
        wrong = str(mistake.get("wrong") or "") if isinstance(mistake, dict) else ""
        if wrong and check_solver_step(wrong, **spec)[0] == "ok" and check_solver_step(wrong, **spec)[1]:
            return f"«ошибка» {wrong[:40]} на самом деле верный ответ"
    return None


def solver_line_outcome(line: str, content: dict[str, Any]) -> str:
    """Строка решения StepSolver для тьютора: 'correct' — верное преобразование, иначе 'incorrect'."""
    start = str(content.get("start") or "").strip()
    raw = content.get("final_answer")
    final_answer = [str(item) for item in (raw if isinstance(raw, list) else [raw]) if isinstance(item, str) and item.strip()]
    kind = content.get("kind") if content.get("kind") in ("expression", "equation") else ("equation" if "=" in start else "expression")
    mode = "equivalent" if content.get("answer_mode") == "equivalent" else "form"
    status, _ = check_solver_step(line, kind=kind, start=start, final_answer=final_answer, answer_mode=mode)
    return "correct" if status == "ok" else "incorrect"


def function_explorer_problem(content: dict[str, Any]) -> str | None:
    """Что не так в данных блока FunctionExplorer (как normalizeExplorer в functionExplorer.ts)."""
    formula = parse_expression(re.sub(r"^\s*y\s*=\s*", "", str(content.get("formula") or ""), flags=re.IGNORECASE))
    if formula is None:
        return "формула не читается"
    params = [param for param in content.get("params") or [] if isinstance(param, dict)]
    names: dict[str, dict[str, Any]] = {}
    for param in params:
        name = str(param.get("name") or "").strip()
        low, high = param.get("min"), param.get("max")
        if not re.fullmatch(r"[a-wzA-WZ]", name) or not all(isinstance(value, (int, float)) for value in (low, high)) or low >= high:
            return f"параметр «{name}» задан неверно"
        names[name] = param
    unknown = set(_ordered(formula)) - {"x", *names}
    if unknown:
        return f"в формуле неизвестные буквы: {', '.join(sorted(unknown))}"
    target = content.get("target") if isinstance(content.get("target"), dict) else None
    target_params = target.get("params") if target and isinstance(target.get("params"), dict) else None
    if target is not None:
        if target_params is None or set(target_params) != set(names):
            return "у цели нужны значения всех параметров"
        for name, value in target_params.items():
            param = names[name]
            step = param.get("step") if isinstance(param.get("step"), (int, float)) and param.get("step") > 0 else 0.5
            if not isinstance(value, (int, float)) or not param["min"] <= value <= param["max"]:
                return f"значение цели {name} вне ползунка"
            if abs((value - param["min"]) / step - round((value - param["min"]) / step)) > 1e-6:
                return f"значение цели {name} не попадает на шаг ползунка"
        initial = {name: param.get("default", (param["min"] + param["max"]) / 2) for name, param in names.items()}
        if all(isinstance(initial[name], (int, float)) and abs(initial[name] - target_params[name]) < 1e-9 for name in names):
            return "начальные значения ползунков совпадают с целью — задание решено без действий"
        for point in content.get("points") or []:
            if isinstance(point, dict) and isinstance(point.get("x"), (int, float)) and isinstance(point.get("y"), (int, float)):
                value = _evaluate(formula, {**{key: float(item) for key, item in target_params.items()}, "x": float(point["x"])})
                if not math.isfinite(value) or abs(value - point["y"]) > 1e-6:
                    return "отмеченная точка не лежит на графике-цели"
    prediction = content.get("prediction") if isinstance(content.get("prediction"), dict) else None
    if prediction is not None:
        options = prediction.get("options") if isinstance(prediction.get("options"), list) else []
        if len(options) < 2 or prediction.get("correct_answer") not in options:
            return "у прогноза нет верного ответа среди вариантов"
    if target is None and prediction is None:
        return "нет задания: нужен прогноз или график-цель"
    if content.get("evidence_stage") == "assessment" and prediction is None:
        # Цель подбирается ползунками наугад — для итоговой проверки нужен прогноз.
        return "в итоговой проверке нужен прогноз, а не только подбор ползунками"
    return None
