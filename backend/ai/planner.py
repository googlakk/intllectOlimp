"""Deterministic lesson planning before the LLM writes content.

The model should fill a pedagogical plan, not invent lesson architecture from
scratch. This module turns KTP topic fields into a compact, serialisable
contract that is stable enough to test and strict enough to guide generation.
"""

from __future__ import annotations

from typing import Any

from objectives import decompose_objectives

Volume = str
LessonShape = str


MATH_WORDS = ("математ", "алгебр", "геометр", "арифмет", "статист")
SCIENCE_WORDS = ("физик", "хими", "биолог", "географ", "естествозн", "астроном")
HUMANITIES_WORDS = ("литератур", "истори", "тарых", "адабият", "обществозн", "право")
LANGUAGE_WORDS = ("русский язык", "кыргыз тили", "киргизский язык", "английск", "граммат")
COMPUTING_WORDS = ("информат", "программ", "робот", "компьютер", "алгоритм")

HEAVY_COMPONENTS = {
    "ProcessBuilder", "ArgumentMap", "BranchingScenario", "PredictionLab",
    "DataInvestigation", "PhysicsSandbox", "HotspotInvestigation", "CodeBlocksLab",
}


def _normalise(value: str | None) -> str:
    return (value or "").casefold().replace("ё", "е")


def subject_family(subject_name: str) -> str:
    text = _normalise(subject_name)
    if any(word in text for word in MATH_WORDS):
        return "math"
    if any(word in text for word in COMPUTING_WORDS):
        return "computing"
    if any(word in text for word in SCIENCE_WORDS):
        return "science"
    if any(word in text for word in LANGUAGE_WORDS):
        return "language"
    if any(word in text for word in HUMANITIES_WORDS):
        return "humanities"
    return "general"


def infer_learning_focus(
    *,
    subject_name: str,
    topic_name: str,
    learning_objectives: str | None,
    skills: list[str] | None,
    lesson_type: str | None,
) -> str:
    if lesson_type == "assessment":
        return "assessment"
    if lesson_type == "project":
        return "project"
    family = subject_family(subject_name)
    text = _normalise(" ".join([topic_name, learning_objectives or "", " ".join(skills or [])]))
    if family in {"math", "computing"}:
        if any(word in text for word in ("реш", "вычисл", "алгоритм", "постро", "примен", "делител", "кратн", "множител", "нод", "нок")):
            return "procedure"
        return "concept"
    if any(word in text for word in ("процесс", "цикл", "строение", "система", "явление", "эксперимент", "опыт")):
        return "process"
    if family in {"humanities", "language"} and any(word in text for word in ("источник", "документ", "карта", "текст", "цитат", "доказ", "аргумент")):
        return "source_analysis" if family == "humanities" else "argumentation"
    if any(word in text for word in ("реш", "вычисл", "алгоритм", "постро", "примен")):
        return "procedure"
    if family == "science":
        return "process"
    if family in {"humanities", "language"}:
        return "argumentation"
    return "concept"


def infer_volume(hours: int | None, objective_count: int, raw_objectives: str | None) -> Volume:
    hours = max(int(hours or 1), 0)
    raw_len = len((raw_objectives or "").strip())
    if hours >= 4 or objective_count >= 5:
        return "unit"
    if hours >= 3 or objective_count >= 3 or raw_len > 420:
        return "extended"
    if hours <= 1 and objective_count <= 1:
        return "micro"
    return "standard"


def infer_complexity(volume: Volume, objective_count: int, skills: list[str] | None, resources: str | None) -> str:
    signal_count = objective_count + len(skills or [])
    if volume in {"extended", "unit"} or signal_count >= 5 or len(resources or "") > 180:
        return "high"
    if volume == "standard" or signal_count >= 2:
        return "medium"
    return "low"


def select_lesson_shape(volume: Volume, learning_focus: str, lesson_type: str | None) -> LessonShape:
    if lesson_type == "assessment":
        return "assessment_only"
    if lesson_type == "review":
        return "review_practice"
    if lesson_type == "reflection":
        return "error_analysis"
    if lesson_type == "project":
        return "project_or_practical"
    if volume == "unit":
        return "unit_part"
    if learning_focus == "process":
        return "process_inquiry"
    if learning_focus in {"source_analysis", "argumentation"}:
        return "source_argument"
    if learning_focus == "procedure":
        return "procedure_mastery"
    if volume == "micro":
        return "micro_intro"
    if volume == "extended":
        return "extended_concept"
    return "standard_skill"


def block_budget(volume: Volume, shape: LessonShape, objective_count: int) -> dict[str, int]:
    if shape == "assessment_only":
        return {"min": max(3, objective_count + 2), "max": max(6, objective_count * 3 + 2), "heavy_max": 1}
    if shape == "project_or_practical":
        return {"min": 8, "max": 12, "heavy_max": 2}
    if shape == "unit_part":
        return {"min": 10, "max": 16, "heavy_max": 3}
    if volume == "micro":
        return {"min": 5, "max": 7, "heavy_max": 1}
    if volume == "extended":
        return {"min": 12, "max": 18, "heavy_max": 3}
    return {"min": 8, "max": 11, "heavy_max": 2}


def media_policy(learning_focus: str, volume: Volume) -> str:
    if learning_focus in {"process", "concept"} or volume in {"extended", "unit"}:
        return "suggested"
    return "optional"


def _objective_ids(objectives: list[dict[str, Any]]) -> list[str]:
    return [item["id"] for item in objectives] or ["obj-general"]


def _step(
    role: str,
    stage: str | None,
    objective_ids: list[str],
    allowed: list[str],
    action: str,
    *,
    required: bool = True,
) -> dict[str, Any]:
    return {
        "role": role,
        "evidence_stage": stage,
        "objective_ids": objective_ids,
        "allowed_components": allowed,
        "cognitive_action": action,
        "required": required,
    }


def build_component_plan(shape: LessonShape, objectives: list[dict[str, Any]], focus: str) -> list[dict[str, Any]]:
    ids = _objective_ids(objectives)
    plan: list[dict[str, Any]] = []

    if shape == "assessment_only":
        for objective_id in ids:
            plan.append(_step("diagnose", "diagnostic", [objective_id], ["RetrievalCheck"], "Вспомнить ключевой факт или способ"))
        plan.append(_step("assess", "assessment", ids, ["MasteryCheck"], "Показать итоговое освоение каждой цели"))
        return plan

    if shape in {"review_practice", "error_analysis"}:
        for objective_id in ids:
            plan.extend([
                _step("diagnose", "diagnostic", [objective_id], ["RetrievalCheck"], "Выявить пробел в изученном материале"),
                _step("explain", "explanation", [objective_id], ["ShortExplanation"], "Вспомнить правило и объяснить типичную ошибку"),
                _step("model", "explanation", [objective_id], ["WorkedExample"], "Разобрать правильный способ решения"),
                _step("practice", "practice", [objective_id], ["MisconceptionDebugger", "GuidedPractice"], "Исправить ошибку и закрепить способ"),
                _step("apply", "practice", [objective_id], ["IndependentProblem"], "Самостоятельно проверить исправленный способ"),
            ])
        plan.append(_step("assess", "assessment", ids, ["MasteryCheck"], "Проверить устранение пробелов отдельным вопросом на каждую цель"))
        return plan

    if shape == "project_or_practical":
        plan.extend([
            _step("explain", "explanation", ids, ["ShortExplanation", "Presentation"], "Понять критерии результата"),
            _step("model", "explanation", ids, ["WorkedExample", "GeneratedMedia"], "Увидеть образец выполнения", required=False),
            _step("practice", "practice", ids, ["ProcessBuilder", "BranchingScenario", "GuidedPractice"], "Спланировать и выполнить шаги"),
            _step("apply", "practice", ids, ["IndependentProblem", "ArgumentBuilder"], "Создать практический результат"),
            _step("assess", "assessment", ids, ["MasteryCheck"], "Проверить результат по критериям"),
            _step("reflect", None, [], ["Reflection"], "Оценить процесс работы"),
        ])
        return plan

    for objective_id in ids:
        plan.append(_step("diagnose", "diagnostic", [objective_id], ["RetrievalCheck"], "Вспомнить предварительное знание"))

    # A concise slide sequence is the shared visual spine. Simulations and
    # generated media may clarify it, but never become the only explanation.
    explain_allowed = ["Presentation"]
    for objective_id in ids:
        plan.append(_step("explain", "explanation", [objective_id], explain_allowed, "Понять новое понятие или явление"))
        if shape != "procedure_mastery":
            plan.append(_step("model", "explanation", [objective_id], ["WorkedExample"], "Разобрать пример применения"))
        if shape == "process_inquiry":
            plan.append(_step("practice", "practice", [objective_id], ["PredictionLab", "ProcessBuilder", "HotspotInvestigation", "DataInvestigation"], "Исследовать процесс или данные"))
        elif shape == "source_argument":
            plan.append(_step("practice", "practice", [objective_id], ["TextEvidencePicker", "ArgumentMap", "BranchingScenario"], "Найти доказательство и построить вывод"))
        elif shape == "procedure_mastery":
            plan.append(_step("model", "explanation", [objective_id], ["WorkedExample"], "Разобрать способ действия"))
            plan.append(_step("practice", "practice", [objective_id], ["GuidedPractice", "MisconceptionDebugger", "SortAndClassify", "ProcessBuilder", "CodeBlocksLab"], "Применить способ и исправить ошибку"))
        else:
            plan.append(_step("practice", "practice", [objective_id], ["GuidedPractice", "SortAndClassify", "ProcessBuilder", "HotspotInvestigation"], "Активно обработать материал"))

    if shape in {"extended_concept", "process_inquiry", "source_argument"} or len(ids) > 1:
        plan.append(_step("apply", "practice", ids, ["IndependentProblem", "ArgumentBuilder", "DataInvestigation", "ProcessBuilder"], "Связать цели и перенести знания"))
    else:
        plan.append(_step("apply", "practice", ids, ["IndependentProblem"], "Самостоятельно применить материал"))
    plan.append(_step("assess", "assessment", ids, ["MasteryCheck"], "Проверить каждую цель отдельным вопросом"))
    plan.append(_step("reflect", None, [], ["Reflection"], "Осознать уверенность и следующий шаг"))
    return plan


def build_topic_contract(
    *,
    topic_name: str,
    subject_name: str,
    learning_objectives: str | None,
    skills: list[str] | None,
    resources: str | None,
    grade: int | None,
    hours: int | None,
    lesson_type: str | None,
    content_language: str = "ru",
) -> dict[str, Any]:
    objectives = decompose_objectives(learning_objectives)
    volume = infer_volume(hours, len(objectives), learning_objectives)
    focus = infer_learning_focus(
        subject_name=subject_name,
        topic_name=topic_name,
        learning_objectives=learning_objectives,
        skills=skills,
        lesson_type=lesson_type,
    )
    shape = select_lesson_shape(volume, focus, lesson_type)
    budget = block_budget(volume, shape, len(objectives))
    contract = {
        "topic_name": topic_name,
        "subject_name": subject_name,
        "grade": grade,
        "hours": max(int(hours or 1), 0),
        "lesson_type": lesson_type or "study",
        "content_language": content_language,
        "volume": volume,
        "complexity": infer_complexity(volume, len(objectives), skills, resources),
        "objective_count": len(objectives),
        "learning_focus": focus,
        "lesson_shape": shape,
        "block_budget": budget,
        "media_policy": media_policy(focus, volume),
    }
    if shape == "unit_part":
        contract["module_part_index"] = 1
        contract["module_total_parts"] = max(2, min(4, (max(int(hours or 4), 4) + 1) // 2))
        contract["suggested_next_parts"] = [
            "Продолжить следующие цели темы отдельными частями модуля.",
            "Добавить повторение и итоговую работу после всех частей.",
        ]
    return {
        "topic_contract": contract,
        "component_plan": build_component_plan(shape, objectives, focus),
    }


def heavy_component_count(blocks: list[dict[str, Any]]) -> int:
    return sum(1 for block in blocks if block.get("component") in HEAVY_COMPONENTS)
