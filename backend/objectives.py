"""Objective decomposition, lesson alignment and deterministic quality checks."""

from __future__ import annotations

import ast
import copy
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
    "GeneratedMedia",
    "MindMap",
    "Timeline",
    "PredictionLab",
    "HotspotInvestigation",
}
PRACTICE_COMPONENTS = {
    "GuidedPractice",
    "IndependentProblem",
    "TextEvidencePicker",
    "ArgumentBuilder",
    "InteractiveGraph",
    "SortAndClassify",
    "ProcessBuilder",
    "ArgumentMap",
    "BranchingScenario",
    "MisconceptionDebugger",
    "DataInvestigation",
    "PhysicsSandbox",
    "CodeBlocksLab",
    "ChronologyLine",
    "CauseEffectMap",
    "StepSolver",
}
ASSESSMENT_COMPONENTS = {"RetrievalCheck", "MasteryCheck"}
INDEPENDENT_ASSESSMENT_COMPONENTS = {
    "IndependentProblem",
    "RetrievalCheck",
    "TextEvidencePicker",
    "ArgumentBuilder",
    "SortAndClassify",
    "ProcessBuilder",
    "ArgumentMap",
    "BranchingScenario",
    "MisconceptionDebugger",
    "PredictionLab",
    "DataInvestigation",
    "PhysicsSandbox",
    "HotspotInvestigation",
    "CodeBlocksLab",
    "ChronologyLine",
    "CauseEffectMap",
    "StepSolver",
    "MasteryCheck",
}
HEAVY_ENGINE_COMPONENTS = {
    "ProcessBuilder",
    "ArgumentMap",
    "BranchingScenario",
    "PredictionLab",
    "DataInvestigation",
    "PhysicsSandbox",
    "HotspotInvestigation",
    "CodeBlocksLab",
    "ChronologyLine",
    "CauseEffectMap",
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
    "Presentation", "Illustration", "GeneratedMedia", "MasteryCheck", "Reflection",
    "SortAndClassify", "ProcessBuilder", "ArgumentMap",
    "BranchingScenario", "MisconceptionDebugger", "PredictionLab",
    "DataInvestigation", "PhysicsSandbox", "HotspotInvestigation",
    "CodeBlocksLab",
    "ChronologyLine",
    "CauseEffectMap",
    "StepSolver",
}
# Выведены из употребления: генератор их не выбирает, в конструкторе и каталоге
# их нет. В ALLOWED_COMPONENTS остаются, чтобы уже созданные уроки открывались
# и проходили проверку качества.
RETIRED_COMPONENTS = frozenset({"HotspotInvestigation"})
GENERATION_COMPONENTS = frozenset(ALLOWED_COMPONENTS - RETIRED_COMPONENTS)


def _normalise(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold().replace("ё", "е")).strip(" \t\r\n-–—•.;:")


def _legacy_split(text: str) -> list[str]:
    """Прежнее деление — по запятым и союзу «и».

    В продукте больше не используется: оно давало обрывки вида
    «складывать целые числа, распознавая обобщения. Помните, что скобки».
    Осталось только чтобы вычислить идентификаторы, под которыми цели были
    сохранены раньше, и перенести на них ссылки уже сгенерированных уроков.
    """
    parts = re.split(r"(?:\n+|;|•|\s+(?=\d+[.)]\s+)|\s+(?=[–—-]\s+))", text)
    parts = [re.sub(r"^\s*(?:\d+[.)]|[-–—•])\s*", "", part).strip(" .;") for part in parts]
    expanded: list[str] = []
    action = re.compile(r"\b[а-яё-]{4,}(?:ть|ти|чь)\b", re.IGNORECASE)
    for part in parts:
        comma_segments = re.split(r"\s*,\s*", part)
        clauses: list[str] = []
        current = comma_segments[0]
        for segment in comma_segments[1:]:
            measurable = re.sub(r"^(?:а\s+также|также)\s+", "", segment, flags=re.IGNORECASE)
            if action.search(measurable):
                clauses.append(current)
                current = measurable
            else:
                current = f"{current}, {segment}"
        clauses.append(current)
        for clause in clauses:
            words = re.split(r"\s+и\s+", clause, flags=re.IGNORECASE)
            if len(words) > 1 and all(action.search(word.strip()) for word in words):
                cleaned = [word.strip() for word in words]
                first, second = action.search(cleaned[0]), action.search(cleaned[1])
                if first and second and not cleaned[0][first.end():].strip():
                    suffix = cleaned[1][second.end():].strip()
                    if suffix:
                        cleaned[0] = f"{cleaned[0]} {suffix}"
                expanded.extend(cleaned)
            else:
                expanded.append(clause.strip())
    return expanded


def _fragment_id(text: str) -> str | None:
    normalized = _normalise(text)
    if len(normalized) < 3:
        return None
    return f"obj-{hashlib.sha1(normalized.encode('utf-8')).hexdigest()[:12]}"


def _historic_fragments(text: str) -> list[str]:
    """Куски, на которые это предложение могли порезать прежние версии.

    Нужно только для переноса ссылок: уроки, сгенерированные раньше, помнят
    идентификаторы обрывков (кусок до запятой, часть после «а также»,
    половинки вокруг союза «и»). Сам текст цели при этом не меняется.
    """
    fragments: list[str] = []
    for chunk in re.split(r"(?:\n+|;|•)", text):
        chunk = re.sub(r"^\s*(?:\d+[.)]|[-–—•])\s*", "", chunk).strip()
        if not chunk:
            continue
        fragments.append(chunk)
        segments = re.split(r"\s*,\s*", chunk)
        if len(segments) > 1:
            for segment in segments:
                segment = segment.strip()
                fragments.append(segment)
                stripped = re.sub(
                    r"^(?:а\s+также|также|а)\s+", "", segment, flags=re.IGNORECASE
                )
                if stripped != segment:
                    fragments.append(stripped)
    fragments.extend(_legacy_split(text))
    return fragments


def build_objective_aliases(
    objectives: list[dict[str, Any]],
    raw: str | None,
) -> dict[str, str]:
    """Старый идентификатор → цель, внутри которой этот обрывок целиком лежит.

    Переносим ссылку только когда подходящая цель ровно одна: иначе урок
    молча привязался бы не к тому результату.
    """
    known_ids = {item["id"] for item in objectives}
    candidates: dict[str, set[str]] = {}

    for item in objectives:
        for fragment in _historic_fragments(item["text"]):
            fragment_id = _fragment_id(fragment)
            if fragment_id is None or fragment_id in known_ids:
                continue
            candidates.setdefault(fragment_id, set()).add(item["id"])

    # Прежнее деление применялось ко всему тексту целиком, поэтому обрывок мог
    # склеить хвост одного предложения с началом другого — такие переносим по
    # вхождению и тоже только при единственном совпадении.
    for legacy in _decompose_objectives(raw, conservative_commas=False):
        if legacy["id"] in known_ids or legacy["id"] in candidates:
            continue
        fragment = _normalise(legacy["text"])
        if not fragment:
            continue
        matches = {
            item["id"] for item in objectives if fragment in _normalise(item["text"])
        }
        if matches:
            candidates[legacy["id"]] = matches

    return {
        legacy_id: next(iter(targets))
        for legacy_id, targets in candidates.items()
        if len(targets) == 1
    }


def _decompose_objectives(
    raw: str | None,
    *,
    conservative_commas: bool,
) -> list[dict[str, Any]]:
    """Turn a KTP string into stable, deliberately conservative objective records."""
    if not raw or not raw.strip():
        return []
    text = re.sub(r"\r\n?", "\n", raw.strip())
    # Явные разделители списка: перевод строки, точка с запятой, маркер, номер пункта.
    parts = re.split(r"(?:\n+|;|•|\s+(?=\d+[.)]\s+)|\s+(?=[–—-]\s+))", text)
    parts = [re.sub(r"^\s*(?:\d+[.)]|[-–—•])\s*", "", part).strip() for part in parts]

    # Дальше режем ТОЛЬКО по границам предложений. Деление по запятым и союзу
    # "и" давало обрывки вида "складывать целые числа, распознавая обобщения.
    # Помните, что скобки" — не цель обучения, а кусок текста через точку.
    # Требуем заглавную букву после точки, чтобы не разрывать "стр. 12".
    if not conservative_commas:                 # режим расчёта прежних ID
        parts = _legacy_split(text)
    else:
        sentence_boundary = re.compile(r"(?<=[.!?])\s+(?=[А-ЯЁA-Z])")
        expanded: list[str] = []
        for part in parts:
            for sentence in sentence_boundary.split(part):
                sentence = sentence.strip().strip(";")
                if sentence:
                    expanded.append(sentence)
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


def decompose_objectives(raw: str | None) -> list[dict[str, Any]]:
    """Разбивает текст целей из КТП на отдельные результаты — по предложениям."""
    return _decompose_objectives(raw, conservative_commas=True)


def default_evidence_stage(component: str) -> str | None:
    if component == "Reflection":
        return None
    if component == "RetrievalCheck":
        return "diagnostic"
    if component == "MasteryCheck":
        return "assessment"
    if component in PRACTICE_COMPONENTS:
        return "practice"
    if component in EXPLANATION_COMPONENTS:
        return "explanation"
    return None


def normalize_lesson_blocks(
    blocks: list[dict[str, Any]],
    objectives: list[dict[str, Any]],
    objective_aliases: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Restore only unambiguous service metadata without changing visible content."""
    normalized = copy.deepcopy(blocks)
    restored_stages = 0
    restored_block_links = 0
    restored_question_links = 0
    single_objective_id = objectives[0]["id"] if len(objectives) == 1 else None
    aliases = objective_aliases or {}

    for block in normalized:
        if not isinstance(block, dict):
            continue
        component = block.get("component")
        content = block.get("content")
        if not isinstance(component, str) or not isinstance(content, dict):
            continue
        if component == "Reflection":
            continue

        if content.get("evidence_stage") not in STAGE_COMPONENTS:
            inferred = default_evidence_stage(component)
            if inferred is not None:
                content["evidence_stage"] = inferred
                restored_stages += 1

        block_ids = objective_ids_from_content(content)
        canonical_block_ids = list(dict.fromkeys(aliases.get(item, item) for item in block_ids))
        if canonical_block_ids != block_ids:
            content["objective_ids"] = canonical_block_ids
            content.pop("objective_id", None)
            restored_block_links += 1
        elif single_objective_id and not block_ids:
            content["objective_ids"] = [single_objective_id]
            restored_block_links += 1

        if component == "MasteryCheck" and single_objective_id:
            for question in content.get("questions", []):
                if not isinstance(question, dict):
                    continue
                question_ids = objective_ids_from_content(question)
                canonical_question_ids = list(dict.fromkeys(
                    aliases.get(item, item) for item in question_ids
                ))
                if canonical_question_ids != question_ids:
                    question["objective_ids"] = canonical_question_ids
                    question.pop("objective_id", None)
                    restored_question_links += 1
                elif not question_ids:
                    question["objective_ids"] = [single_objective_id]
                    restored_question_links += 1

    restored_total = restored_stages + restored_block_links + restored_question_links
    warnings = []
    if restored_total:
        warnings.append({
            "code": "legacy_metadata_restored",
            "message": (
                "Служебная разметка восстановлена автоматически без изменения содержания: "
                f"этапы — {restored_stages}, связи блоков с целью — {restored_block_links}, "
                f"связи итоговых вопросов — {restored_question_links}."
            ),
            "restored_stages": restored_stages,
            "restored_block_links": restored_block_links,
            "restored_question_links": restored_question_links,
        })
    return normalized, warnings


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


def build_coverage(
    blocks: list[dict[str, Any]],
    objectives: list[dict[str, Any]],
    *,
    allow_legacy_diagnostic_order: bool = False,
    assessment_only: bool = False,
) -> dict[str, Any]:
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
        # Разминка в начале урока одна на весь урок, поэтому для каждой цели
        # её не требуем; если она есть, она по-прежнему должна идти первой.
        required_stages = ("assessment",) if assessment_only else ("explanation", "practice", "assessment")
        missing = [stage for stage in required_stages if not item[stage]]
        teaching = item["explanation"] + item["practice"]
        if (
            item["diagnostic"]
            and teaching
            and min(item["diagnostic"]) > min(teaching)
            and not allow_legacy_diagnostic_order
        ):
            errors.append({
                "code": "diagnostic_after_teaching",
                "objective_id": objective_id,
                "message": "Диагностика должна идти до объяснения или практики",
            })
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


def _lesson_shape_warnings_and_errors(
    blocks: list[dict[str, Any]],
    topic_contract: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not isinstance(topic_contract, dict):
        return [], []

    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    budget = topic_contract.get("block_budget")
    budget = budget if isinstance(budget, dict) else {}
    minimum = budget.get("min")
    maximum = budget.get("max")
    heavy_max = budget.get("heavy_max")
    block_count = len(blocks)
    shape = str(topic_contract.get("lesson_shape") or "")
    volume = str(topic_contract.get("volume") or "")

    if isinstance(minimum, int) and block_count < minimum:
        errors.append({
            "code": "lesson_too_short_for_topic_volume",
            "message": (
                f"Урок слишком короткий для объёма темы: {block_count} блоков, "
                f"ожидается минимум {minimum}."
            ),
            "block_count": block_count,
            "expected_min": minimum,
        })
    if isinstance(maximum, int) and block_count > maximum:
        warnings.append({
            "code": "lesson_exceeds_topic_block_budget",
            "message": (
                f"Урок превышает рекомендуемый объём: {block_count} блоков, "
                f"рекомендуется до {maximum}."
            ),
            "block_count": block_count,
            "expected_max": maximum,
        })

    heavy_count = sum(1 for block in blocks if block.get("component") in HEAVY_ENGINE_COMPONENTS)
    if isinstance(heavy_max, int) and heavy_count > heavy_max:
        warnings.append({
            "code": "too_many_heavy_interactive_blocks",
            "message": (
                f"Слишком много тяжёлых интерактивных блоков для этого объёма темы: "
                f"{heavy_count}, рекомендуется до {heavy_max}."
            ),
            "heavy_count": heavy_count,
            "heavy_max": heavy_max,
        })

    if volume == "micro" and block_count > 9:
        warnings.append({
            "code": "micro_topic_overexpanded",
            "message": "Маленькая тема выглядит перегруженной; сократите объяснение или практику.",
        })
    if shape == "assessment_only" or topic_contract.get("lesson_type") == "assessment":
        for index, block in enumerate(blocks):
            if block.get("component") not in {"RetrievalCheck", "IndependentProblem", "MasteryCheck"}:
                errors.append({
                    "code": "assessment_unsupported_component", "block": index,
                    "message": "В контрольной используйте вопрос, самостоятельную задачу или итоговую проверку. Разбор доступен после сдачи.",
                })
    if shape == "project_or_practical":
        has_criteria = any(
            isinstance(block.get("content"), dict)
            and any("критер" in str(value).casefold() for value in block["content"].values())
            for block in blocks
        )
        if not has_criteria:
            warnings.append({
                "code": "project_lesson_missing_criteria",
                "message": "Проектный урок должен явно описывать критерии результата.",
            })
    return errors, warnings


_EMPTY_EXPLANATION_WORDS = {"ответ", "верно", "правильно", "правильный", "это", "да", "итак", "получаем"}


def _explanation_without_path(explanation: Any, correct: Any) -> bool:
    """Объяснение только повторяет ответ: «Ответ 9» вместо «$3^2 = 3 \\cdot 3 = 9$»."""
    if not isinstance(explanation, str) or not explanation.strip():
        return False
    words = re.findall(r"\w+", explanation.casefold())
    answer = set(re.findall(r"\w+", str(correct or "").casefold()))
    return not [word for word in words if word not in answer and word not in _EMPTY_EXPLANATION_WORDS]


def explanation_path_warnings(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Предупреждения учителю, когда урок показывает ответ без пути к нему."""
    warnings: list[dict[str, Any]] = []
    for index, block in enumerate(blocks):
        content = block.get("content")
        if not isinstance(content, dict):
            continue
        if block.get("component") == "WorkedExample":
            steps = [step for step in content.get("steps") or [] if isinstance(step, dict)]
            has_formula = "$" in str(content.get("problem", ""))
            if len(steps) < 2 or (has_formula and not any(str(step.get("math", "")).strip() for step in steps)):
                warnings.append({
                    "code": "worked_example_without_path",
                    "block": index,
                    "message": "Разобранный пример показывает ответ без хода решения",
                })
        if _explanation_without_path(content.get("explanation"), content.get("correct_answer")):
            warnings.append({
                "code": "explanation_without_path",
                "block": index,
                "message": "Объяснение повторяет ответ и не показывает, как он получен",
            })
        for question_index, question in enumerate(content.get("questions") or []):
            if isinstance(question, dict) and _explanation_without_path(question.get("explanation"), question.get("correct_answer")):
                warnings.append({
                    "code": "explanation_without_path",
                    "block": index,
                    "question": question_index,
                    "message": "Объяснение повторяет ответ и не показывает, как он получен",
                })
    return warnings


_CAUSE_ROLE_ALIASES = {
    "cause": "cause", "причина": "cause", "себеп": "cause",
    "trigger": "trigger", "повод": "trigger", "шылтоо": "trigger",
    "consequence": "consequence", "последствие": "consequence", "следствие": "consequence", "натыйжа": "consequence",
    "unrelated": "unrelated", "не связано": "unrelated", "байланышы жок": "unrelated",
}


def _cause_role(value: Any) -> str | None:
    """Как во фронтенде (causeEffect.ts normalizeRole): регистр, пробелы, русские и кыргызские слова."""
    return _CAUSE_ROLE_ALIASES.get(str(value or "").strip().lower().replace("ё", "е"))


def component_content_warnings(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Проверка данных интерактивов, которые модель могла собрать неаккуратно.

    Это ошибки, а не рекомендации: повреждённый блок не должен дойти до учеников."""
    warnings: list[dict[str, Any]] = []
    for index, block in enumerate(blocks):
        if not isinstance(block, dict) or block.get("component") != "ChronologyLine":
            continue
        content = block.get("content") if isinstance(block.get("content"), dict) else {}
        events = content.get("events") if isinstance(content.get("events"), list) else []
        ids = [str(event.get("id")) for event in events if isinstance(event, dict)]
        good_years = all(isinstance(event, dict) and isinstance(event.get("year"), int) and not isinstance(event.get("year"), bool)
                         for event in events)
        if not 3 <= len(events) <= 7 or not good_years or len(set(ids)) != len(ids):
            warnings.append({
                "code": "chronology_line_invalid",
                "block": index,
                "message": "Лента событий: нужно 3–7 событий с годами числом и разными id — исправьте или перегенерируйте блок",
            })
    for index, block in enumerate(blocks):
        if not isinstance(block, dict) or block.get("component") != "CauseEffectMap":
            continue
        content = block.get("content") if isinstance(block.get("content"), dict) else {}
        factors = content.get("factors") if isinstance(content.get("factors"), list) else []
        roles = [_cause_role(factor.get("role")) for factor in factors if isinstance(factor, dict)]
        ids = [str(factor.get("id")) for factor in factors if isinstance(factor, dict)]
        event = content.get("event")
        if (len(factors) < 4 or roles.count("trigger") > 1 or "cause" not in roles or "consequence" not in roles
                or any(role is None for role in roles) or len(set(ids)) != len(ids)
                or not ((isinstance(event, dict) and event.get("label")) or (isinstance(event, str) and event.strip()))):
            warnings.append({
                "code": "cause_effect_map_invalid",
                "block": index,
                "message": "Причины и следствия: нужны событие, 4+ фактора с ролями, причина и последствие, не больше одного повода — исправьте или перегенерируйте блок",
            })
    from services.math_expression import step_solver_problem

    for index, block in enumerate(blocks):
        if not isinstance(block, dict) or block.get("component") != "StepSolver":
            continue
        problem = step_solver_problem(block.get("content") if isinstance(block.get("content"), dict) else {})
        if problem:
            warnings.append({
                "code": "step_solver_invalid",
                "block": index,
                "message": f"Решаю по шагам: {problem} — исправьте или перегенерируйте блок",
            })
    return warnings


def quality_report(
    blocks: list[dict[str, Any]],
    raw_objectives: str | None,
    topic_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    objectives = decompose_objectives(raw_objectives)
    # Уроки, сгенерированные до перехода на деление по предложениям, ссылаются
    # на прежние идентификаторы — переносим их на нынешние цели.
    objective_aliases = build_objective_aliases(objectives, raw_objectives)
    normalized_blocks, normalization_warnings = normalize_lesson_blocks(
        blocks,
        objectives,
        objective_aliases,
    )
    coverage = build_coverage(
        normalized_blocks,
        objectives,
        allow_legacy_diagnostic_order=bool(normalization_warnings),
        assessment_only=bool(topic_contract and (topic_contract.get("lesson_type") == "assessment" or topic_contract.get("lesson_shape") == "assessment_only")),
    )
    shape_errors, shape_warnings = _lesson_shape_warnings_and_errors(
        normalized_blocks,
        topic_contract,
    )
    coverage["errors"] = coverage["errors"] + shape_errors
    coverage["warnings"] = normalization_warnings + coverage["warnings"]
    coverage["warnings"] = coverage["warnings"] + shape_warnings
    coverage["warnings"] = coverage["warnings"] + explanation_path_warnings(normalized_blocks)
    coverage["errors"] = coverage["errors"] + component_content_warnings(normalized_blocks)
    coverage["publishable"] = not coverage["errors"] and not coverage["gaps"] and bool(objectives)
    return {
        "objectives": objectives,
        "normalized_blocks": normalized_blocks,
        "quality_report": coverage,
    }


def calculate_objective_mastery(
    blocks: list[dict[str, Any]],
    objectives: list[dict[str, Any]],
    answers: dict[str, Any],
    attempts_by_step: dict[str, Any],
    lesson_completed: bool = False,
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]], str]:
    """Derive objective evidence from lesson mappings instead of trusting client results."""
    blocks, _warnings = normalize_lesson_blocks(blocks, objectives)
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
