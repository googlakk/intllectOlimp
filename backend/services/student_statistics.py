"""Read models for educator reports; saved grades are never recalculated here."""
from __future__ import annotations

from datetime import datetime
from math import isfinite
import re
from typing import Any

from lesson_contracts import flatten_lesson_document


def timestamp(value: Any) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else value if isinstance(value, str) else None


def progress_snapshot(progress: Any) -> dict[str, Any]:
    fields = ("status", "score", "mastery_status", "mastery_level", "completed_at", "started_at", "updated_at",
              "elapsed_time_sec", "time_spent_sec", "lesson_version_id", "answers", "responses",
              "response_details", "attempts_by_step", "objective_mastery", "objective_evidence")
    return {key: getattr(progress, key, None) for key in fields}


def assessed_score(snapshot: dict[str, Any]) -> float | None:
    score = snapshot.get("score")
    if (snapshot.get("status") != "completed" or snapshot.get("mastery_level") == "Не оценено"
            or isinstance(score, bool) or not isinstance(score, (int, float)) or not isfinite(score)):
        return None
    answers = _dict(snapshot.get("answers"))
    measured = any(isinstance(value, bool) for value in answers.values()) or bool(_dict(snapshot.get("responses")))
    measured = measured or any(_dict(item).get("status") in {"mastered", "needs_practice"}
                               for item in _dict(snapshot.get("objective_mastery")).values())
    if not measured:
        return None
    # A recorded grade with assessment evidence is authoritative; never regrade here.
    return min(100, max(0, float(score)))


def result_summary(snapshot: dict[str, Any] | None) -> dict[str, Any] | None:
    if not snapshot:
        return None
    return {
        "score": assessed_score(snapshot), "mastery_status": snapshot.get("mastery_status") or "not_assessed",
        "completed_at": timestamp(snapshot.get("completed_at")),
        "elapsed_time_sec": snapshot.get("elapsed_time_sec") or snapshot.get("time_spent_sec") or 0,
        "lesson_version_id": snapshot.get("lesson_version_id"),
    }


def lesson_row(topic: Any, subject: Any, published: bool, progress: Any, latest: dict[str, Any] | None,
               grade: int) -> dict[str, Any]:
    current = progress_snapshot(progress) if progress else {}
    completed = current if current.get("status") == "completed" else latest
    historical = bool(topic.archived_at is not None or subject.grade != grade or not published)
    return {
        "topic_id": topic.id, "name": topic.name, "subject_id": subject.id, "subject_name": subject.name,
        "subject_grade": subject.grade, "archived": topic.archived_at is not None, "historical": historical,
        "published": published, "has_progress": progress is not None,
        "status": current.get("status") or "not_started", "score": current.get("score"),
        "mastery_status": (completed or current).get("mastery_status") or "not_assessed",
        "completed_at": timestamp(current.get("completed_at")),
        "started_at": timestamp(current.get("started_at")), "updated_at": timestamp(current.get("updated_at")),
        "elapsed_time_sec": current.get("elapsed_time_sec") or current.get("time_spent_sec") or 0,
        "retrying": bool(completed and current.get("status") == "in_progress"),
        "last_completed": result_summary(completed),
    }


def summarize_lessons(lessons: list[dict[str, Any]]) -> dict[str, Any]:
    current = [lesson for lesson in lessons if not lesson["historical"]]
    completed = [lesson for lesson in current if lesson["last_completed"] is not None]
    scores = [lesson["last_completed"]["score"] for lesson in completed
              if lesson["last_completed"]["score"] is not None]
    published = [lesson for lesson in current if lesson["published"]]
    completed_published = sum(lesson["last_completed"] is not None for lesson in published)
    return {
        "completed": len(completed), "in_progress": sum(lesson["status"] == "in_progress" for lesson in current),
        "average_score": round(sum(scores) / len(scores), 1) if scores else None,
        "needs_practice": sum(lesson["mastery_status"] == "needs_practice" for lesson in current),
        "total_published": len(published), "completed_published": completed_published,
        "progress_percent": round(completed_published / len(published) * 100, 1) if published else 0,
    }


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def readable(value: Any) -> str:
    """Render trusted lesson criteria as text rather than dumping JSON into a teacher's view."""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "да" if value else "нет"
    if isinstance(value, (float, int)):
        return str(value)
    if isinstance(value, list):
        return "\n".join(filter(None, (readable(item) for item in value)))
    if isinstance(value, dict):
        label = next((value.get(key) for key in ("text", "label", "question", "title", "expected") if value.get(key)), None)
        return readable(label) if label is not None else "; ".join(f"{key}: {readable(item)}" for key, item in value.items())
    return ""


def expected_answer(component: str, content: dict[str, Any]) -> str | None:
    if component == "DataInvestigation" and isinstance(content.get("question"), dict):
        return expected_answer(component, content["question"])
    for key in ("correct_answer", "final_answer", "correct_prediction", "correct_segments", "correct_thesis"):
        if content.get(key) is not None:
            value = readable(content[key])
            if key == "correct_prediction":
                option = next((item for item in _items(content.get("options")) if item.get("id") == content[key]), None)
                if option:
                    value = readable(option)
            if key == "correct_thesis" and content.get("correct_evidence"):
                value += "\nДоказательства:\n" + readable(content["correct_evidence"])
            if key == "correct_answer" and content.get("answer_unit"):
                value += "\nЕдиница измерения: " + readable(content["answer_unit"])
            return value or None
    if "correct_index" in content:
        options, index = content.get("options"), content["correct_index"]
        return readable(options[index]) if isinstance(options, list) and isinstance(index, int) and 0 <= index < len(options) else None
    if component == "SortAndClassify":
        groups = {item.get("id"): readable(item) for item in _items(content.get("groups"))}
        return "\n".join(f"{readable(item)} → {groups.get(item.get('correct_group'), item.get('correct_group', ''))}"
                         for item in _items(content.get("items"))) or None
    if component in {"ArgumentMap", "ProcessBuilder"}:
        nodes = _items(content.get("nodes")) + _items(content.get("steps"))
        labels = {item.get("id"): readable(item) for item in nodes}
        return "\n".join(f"{labels.get(item.get('from'), item.get('from', ''))} → {labels.get(item.get('to'), item.get('to', ''))}"
                         for item in _items(content.get("correct_links") or content.get("correct_edges"))) or None
    if component == "HotspotInvestigation":
        required = content.get("required_hotspots") or []
        return "\n".join(readable(item) for item in _items(content.get("hotspots")) if item.get("id") in required) or None
    if component == "MisconceptionDebugger":
        errors = [readable(item) for item in _items(content.get("steps")) if item.get("is_error")]
        return "Ошибка: " + "; ".join(errors) + "\nИсправление:\n" + readable(content.get("repair_steps"))
    if component == "BranchingScenario":
        return readable(content.get("success_feedback")) or "Прийти к успешному завершению сценария."
    if component == "ChronologyLine":
        return "\n".join(f"{readable(item)} → {item.get('year', '')}" for item in _items(content.get("events"))) or None
    if component == "CauseEffectMap":
        roles = {"cause": "причина", "trigger": "повод", "consequence": "последствие", "unrelated": "не связано"}
        return "\n".join(f"{readable(item)} → {roles.get(item.get('role'), item.get('role', ''))}"
                         for item in _items(content.get("factors"))) or None
    if component == "CodeBlocksLab":
        return "Необходимые блоки: " + readable(content.get("expected_block_types"))
    if component == "FunctionExplorer":
        parts = ["Цель графика: " + readable(content["target"])] if content.get("target") else []
        prediction = _dict(content.get("prediction"))
        if prediction.get("correct_answer"):
            parts.append("Прогноз: " + readable(prediction["correct_answer"]))
        return "\n".join(parts) or readable(content.get("explanation")) or None
    if component == "TransformationMachine":
        operations = {item.get("id"): readable(item) for item in _items(content.get("operations"))}
        return " → ".join(operations.get(item, str(item)) for item in content.get("solution", [])) or None
    if component == "RuleDiscovery":
        rule = _dict(content.get("rule")); kind = rule.get("kind")
        values = content.get("challenge_inputs") or []
        multiplier, offset = rule.get("multiplier"), rule.get("offset")
        if isinstance(multiplier, (int, float)) and isinstance(offset, (int, float)):
            def output(value: float):
                base = value ** 2 if kind == "square" else abs(value) if kind == "absolute" else value
                return multiplier * base + offset
            return "\n".join(f"{value} → {output(value):g}" for value in values if isinstance(value, (int, float))) or None
    if component == "ErrorHunt":
        return "\n".join((readable(line.get("fixes", [])[line["correct_index"]])
                           if line.get("is_error") and isinstance(line.get("correct_index"), int)
                           and 0 <= line["correct_index"] < len(line.get("fixes", []))
                           else readable(line.get("text"))) for line in _items(content.get("lines"))) or None
    return readable(content.get("criteria") or content.get("rubric") or content.get("explanation")) or None


def question_prompt(component: str, content: dict[str, Any]) -> str:
    fields = ("context", "passage", "description", "prompt", "instruction", "question", "problem", "task", "claim", "start", "event")
    parts = list(dict.fromkeys(readable(content[field]) for field in fields if content.get(field)))
    if component in {"SortAndClassify", "ProcessBuilder", "ArgumentMap", "MisconceptionDebugger", "ErrorHunt"}:
        for field in ("items", "steps", "nodes", "lines"):
            if content.get(field):
                parts.append(readable(content[field]))
    for field in ("options", "thesis_options", "evidence_pool", "events", "factors"):
        if content.get(field):
            parts.append(readable(content[field]))
    if component == "FunctionExplorer" and content.get("formula"):
        parts.append("Формула: " + readable(content["formula"]))
    if component == "CauseEffectMap":
        if content.get("event"):
            parts.append("Событие: " + readable(content["event"]))
        if content.get("factors"):
            parts.append("Факторы:\n" + readable(content["factors"]))
    if component == "ChronologyLine" and content.get("events"):
        parts.append("События:\n" + readable(content["events"]))
    if component == "DataInvestigation":
        values = _dict(_dict(content.get("vega_lite_spec")).get("data")).get("values")
        if isinstance(values, list):
            parts.append("Данные графика:\n" + readable(values))
    return "\n\n".join(parts) or readable(content.get("title") or content.get("label")) or "Задание"


def _questions(blocks: list[dict[str, Any]], details: dict[str, Any]):
    # This is report-specific extraction; classification itself stays in the shared backend registry.
    from objectives import INDEPENDENT_ASSESSMENT_COMPONENTS
    for index, block in enumerate(blocks):
        component, content = block.get("component", ""), _dict(block.get("content"))
        if component not in INDEPENDENT_ASSESSMENT_COMPONENTS and component != "GuidedPractice":
            continue
        if component in {"MasteryCheck", "LearningPath"}:
            children = _items(content.get("questions") if component == "MasteryCheck" else content.get("checkpoints"))
            for question_index, child in enumerate(children):
                key = f"{index}_q{question_index}"
                raw_variant = _dict(details.get(key)).get("variant")
                variant = raw_variant if isinstance(raw_variant, str) else None
                question = _dict(child.get(variant)) if component == "LearningPath" and variant in {"support", "challenge"} else child
                yield index, question_index, key, component, content, question, variant
        else:
            yield index, None, str(index), component, content, content, None


def build_attempt_detail(snapshot: dict[str, Any], document: dict[str, Any] | None, *,
                         server_graded: bool = False) -> dict[str, Any]:
    summary = result_summary(snapshot) or {}
    result = {**summary, "status": snapshot.get("status") or "not_started", "version_available": document is not None,
              "objectives": [], "questions": []}
    details, answers = _dict(snapshot.get("response_details")), _dict(snapshot.get("answers"))
    responses, attempts = _dict(snapshot.get("responses")), _dict(snapshot.get("attempts_by_step"))
    if document is None:
        saved_keys = answers.keys() | responses.keys()
        if not server_graded:
            saved_keys |= details.keys()
        keys = [key for key in saved_keys
                if isinstance(key, str) and len(key) <= 32 and re.fullmatch(r"\d+(?:_q\d+)?", key)]
        for key in sorted(keys, key=lambda value: tuple(int(part) for part in value.split("_q"))):
            match = re.fullmatch(r"(\d+)(?:_q(\d+))?", key)
            index, question_index = int(match[1]), int(match[2]) if match[2] else None
            detail = _dict(details.get(key)); saved = answers.get(key)
            response = responses.get(key) if server_graded else detail.get("value") if isinstance(detail.get("value"), str) else responses.get(key)
            outcome = "correct" if saved is True else "incorrect" if saved is False else None
            result["questions"].append({
                "key": key, "block_index": index, "question_index": question_index, "component": "Unknown",
                "stage": "unknown", "prompt": "Версия задания недоступна",
                "response": response if isinstance(response, str) else None,
                "outcome": outcome if server_graded else detail.get("outcome") or outcome,
                "expected": None, "explanation": None, "attempts": attempts.get(key),
                "variant": detail.get("variant") if isinstance(detail.get("variant"), str) else None,
            })
        return result
    mastery = _dict(snapshot.get("objective_mastery"))
    for objective in _items(document.get("objectives")):
        identifier = objective.get("id")
        measured = _dict(mastery.get(identifier))
        result["objectives"].append({"id": str(identifier or ""), "text": readable(objective),
                                     "status": measured.get("status") or "not_assessed", "score": measured.get("score")})
    blocks = flatten_lesson_document(document)
    server_outcomes = {}
    if server_graded and snapshot.get("status") == "completed":
        from services.assessment import assessment_outcomes
        server_outcomes = assessment_outcomes(blocks, responses)
    for index, question_index, key, component, content, question, variant in _questions(blocks, details):
        detail = _dict(details.get(key))
        response = responses.get(key) if server_graded else detail.get("value") if isinstance(detail.get("value"), str) else responses.get(key)
        saved = answers.get(key)
        checked_outcome = "correct" if saved is True else "incorrect" if saved is False else None
        # Only distinguish the reason for a stored failure; never replace its saved grade.
        if saved is False and server_outcomes.get(key) == "wrong_unit":
            checked_outcome = "wrong_unit"
        outcome = checked_outcome if server_graded else detail.get("outcome") or checked_outcome
        stage = content.get("evidence_stage")
        prompt = question_prompt(component, question)
        if component == "LearningPath" and variant not in {"support", "challenge"}:
            expected = None
            prompt += " · Вариант задания не сохранён"
        else:
            expected = expected_answer(component, question)
        result["questions"].append({
            "key": key, "block_index": index, "question_index": question_index, "component": component,
            "stage": stage if stage in {"diagnostic", "practice", "assessment"} else "assessment" if component == "MasteryCheck" else "practice",
            "prompt": prompt, "response": response if isinstance(response, str) else None,
            "outcome": outcome, "expected": expected,
            "explanation": readable(question.get("explanation") or question.get("solution") or question.get("model_reasoning") or content.get("explanation")) or None,
            "attempts": attempts.get(key), "variant": variant,
        })
    return result
