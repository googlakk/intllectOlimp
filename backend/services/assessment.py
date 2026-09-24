"""Deterministic, server-side grading for self-check assessments."""
from __future__ import annotations
from decimal import Decimal, InvalidOperation
from typing import Any


def equal_answer(value: Any, expected: Any) -> bool:
    actual = str(value).strip().casefold().replace(",", ".")
    target = str(expected).strip().casefold().replace(",", ".")
    if not actual or not target:
        return False
    try:
        left, right = Decimal(actual), Decimal(target)
        return left.is_finite() and right.is_finite() and left == right
    except InvalidOperation:
        return " ".join(actual.split()) == " ".join(target.split())


def grade_assessment(blocks: list[dict], responses: dict[str, str]) -> tuple[dict[str, bool], int]:
    answers: dict[str, bool] = {}
    for index, block in enumerate(blocks):
        content = block.get("content") or {}
        if block.get("component") == "MasteryCheck":
            for question_index, question in enumerate(content.get("questions") or []):
                key = f"{index}_q{question_index}"
                answers[key] = equal_answer(responses.get(key, ""), question.get("correct_answer", ""))
        elif block.get("component") in {"RetrievalCheck", "IndependentProblem"}:
            key = str(index)
            answers[key] = equal_answer(responses.get(key, ""), content.get("correct_answer", ""))
    score = round(100 * sum(answers.values()) / len(answers)) if answers else 0
    return answers, score
