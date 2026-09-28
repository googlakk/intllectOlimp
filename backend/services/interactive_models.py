"""Bounded deterministic numeric models shared by generation and quality checks."""

import math


MODEL_COMPONENTS = frozenset({"RuleDiscovery", "TransformationMachine"})
INPUT_LIMIT = 100
RESULT_LIMIT = 1_000_000
ANSWER_TOLERANCE = 1e-6


def _number(value: object, limit: float) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and abs(value) <= limit and math.isfinite(value))


def _numbers(value: object, *, limit: float = INPUT_LIMIT) -> bool:
    return isinstance(value, list) and 1 <= len(value) <= 6 and all(_number(item, limit) for item in value)


def rule_output(rule: dict, value: float) -> float:
    base = {"affine": lambda x: x, "square": lambda x: x * x, "absolute": abs}[rule["kind"]](value)
    return rule["multiplier"] * base + rule["offset"]


def _rule_problem(content: dict) -> str | None:
    rule = content.get("rule")
    if not isinstance(rule, dict) or rule.get("kind") not in ("affine", "square", "absolute"):
        return "нужна числовая модель affine, square или absolute"
    if not all(_number(rule.get(key), INPUT_LIMIT) for key in ("multiplier", "offset")):
        return "коэффициенты правила должны быть конечными числами от −100 до 100"
    examples, challenges = content.get("examples"), content.get("challenge_inputs")
    if not _numbers(examples) or not _numbers(challenges):
        return "нужно 1–6 примеров и 1–6 заданий с числами от −100 до 100"
    if len(set(examples)) != len(examples) or len(set(challenges)) != len(challenges) or set(examples) & set(challenges):
        return "числа примеров и заданий должны быть разными и не повторяться"
    if not all(_number(rule_output(rule, value), RESULT_LIMIT) for value in examples + challenges):
        return "результат правила выходит за пределы ±1000000"
    return None


def _machine_problem(content: dict) -> str | None:
    inputs, targets = content.get("inputs"), content.get("target_outputs")
    if not _numbers(inputs) or not _numbers(targets, limit=RESULT_LIMIT) or len(inputs) != len(targets):
        return "нужно 1–6 входных чисел от −100 до 100 и столько же конечных результатов в пределах ±1000000"
    operations, solution, max_steps = content.get("operations"), content.get("solution"), content.get("max_steps")
    if not isinstance(max_steps, int) or isinstance(max_steps, bool) or not 1 <= max_steps <= 8:
        return "число шагов должно быть целым от 1 до 8"
    if not isinstance(operations, list) or not 1 <= len(operations) <= 8:
        return "нужно от 1 до 8 операций"
    by_id = {}
    for operation in operations:
        if not isinstance(operation, dict):
            return "операция должна содержать id, название, вид и число"
        identity, label, kind, value = (operation.get(key) for key in ("id", "label", "kind", "value"))
        if not isinstance(identity, str) or not identity.strip() or identity in by_id:
            return "id операций должны быть непустыми и уникальными"
        if not isinstance(label, str) or not label.strip():
            return "у каждой операции должно быть название"
        if kind not in ("add", "subtract", "multiply", "divide") or not _number(value, INPUT_LIMIT):
            return "допустимы только сложение, вычитание, умножение и деление на число от −100 до 100"
        if kind == "divide" and value == 0:
            return "деление на ноль недопустимо"
        by_id[identity] = operation
    if not isinstance(solution, list) or not 1 <= len(solution) <= max_steps:
        return "образец решения должен содержать от 1 до max_steps операций"
    if not all(isinstance(identity, str) and identity in by_id for identity in solution):
        return "образец решения ссылается на неизвестную операцию"
    for initial, target in zip(inputs, targets):
        current = initial
        for identity in solution:
            operation = by_id[identity]
            value = operation["value"]
            match operation["kind"]:
                case "add": current += value
                case "subtract": current -= value
                case "multiply": current *= value
                case "divide": current /= value
            if not _number(current, RESULT_LIMIT):
                return "промежуточный результат выходит за пределы ±1000000"
        if abs(current - target) > ANSWER_TOLERANCE:
            return "образец решения не даёт указанные результаты для всех входных чисел"
    return None


def interactive_model_problem(component: str, content: dict) -> str | None:
    """Return a teacher-readable error, without executing generated expressions."""
    if component not in MODEL_COMPONENTS:
        return None
    if not isinstance(content, dict):
        return "содержимое блока должно быть объектом"
    if not all(isinstance(content.get(key), str) and content[key].strip() for key in ("title", "prompt", "explanation")):
        return "заполните название, задание и объяснение"
    return _rule_problem(content) if component == "RuleDiscovery" else _machine_problem(content)
