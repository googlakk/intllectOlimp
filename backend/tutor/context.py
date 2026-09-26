"""Контекст тьютора из урока и хода ученика. Чистые функции, без базы и сети.

Контекст делится на кэшируемую часть (урок целиком — общая для класса) и
некэшируемую (текущий шаг, ответ ученика, реплики по этому заданию).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

# Те же блоки, что во фронтенде считаются оцениваемыми (src/lib/lessonBlocks.ts):
# всё остальное — теория, к которой можно вернуться.
ASSESSMENT_COMPONENTS = frozenset({
    "GuidedPractice", "IndependentProblem", "RetrievalCheck", "TextEvidencePicker", "ArgumentBuilder",
    "SortAndClassify", "ProcessBuilder", "ArgumentMap", "BranchingScenario", "MisconceptionDebugger",
    "PredictionLab", "DataInvestigation", "PhysicsSandbox", "HotspotInvestigation", "CodeBlocksLab", "ChronologyLine", "CauseEffectMap",
    "StepSolver", "MasteryCheck",
})
LESSON_CONTEXT_LIMIT = 12000
BLOCK_TEXT_LIMIT = 1200


def _content(block: dict[str, Any]) -> dict[str, Any]:
    return block.get("content") if isinstance(block.get("content"), dict) else {}


def assessment_mode(block: dict[str, Any]) -> bool:
    """Итоговое задание: тьютор молчит, чтобы оценка освоения была честной."""
    return block.get("component") == "MasteryCheck" or _content(block).get("evidence_stage") == "assessment"


def nearest_theory_index(blocks: list[dict[str, Any]], block_index: int) -> int | None:
    """Ближайшее объяснение перед заданием — как findNearestExplanation во фронтенде."""
    for index in range(min(block_index, len(blocks)) - 1, -1, -1):
        if blocks[index].get("component") not in ASSESSMENT_COMPONENTS:
            return index
    return None


def task_item(block: dict[str, Any], question_index: int | None) -> dict[str, Any]:
    """Само задание: для MasteryCheck — вопрос, для остальных — содержимое блока."""
    content = _content(block)
    if block.get("component") == "MasteryCheck" and question_index is not None:
        questions = content.get("questions") if isinstance(content.get("questions"), list) else []
        if 0 <= question_index < len(questions) and isinstance(questions[question_index], dict):
            return questions[question_index]
    return content


def answer_spec(block: dict[str, Any], question_index: int | None = None) -> dict[str, Any]:
    """Как проверять ответ — те же поля и правила, что у урока (services/assessment.py)."""
    item = task_item(block, question_index)
    kind = str(item.get("type") or item.get("input_type") or "")
    numeric = kind in {"numeric", "number"} or bool(item.get("answer_unit"))
    return {
        # У «Решаю по шагам» ответ — final_answer.
        "correct": item.get("correct_answer", item.get("final_answer", "")),
        "mode": "choice" if kind == "multiple_choice" or block.get("component") == "RetrievalCheck"
        else item.get("answer_mode") if item.get("answer_mode") in {"form", "equivalent"} else None,
        "numeric": numeric and kind != "multiple_choice",
        "unit": item.get("answer_unit"),
        "accepted_units": item.get("accepted_units") if isinstance(item.get("accepted_units"), list) else None,
        "tolerance": item.get("tolerance"),
        "options": [str(option) for option in item.get("options") or []] if isinstance(item.get("options"), list) else [],
    }


def protected_items(blocks: list[dict[str, Any]], block_index: int, question_index: int | None) -> list[tuple[dict[str, Any], str, bool]]:
    """Ответы, которые реплика не должна раскрыть: текущее задание и все итоговые задания урока.

    Иначе ученик скопирует итоговый вопрос в чат на другом задании. Третий элемент —
    это ли текущее задание (только для него учитывается, что ученик уже дошёл до ответа).
    """
    items = [(answer_spec(blocks[block_index], question_index), task_text(blocks[block_index], question_index), True)]
    for index, block in enumerate(blocks):
        if not assessment_mode(block):
            continue
        questions = _content(block).get("questions") if block.get("component") == "MasteryCheck" else None
        for number in range(len(questions)) if isinstance(questions, list) else [None]:
            if (index, number) != (block_index, question_index):
                items.append((answer_spec(block, number), task_text(block, number), False))
    return items


def task_text(block: dict[str, Any], question_index: int | None = None) -> str:
    item = task_item(block, question_index)
    return str(item.get("question") or item.get("problem") or item.get("prompt") or item.get("task") or item.get("title") or "")


def authored_hints(block: dict[str, Any]) -> list[str]:
    hints = _content(block).get("hints")
    return [str(hint) for hint in hints if str(hint).strip()] if isinstance(hints, list) else []


_SUMMARY_FIELDS = ("title", "heading", "term", "definition", "text", "problem", "question", "prompt", "body", "learning_point", "callout")


def compact_block(block: dict[str, Any]) -> str:
    """Короткая выжимка блока для общего контекста урока (без правильных ответов)."""
    content = _content(block)
    parts = [str(content[key]) for key in _SUMMARY_FIELDS if isinstance(content.get(key), str) and content.get(key)]
    if isinstance(content.get("slides"), list):
        parts.extend(
            f"{slide.get('heading', '')}: {slide.get('body', '')}"
            for slide in content["slides"] if isinstance(slide, dict)
        )
    if isinstance(content.get("steps"), list):
        parts.extend(str(step.get("description", "")) for step in content["steps"] if isinstance(step, dict))
    return " | ".join(part.strip() for part in parts if part.strip())[:BLOCK_TEXT_LIMIT]


def lesson_context(blocks: list[dict[str, Any]], metadata: dict[str, Any]) -> str:
    """Кэшируемая часть: тема, цели и ход урока. Одинакова для всего класса."""
    objectives = [
        str(item.get("text")) for item in metadata.get("objectives") or []
        if isinstance(item, dict) and item.get("text")
    ]
    lines = [
        f"Тема урока: {metadata.get('topic_name') or ''}",
        f"Цели: {'; '.join(objectives) or metadata.get('learning_objectives') or ''}",
        "Ход урока:",
    ]
    lines.extend(
        f"[{index}] {block.get('component')}: {compact_block(block)}"
        for index, block in enumerate(blocks) if isinstance(block, dict)
    )
    return "\n".join(lines)[:LESSON_CONTEXT_LIMIT]


@dataclass
class TurnContext:
    """Некэшируемая часть одного хода тьютора."""

    block: dict[str, Any]
    block_index: int
    question_index: int | None
    event: str
    student_value: str | None
    check_outcome: str | None
    message: str | None
    hints_shown: list[str] = field(default_factory=list)
    recent_turns: list[dict[str, str]] = field(default_factory=list)


def turn_prompt(turn: TurnContext) -> str:
    """Что происходит сейчас: задание (с ответом — только для тьютора), попытка ученика, диалог."""
    spec = answer_spec(turn.block, turn.question_index)
    item = task_item(turn.block, turn.question_index)
    steps = _content(turn.block).get("steps")
    lines = [
        f"Текущее задание [{turn.block_index}] {turn.block.get('component')}:",
        task_text(turn.block, turn.question_index),
        f"Правильный ответ (ТОЛЬКО для тебя, ученику не называть): {json.dumps(spec['correct'], ensure_ascii=False)}"
        + (f" {spec['unit']}" if spec.get("unit") else ""),
    ]
    if item.get("explanation"):
        lines.append(f"Разбор решения (для тебя): {str(item['explanation'])[:BLOCK_TEXT_LIMIT]}")
    if isinstance(steps, list) and steps:
        lines.append("Шаги решения (для тебя): " + " → ".join(
            # WorkedExample — description; StepSolver — преобразование (hint) и строка после него (expected).
            str(step.get("description") or " ".join(filter(None, [step.get("hint"), step.get("expected")])))
            for step in steps if isinstance(step, dict)
        )[:BLOCK_TEXT_LIMIT])
    if turn.hints_shown:
        lines.append("Подсказки, которые ученик уже видел: " + " | ".join(turn.hints_shown))
    if turn.student_value:
        lines.append(f"Ответ ученика: {turn.student_value} (проверка урока: {turn.check_outcome or 'нет'})")
    if turn.recent_turns:
        lines.append("Разговор по этому заданию:")
        lines.extend(f"{item['role']}: {item['text']}" for item in turn.recent_turns[-6:])
    lines.append(f"Событие: {turn.event}")
    if turn.message:
        lines.append(f"Сообщение ученика: {turn.message}")
    return "\n".join(line for line in lines if line)
