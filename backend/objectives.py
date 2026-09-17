"""Objective decomposition, lesson alignment and deterministic quality checks."""

from __future__ import annotations

import ast
import hashlib
import operator
import re
from typing import Any


EXPLANATION_COMPONENTS = {
    "ShortExplanation",
    "KeyConcept",
    "WorkedExample",
    "Presentation",
    "Illustration",
    "MindMap",
    "Timeline",
}
PRACTICE_COMPONENTS = {
    "GuidedPractice",
    "IndependentProblem",
    "TextEvidencePicker",
    "ArgumentBuilder",
    "InteractiveGraph",
}
ASSESSMENT_COMPONENTS = {"RetrievalCheck", "MasteryCheck"}
INDEPENDENT_ASSESSMENT_COMPONENTS = {
    "IndependentProblem",
    "RetrievalCheck",
    "TextEvidencePicker",
    "ArgumentBuilder",
    "MasteryCheck",
}
STAGE_COMPONENTS = {
    "diagnostic": {"RetrievalCheck"},
    "explanation": EXPLANATION_COMPONENTS,
    "practice": PRACTICE_COMPONENTS,
    "assessment": INDEPENDENT_ASSESSMENT_COMPONENTS,
}
ALLOWED_COMPONENTS = {
    "ShortExplanation", "KeyConcept", "WorkedExample", "GuidedPractice",
    "IndependentProblem", "RetrievalCheck", "MindMap", "Timeline",
    "TextEvidencePicker", "ArgumentBuilder", "InteractiveGraph",
    "Presentation", "Illustration", "MasteryCheck", "Reflection",
}


def _normalise(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold().replace("ё", "е")).strip(" \t\r\n-–—•.;:")


def decompose_objectives(raw: str | None) -> list[dict[str, Any]]:
    """Turn a KTP string into stable, deliberately conservative objective records."""
    if not raw or not raw.strip():
        return []
    text = re.sub(r"\r\n?", "\n", raw.strip())
    parts = re.split(r"(?:\n+|;|•|\s+(?=\d+[.)]\s+)|\s+(?=[–—-]\s+))", text)
    parts = [re.sub(r"^\s*(?:\d+[.)]|[-–—•])\s*", "", part).strip(" .;") for part in parts]
    # Split only explicit action-verb conjunctions. This avoids inventing
    # separate objectives for noun phrases such as "квадраты и корни".
    expanded: list[str] = []
    action = re.compile(r"\b[а-яё-]{4,}(?:ть|ти|чь)\b", re.IGNORECASE)
    for part in parts:
        clauses = re.split(r"\s*,\s*|\s*;\s*", part)
        for clause in clauses:
            words = re.split(r"\s+и\s+", clause, flags=re.IGNORECASE)
            if len(words) > 1 and all(action.search(word.strip()) for word in words):
                cleaned_words = [word.strip() for word in words]
                # Carry a shared complement back to a bare first verb:
                # "складывать и вычитать целые числа" -> two complete results.
                second_match = action.search(cleaned_words[1])
                first_match = action.search(cleaned_words[0])
                if first_match and second_match and not cleaned_words[0][first_match.end():].strip():
                    suffix = cleaned_words[1][second_match.end():].strip()
                    if suffix:
                        cleaned_words[0] = f"{cleaned_words[0]} {suffix}"
                expanded.extend(cleaned_words)
            else:
                expanded.append(clause.strip())
    parts = expanded
    parts = [part for part in parts if len(_normalise(part)) >= 3]
    # A single sentence is one result; do not invent granularity from conjunctions.
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for part in parts:
        normalized = _normalise(part)
        if normalized in seen:
            continue
        seen.add(normalized)
        digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]
        result.append(
            {
                "id": f"obj-{digest}",
                "text": part,
                "success_criteria": "Выполнить независимое задание по этому результату не менее чем на 80%.",
            }
        )
    return result


def objective_ids_from_content(content: dict[str, Any]) -> list[str]:
    values = content.get("objective_ids", content.get("objective_id", []))
    if isinstance(values, str):
        values = [values]
    return [value for value in values if isinstance(value, str) and value.strip()]


def _question_ids(content: dict[str, Any], valid_ids: set[str] | None = None) -> list[str]:
    ids: list[str] = []
    for question in content.get("questions", []):
        if isinstance(question, dict):
            ids.extend(objective_ids_from_content(question))
            dimension = question.get("dimension")
            if isinstance(dimension, str) and dimension.strip() and (valid_ids is None or dimension in valid_ids) and dimension not in ids:
                ids.append(dimension)
    return ids


def _safe_arithmetic(value: str) -> int | float | None:
    """Evaluate only simple arithmetic, useful for catching generated key errors."""
    expression = (
        value.replace("$", "")
        .replace(r"\times", "*")
        .replace(r"\cdot", "*")
        .replace(r"\div", "/")
        .replace("×", "*")
        .replace("÷", "/")
        .replace("{", "(")
        .replace("}", ")")
        .replace("^", "**")
        .replace("−", "-")
        .strip()
    )
    if not re.fullmatch(r"[\d\s()+\-*/%.]+", expression):
        return None

    operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.Mod: operator.mod,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    def visit(node: ast.AST) -> int | float:
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.UnaryOp) and type(node.op) in operators:
            return operators[type(node.op)](visit(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in operators:
            return operators[type(node.op)](visit(node.left), visit(node.right))
        raise ValueError

    try:
        return visit(ast.parse(expression, mode="eval"))
    except (SyntaxError, ValueError, ZeroDivisionError):
        return None


def validate_block_answers(block: dict[str, Any], index: int) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    content = block.get("content", {})
    if not isinstance(content, dict):
        return [{"code": "invalid_content", "block": index, "message": "content должен быть объектом"}]
    if block.get("component") in {"IndependentProblem", "RetrievalCheck"}:
        options = content.get("options")
        correct = content.get("correct_answer")
        if content.get("type") == "multiple_choice" or options is not None:
            if not isinstance(options, list) or len(options) != 4:
                errors.append({"code": "invalid_options", "block": index, "message": "Нужно ровно 4 варианта ответа"})
            elif correct not in options:
                errors.append({"code": "answer_not_in_options", "block": index, "message": "Правильный ответ отсутствует среди вариантов"})
    if block.get("component") == "MasteryCheck":
        questions = content.get("questions")
        if not isinstance(questions, list) or not questions:
            errors.append({"code": "empty_mastery_check", "block": index, "message": "Итоговая проверка пуста"})
        for question_index, question in enumerate(questions or []):
            if not isinstance(question, dict):
                errors.append({"code": "invalid_mastery_question", "block": index, "question": question_index, "message": "Вопрос должен быть объектом"})
                continue
            if not objective_ids_from_content(question) and not str(question.get("dimension", "")).strip():
                errors.append({"code": "missing_mastery_objective", "block": index, "question": question_index, "message": "Итоговый вопрос не связан с целью"})
            if not isinstance(question.get("correct_answer"), str) or not question["correct_answer"].strip():
                errors.append({"code": "missing_mastery_answer", "block": index, "question": question_index, "message": "У итогового вопроса нет правильного ответа"})
            if question.get("type") not in {"multiple_choice", "numeric"}:
                errors.append({"code": "invalid_mastery_type", "block": index, "question": question_index, "message": "Тип итогового вопроса должен быть multiple_choice или numeric"})
            options = question.get("options") if isinstance(question, dict) else None
            correct = question.get("correct_answer") if isinstance(question, dict) else None
            if question.get("type") == "multiple_choice" and (not isinstance(options, list) or len(options) != 4 or correct not in options):
                errors.append({"code": "invalid_mastery_options", "block": index, "question": question_index, "message": "Некорректные варианты или ответ"})
    question = content.get("question")
    correct = content.get("correct_answer")
    if isinstance(question, str) and isinstance(correct, str) and block.get("component") in {"IndependentProblem", "GuidedPractice"}:
        prompt = re.search(r"(?:вычисли|реши|calculate)\s*:?\s*(.+)", question, re.IGNORECASE)
        math = re.search(r"\$([^$]+)\$", prompt.group(1)) if prompt else None
        expression = math.group(1) if math else prompt.group(1) if prompt else ""
        expected = _safe_arithmetic(expression)
        if expected is not None:
            supplied = _safe_arithmetic(correct)
            if supplied is not None and abs(float(expected) - float(supplied)) > 1e-9:
                errors.append({"code": "arithmetic_answer_mismatch", "block": index, "message": "Ответ не совпадает с вычисленным результатом"})
    return errors


def build_coverage(blocks: list[dict[str, Any]], objectives: list[dict[str, Any]]) -> dict[str, Any]:
    ids = {item["id"] for item in objectives}
    coverage = {
        item["id"]: {
            "objective": item["text"],
            "diagnostic": [],
            "explanation": [],
            "practice": [],
            "assessment": [],
            "evidence": [],
        }
        for item in objectives
    }
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    aligned_count = 0
    for index, block in enumerate(blocks):
        component = block.get("component")
        if component not in ALLOWED_COMPONENTS:
            errors.append({"code": "unknown_component", "block": index, "message": f"Неизвестный компонент: {component}"})
            continue
        content = block.get("content") if isinstance(block, dict) else None
        if not isinstance(content, dict):
            errors.extend(validate_block_answers(block, index))
            continue
        block_ids = objective_ids_from_content(content)
        if component == "Reflection":
            if block_ids or content.get("evidence_stage"):
                warnings.append({
                    "code": "reflection_evidence_ignored",
                    "block": index,
                    "message": "Рефлексия не считается доказательством достижения цели",
                })
            errors.extend(validate_block_answers(block, index))
            continue
        if component == "MasteryCheck":
            # Only per-question links count as independent final evidence.
            # A broad block tag must not make an unmeasured objective pass.
            block_ids = []
            for question_index, question in enumerate(content.get("questions", [])):
                if not isinstance(question, dict):
                    continue
                question_ids = objective_ids_from_content(question)
                dimension = question.get("dimension")
                if isinstance(dimension, str) and dimension in ids and dimension not in question_ids:
                    question_ids.append(dimension)
                question_ids = list(dict.fromkeys(question_ids))
                if len(question_ids) != 1:
                    errors.append({
                        "code": "ambiguous_objective_evidence",
                        "block": index,
                        "question": question_index,
                        "message": "Каждый итоговый вопрос должен проверять ровно одну цель",
                    })
                    continue
                block_ids.extend(question_ids)
        block_ids = list(dict.fromkeys(block_ids))
        unknown = [item for item in block_ids if item not in ids]
        if unknown:
            errors.append({"code": "unknown_objective", "block": index, "message": f"Неизвестные цели: {', '.join(unknown)}"})
        if block_ids:
            aligned_count += 1
        else:
            warnings.append({"code": "missing_objective_ids", "block": index, "message": "Блок не связан с целью КТП"})
        stage = content.get("evidence_stage")
        if stage not in {"diagnostic", "explanation", "practice", "assessment"}:
            stage = "assessment" if component == "MasteryCheck" else "diagnostic" if component == "RetrievalCheck" else "practice" if component in PRACTICE_COMPONENTS else "explanation"
            errors.append({"code": "missing_evidence_stage", "block": index, "message": "Блок не содержит явного evidence_stage"})
        if component not in STAGE_COMPONENTS[stage]:
            errors.append({
                "code": "stage_component_mismatch",
                "block": index,
                "message": f"{component} нельзя использовать как этап {stage}",
            })
        evidence_ids = block_ids
        if component != "MasteryCheck" and stage in {"diagnostic", "assessment"} and len(block_ids) != 1:
            errors.append({
                "code": "ambiguous_objective_evidence",
                "block": index,
                "message": "Диагностическое или итоговое задание должно проверять ровно одну цель",
            })
            evidence_ids = []
        for objective_id in evidence_ids:
            if objective_id not in coverage:
                continue
            coverage[objective_id].setdefault(stage, []).append(index)
            coverage[objective_id]["evidence"].append({"block": index, "stage": stage})
        errors.extend(validate_block_answers(block, index))
    gaps = []
    for objective_id, item in coverage.items():
        missing = [stage for stage in ("diagnostic", "explanation", "practice", "assessment") if not item[stage]]
        teaching = item["explanation"] + item["practice"]
        if item["diagnostic"] and teaching and min(item["diagnostic"]) > min(teaching):
            errors.append({"code": "diagnostic_after_teaching", "objective_id": objective_id, "message": "Диагностика должна идти до объяснения или практики"})
        if missing:
            gaps.append({"objective_id": objective_id, "objective": item["objective"], "missing": missing})
    if objectives and aligned_count == 0:
        warnings.append({"code": "legacy_lesson", "message": "Урок создан до objective-разметки и требует повторной проверки"})
    return {
        "objectives": coverage,
        "gaps": gaps,
        "errors": errors,
        "warnings": warnings,
        "legacy": bool(objectives and aligned_count == 0),
        "publishable": not errors and not gaps and bool(objectives),
    }


def quality_report(blocks: list[dict[str, Any]], raw_objectives: str | None) -> dict[str, Any]:
    objectives = decompose_objectives(raw_objectives)
    coverage = build_coverage(blocks, objectives)
    return {"objectives": objectives, "quality_report": coverage}


def calculate_objective_mastery(
    blocks: list[dict[str, Any]],
    objectives: list[dict[str, Any]],
    answers: dict[str, Any],
    attempts_by_step: dict[str, Any],
    lesson_completed: bool = False,
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]], str]:
    """Derive objective evidence from lesson mappings instead of trusting client results."""
    mastery: dict[str, Any] = {}
    evidence: dict[str, list[dict[str, Any]]] = {}

    for objective in objectives:
        objective_id = objective["id"]
        records: list[dict[str, Any]] = []
        expected_final = 0
        expected_diagnostic = 0

        for block_index, block in enumerate(blocks):
            content = block.get("content")
            if not isinstance(content, dict):
                continue
            stage = content.get("evidence_stage")
            component = block.get("component")
            if component == "MasteryCheck":
                if stage != "assessment":
                    continue
                for question_index, question in enumerate(content.get("questions", [])):
                    if not isinstance(question, dict):
                        continue
                    question_ids = objective_ids_from_content(question)
                    if question.get("dimension") == objective_id and objective_id not in question_ids:
                        question_ids.append(objective_id)
                    question_ids = list(dict.fromkeys(question_ids))
                    if question_ids != [objective_id]:
                        continue
                    expected_final += 1
                    key = f"{block_index}_q{question_index}"
                    if key in answers:
                        records.append({
                            "objective_id": objective_id,
                            "block_index": block_index,
                            "question_index": question_index,
                            "stage": "assessment",
                            "correct": answers[key] is True,
                            "attempts": int(attempts_by_step.get(str(block_index), attempts_by_step.get(block_index, 1)) or 1),
                        })
                continue

            mapped_ids = list(dict.fromkeys(objective_ids_from_content(content)))
            if mapped_ids != [objective_id]:
                continue
            if stage == "diagnostic":
                expected_diagnostic += 1
            elif stage == "assessment":
                expected_final += 1
            else:
                continue
            key = str(block_index)
            if key in answers or block_index in answers:
                correct = answers.get(key, answers.get(block_index)) is True
                records.append({
                    "objective_id": objective_id,
                    "block_index": block_index,
                    "stage": stage,
                    "correct": correct,
                    "attempts": int(attempts_by_step.get(key, attempts_by_step.get(block_index, 1)) or 1),
                })

        diagnostic_records = [item for item in records if item["stage"] == "diagnostic"]
        final_records = [item for item in records if item["stage"] == "assessment"]
        diagnostic_score = round(
            100 * sum(item["correct"] for item in diagnostic_records) / expected_diagnostic
        ) if expected_diagnostic else 0
        final_score = round(
            100 * sum(item["correct"] for item in final_records) / expected_final
        ) if expected_final else 0
        diagnostic_passed = (
            expected_diagnostic > 0
            and len(diagnostic_records) == expected_diagnostic
            and diagnostic_score >= 80
        )
        final_passed = (
            expected_final > 0
            and len(final_records) == expected_final
            and final_score >= 80
            and any(item["correct"] for item in final_records)
        )
        if final_passed:
            status = "mastered"
        elif lesson_completed or final_records:
            status = "needs_practice"
        elif diagnostic_records:
            status = "in_progress"
        else:
            status = "not_assessed"

        mastery[objective_id] = {
            "status": status,
            "score": final_score,
            "diagnostic_score": diagnostic_score,
            "diagnostic_passed": diagnostic_passed,
            "final_passed": final_passed,
        }
        evidence[objective_id] = records

    statuses = [item["status"] for item in mastery.values()]
    if statuses and all(status == "mastered" for status in statuses):
        mastery_status = "mastered"
    elif lesson_completed or any(status == "needs_practice" for status in statuses):
        mastery_status = "needs_practice"
    elif any(status == "in_progress" for status in statuses):
        mastery_status = "in_progress"
    else:
        mastery_status = "not_assessed"
    return mastery, evidence, mastery_status