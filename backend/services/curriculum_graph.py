"""Curriculum intelligence, skill graph construction and student warp gates."""

from __future__ import annotations

import hashlib
import re
from copy import deepcopy
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from time import monotonic
from typing import Any, Iterable
from types import SimpleNamespace

from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from errors import ApplicationError
from objectives import decompose_objectives
from topic_semantics import CONSOLIDATION_TYPES, ambiguous_lesson_name
from models import (
    GeneratedLesson,
    Progress,
    Section,
    Skill,
    Student,
    StudentSkillMastery,
    StudentTopicAccess,
    Subject,
    Topic,
    TopicEdge,
    TopicSkill,
    WarpGateEvent,
)


class CurriculumGraphError(ApplicationError):
    pass


CURRICULUM_MAP_CACHE_TTL_SEC = 30
_curriculum_map_cache: dict[tuple[int, int | None], tuple[float, dict[str, Any]]] = {}


def clear_curriculum_map_cache(student_id: int | None = None, subject_id: int | None = None) -> None:
    if student_id is None:
        _curriculum_map_cache.clear()
        return
    for key in [
        cache_key
        for cache_key in _curriculum_map_cache
        if cache_key[0] == student_id and (subject_id is None or cache_key[1] == subject_id)
    ]:
        _curriculum_map_cache.pop(key, None)


def cached_curriculum_map(student_id: int, subject_id: int | None) -> dict[str, Any] | None:
    cached = _curriculum_map_cache.get((student_id, subject_id))
    if cached is None:
        return None
    expires_at, payload = cached
    if expires_at <= monotonic():
        _curriculum_map_cache.pop((student_id, subject_id), None)
        return None
    return deepcopy(payload)


def remember_curriculum_map(student_id: int, subject_id: int | None, payload: dict[str, Any]) -> None:
    _curriculum_map_cache[(student_id, subject_id)] = (
        monotonic() + CURRICULUM_MAP_CACHE_TTL_SEC,
        deepcopy(payload),
    )


@dataclass(frozen=True)
class SubjectProfile:
    family: str
    action: str
    practice: str
    transferable_skill: str


SUBJECT_PROFILES: tuple[tuple[tuple[str, ...], SubjectProfile], ...] = (
    (("математ", "алгебр", "геометр"), SubjectProfile("mathematics", "объяснять математическую идею", "решать задачи и обосновывать способ решения", "Логическое рассуждение")),
    (("физик",), SubjectProfile("physics", "объяснять физическую закономерность", "применять модель к наблюдаемой ситуации", "Анализ причин и следствий")),
    (("хими",), SubjectProfile("chemistry", "объяснять свойства и превращения веществ", "интерпретировать реакцию или эксперимент", "Анализ причин и следствий")),
    (("биолог",), SubjectProfile("biology", "объяснять строение, функцию или процесс", "связывать наблюдение с биологической моделью", "Системное мышление")),
    (("географ",), SubjectProfile("geography", "объяснять пространственную закономерность", "анализировать карту, данные или географический процесс", "Работа с данными")),
    (("информат",), SubjectProfile("informatics", "объяснять алгоритм или информационный процесс", "создавать и проверять алгоритмическое решение", "Алгоритмическое мышление")),
    (("истори", "обществ"), SubjectProfile("social_sciences", "объяснять событие, явление или общественный процесс", "аргументировать вывод с опорой на источники", "Анализ доказательств")),
    (("литератур", "русск", "кыргыз", "язык"), SubjectProfile("language_arts", "интерпретировать текст и ключевые понятия", "подтверждать вывод фрагментами и языковыми средствами", "Аргументация на основе текста")),
)
DEFAULT_PROFILE = SubjectProfile("general", "объяснять основные понятия", "применять знания в новой ситуации", "Самостоятельное рассуждение")
GENERIC_TRANSFER_SKILLS = {
    profile.transferable_skill.casefold()
    for _markers, profile in SUBJECT_PROFILES
} | {DEFAULT_PROFILE.transferable_skill.casefold()}
CROSS_DOMAIN_SKILL_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Анализ структуры и взаимосвязей", ("структур", "сюжет", "композиц", "выражен", "функц", "график")),
    ("Сравнение и классификация", ("сравнен", "классификац", "виды", "типы", "фигур", "персонаж", "геро")),
    ("Интерпретация данных и источников", ("данн", "таблиц", "источник", "документ", "диаграм", "статист")),
    ("Причинно-следственное объяснение", ("причин", "следств", "истори", "развити", "изменени", "преобразован")),
)
CONTROLLED_CROSS_SKILLS = {name.casefold() for name, _markers in CROSS_DOMAIN_SKILL_RULES}
CROSS_SKILL_FAMILY_PAIRS: dict[str, set[frozenset[str]]] = {
    "анализ структуры и взаимосвязей": {
        frozenset(("mathematics", "informatics")),
        frozenset(("language_arts", "social_sciences")),
        frozenset(("biology", "chemistry")),
        frozenset(("biology", "geography")),
    },
    "сравнение и классификация": {
        frozenset(("biology", "chemistry")),
        frozenset(("biology", "geography")),
        frozenset(("chemistry", "physics")),
        frozenset(("language_arts", "social_sciences")),
    },
    "интерпретация данных и источников": {
        frozenset(("mathematics", "physics")),
        frozenset(("mathematics", "geography")),
        frozenset(("mathematics", "social_sciences")),
        frozenset(("informatics", "mathematics")),
        frozenset(("geography", "social_sciences")),
        frozenset(("language_arts", "social_sciences")),
    },
    "причинно следственное объяснение": {
        frozenset(("physics", "chemistry")),
        frozenset(("biology", "chemistry")),
        frozenset(("biology", "geography")),
        frozenset(("geography", "social_sciences")),
        frozenset(("language_arts", "social_sciences")),
    },
}


def normalize_text(value: str) -> str:
    return re.sub(r"[^0-9a-zа-яё]+", " ", value.casefold()).strip()


def subject_profile(subject_name: str) -> SubjectProfile:
    normalized = normalize_text(subject_name).replace("ё", "е")
    for markers, profile in SUBJECT_PROFILES:
        if any(marker in normalized for marker in markers):
            return profile
    return DEFAULT_PROFILE


def canonical_skill_key(subject_family: str, name: str) -> str:
    normalized = normalize_text(name).replace("ё", "е")
    digest = hashlib.sha1(f"{subject_family}:{normalized}".encode("utf-8")).hexdigest()[:12]
    return f"{subject_family}:{digest}"


def supports_cross_subject_transfer(skill_name: str, source_subject: str, target_subject: str) -> bool:
    """Require an explicit pedagogical bridge, not just a shared generic label."""
    source_family = subject_profile(source_subject).family
    target_family = subject_profile(target_subject).family
    if source_family == target_family:
        return False
    allowed_pairs = CROSS_SKILL_FAMILY_PAIRS.get(normalize_text(skill_name), set())
    return frozenset((source_family, target_family)) in allowed_pairs


def infer_topic_contract(
    *,
    subject_name: str,
    grade: int,
    topic_name: str,
    lesson_type: str = "study",
    learning_objectives: str | None = None,
    skills: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Recover a reviewable minimum contract when a KTP only has topic/hours."""
    profile = subject_profile(subject_name)
    supplied_skills = [str(item).strip() for item in (skills or []) if str(item).strip()]
    objective = (learning_objectives or "").strip()
    inferred = not bool(objective)
    if inferred and lesson_type not in CONSOLIDATION_TYPES:
        objective = (
            f"{profile.action.capitalize()} по теме «{topic_name}»; "
            f"{profile.practice} на уровне {grade} класса."
        )

    if inferred and lesson_type not in CONSOLIDATION_TYPES and profile.family == "mathematics":
        name = normalize_text(topic_name)
        concrete_goals = (
            (("кубические корни", "кубы и"), "Вычислять кубы чисел; Находить кубические корни из полных кубов"),
            (("квадратные корни", "квадраты и"), "Вычислять квадраты чисел; Находить квадратные корни из полных квадратов"),
            (("неправильные дроби", "смешанные числа"), "Преобразовывать неправильную дробь в смешанное число; Преобразовывать смешанное число в неправильную дробь"),
            (("сравнение дробей", "сравнивать дроби"), "Сравнивать дроби с одинаковыми знаменателями; Приводить дроби к общему знаменателю для сравнения"),
            (("свойства степеней",), "Применять правило произведения степеней; Применять правило частного степеней; Возводить степень в степень"),
        )
        for markers, goals in concrete_goals:
            if any(marker in name for marker in markers):
                objective = goals
                break

    # Skills are observable objectives, never the title of an administrative lesson.
    supplied_skills = [item for item in supplied_skills if not normalize_text(item).startswith("освоение темы")]
    inferred_skills = list(supplied_skills)
    if lesson_type not in {"assessment", "review", "reflection"}:
        inferred_skills.extend(item["text"] for item in decompose_objectives(objective))

    deduplicated_skills: list[str] = []
    seen_skills: set[str] = set()
    for skill in inferred_skills:
        normalized = normalize_text(skill)
        if normalized and normalized not in seen_skills:
            seen_skills.add(normalized)
            deduplicated_skills.append(skill)

    return {
        "learning_objectives": objective,
        "skills": deduplicated_skills,
        "objective_source": "inferred" if inferred else "ktp",
        "objective_confidence": 0.72 if inferred else 1.0,
        "subject_family": profile.family,
    }


def enrich_ktp_draft(draft: dict[str, Any]) -> dict[str, Any]:
    """Attach inferred objectives/skills before the teacher reviews an import."""
    subject_name = str(draft.get("subject_name") or "Предмет")
    grade = int(draft.get("grade") or 7)
    inferred_count = 0
    for section in draft.get("sections") or []:
        for topic in section.get("topics") or []:
            contract = infer_topic_contract(
                subject_name=subject_name,
                grade=grade,
                topic_name=str(topic.get("name") or "Тема"),
                lesson_type=str(topic.get("lesson_type") or "study"),
                learning_objectives=topic.get("learning_objectives"),
                skills=topic.get("skills"),
            )
            if contract["objective_source"] == "inferred":
                inferred_count += 1
                topic["learning_objectives"] = contract["learning_objectives"]
            topic["skills"] = contract["skills"]
            topic["objective_source"] = contract["objective_source"]
            topic["objective_confidence"] = contract["objective_confidence"]
            topic["review_required"] = bool(topic.get("review_required")) or ambiguous_lesson_name(str(topic.get("name") or ""))
            if topic.get("lesson_type") in CONSOLIDATION_TYPES and not topic.get("learning_objectives"):
                topic["review_required"] = True
    draft["inferred_objectives_count"] = inferred_count
    if inferred_count:
        draft.setdefault("warnings", []).append(
            f"Для {inferred_count} тем цели восстановлены автоматически. Проверьте их перед сохранением."
        )
    return draft


async def _upsert_skill(
    db: AsyncSession,
    *,
    name: str,
    family: str,
    grade: int,
) -> int:
    key = canonical_skill_key(family, name)
    statement = (
        insert(Skill)
        .values(
            canonical_key=key,
            name=name,
            normalized_name=normalize_text(name),
            subject_family=family,
            grade_min=max(1, grade - 1),
            grade_max=min(12, grade + 2),
            metadata_json={},
        )
        .on_conflict_do_update(
            index_elements=[Skill.canonical_key],
            set_={"name": name, "updated_at": datetime.now(timezone.utc)},
        )
        .returning(Skill.id)
    )
    skill_id = await db.scalar(statement)
    if skill_id is None:
        raise CurriculumGraphError(status_code=500, detail="Не удалось сохранить навык")
    return int(skill_id)


def objective_id_for_skill(objectives: str | None, skill_name: str) -> str | None:
    """Only a concrete, directly assessed objective can certify a skill."""
    normalized = normalize_text(skill_name)
    generic = {normalize_text(name) for name in GENERIC_TRANSFER_SKILLS | CONTROLLED_CROSS_SKILLS}
    generic.update({"логическое мышление", "критическое мышление", "сравнение", "коммуникация"})
    if normalized in generic or normalized.startswith("освоение темы"):
        return None
    return next((item["id"] for item in decompose_objectives(objectives)
                 if normalize_text(item["text"]) == normalized), None)


async def rebuild_subject_graph(subject_id: int, db: AsyncSession) -> dict[str, int]:
    """Build deterministic passports and explainable links for one subject."""
    subject = await db.get(Subject, subject_id)
    if subject is None:
        raise CurriculumGraphError(status_code=404, detail="Предмет не найден")

    rows = (
        await db.execute(
            select(Topic, Section)
            .join(Section, Section.id == Topic.section_id)
            .where(Section.subject_id == subject_id, Topic.archived_at.is_(None))
            .order_by(Section.sort_order, Topic.sort_order, Topic.id)
        )
    ).all()
    topics = [topic for topic, _section in rows]
    if not topics:
        return {"topics": 0, "skills": 0, "edges": 0}

    topic_ids = [topic.id for topic in topics]
    await db.execute(delete(TopicSkill).where(TopicSkill.topic_id.in_(topic_ids), TopicSkill.source == "inferred"))
    await db.execute(
        delete(TopicEdge).where(
            TopicEdge.source == "inferred",
            (TopicEdge.from_topic_id.in_(topic_ids)) | (TopicEdge.to_topic_id.in_(topic_ids)),
        )
    )

    family = subject_profile(subject.name).family
    contracts: dict[int, dict[str, Any]] = {}
    skill_values_by_key: dict[str, dict[str, Any]] = {}
    topic_skill_keys: dict[int, list[tuple[str, str]]] = defaultdict(list)
    for topic in topics:
        contract = infer_topic_contract(
            subject_name=subject.name,
            grade=subject.grade,
            topic_name=topic.name,
            lesson_type=topic.lesson_type,
            learning_objectives=topic.learning_objectives,
            skills=topic.skills,
        )
        if not (topic.learning_objectives or "").strip():
            topic.learning_objectives = contract["learning_objectives"]
        topic.skills = contract["skills"]
        contracts[topic.id] = contract
        for skill_name in ([] if topic.lesson_type in CONSOLIDATION_TYPES else contract["skills"]):
            skill_family = "transferable" if skill_name.casefold() in GENERIC_TRANSFER_SKILLS | CONTROLLED_CROSS_SKILLS else family
            key = canonical_skill_key(skill_family, skill_name)
            skill_values_by_key[key] = {
                "canonical_key": key,
                "name": skill_name,
                "normalized_name": normalize_text(skill_name),
                "subject_family": skill_family,
                "grade_min": max(1, subject.grade - 1),
                "grade_max": min(12, subject.grade + 2),
                "metadata_json": {},
            }
            topic_skill_keys[topic.id].append((key, skill_name))

    # Explicitly authored links are authoritative and may not be present in Topic.skills.
    authored_rows = (await db.execute(
        select(TopicSkill, Skill).join(Skill, Skill.id == TopicSkill.skill_id)
        .where(TopicSkill.topic_id.in_(topic_ids), TopicSkill.role == "outcome", TopicSkill.source != "inferred")
    )).all()
    for link, skill in authored_rows:
        pair = (skill.canonical_key, skill.name)
        if pair not in topic_skill_keys[link.topic_id]:
            topic_skill_keys[link.topic_id].append(pair)
        skill_values_by_key[skill.canonical_key] = {
            "canonical_key": skill.canonical_key, "name": skill.name,
            "normalized_name": skill.normalized_name, "subject_family": skill.subject_family,
            "grade_min": skill.grade_min, "grade_max": skill.grade_max,
            "metadata_json": skill.metadata_json or {},
        }

    # Reviews and assessments reuse the source skill identities and objective text.
    by_id = {topic.id: topic for topic in topics}
    for topic in topics:
        if topic.lesson_type not in {"review", "assessment", "reflection"}:
            continue
        covered = list(getattr(topic, "covered_topic_ids", None) or [])
        linked = list(dict.fromkeys(pair for source_id in covered for pair in topic_skill_keys.get(source_id, [])))
        topic_skill_keys[topic.id] = linked
        topic.skills = [name for _key, name in linked]
        topic.review_required = bool(topic.review_required) or not bool(linked)
        # Empty/imported generic goals can be repaired; authored goals are preserved.
        old_study_goal = infer_topic_contract(subject_name=subject.name, grade=subject.grade, topic_name=topic.name)["learning_objectives"]
        old_assessment_goal = (f"Продемонстрировать освоение темы «{topic.name}»: корректно выполнить "
                               "самостоятельные задания и объяснить ход решения или вывода.")
        if not topic.learning_objectives or topic.learning_objectives in {old_study_goal, old_assessment_goal}:
            topic.learning_objectives = "; ".join(topic.skills)
    if not skill_values_by_key:
        clear_curriculum_map_cache()
        return {"topics": len(topics), "skills": 0, "edges": 0}

    skill_insert = insert(Skill).values(list(skill_values_by_key.values()))
    skill_result = await db.execute(
        skill_insert.on_conflict_do_update(
            index_elements=[Skill.canonical_key],
            set_={"name": skill_insert.excluded.name, "updated_at": datetime.now(timezone.utc)},
        ).returning(Skill.canonical_key, Skill.id)
    )
    skill_id_by_key = {key: int(skill_id) for key, skill_id in skill_result.all()}
    unique_skill_ids = set(skill_id_by_key.values())
    skill_topics: dict[int, list[int]] = defaultdict(list)
    concept_skill_by_topic: dict[int, int] = {}
    topic_skill_values: dict[tuple[int, int, str], dict[str, Any]] = {}
    for topic in topics:
        contract = contracts[topic.id]
        for key, skill_name in topic_skill_keys[topic.id]:
            skill_id = skill_id_by_key[key]
            if topic.id not in skill_topics[skill_id]:
                skill_topics[skill_id].append(topic.id)
            topic_skill_values[(topic.id, skill_id, "outcome")] = {
                "topic_id": topic.id,
                "skill_id": skill_id,
                "role": "outcome",
                "weight": 1.0,
                "mastery_threshold": 0.8,
                "source": "inferred",
                "confidence": contract["objective_confidence"],
                "objective_id": objective_id_for_skill(topic.learning_objectives, skill_name),
            }
            if skill_name.casefold() not in GENERIC_TRANSFER_SKILLS | CONTROLLED_CROSS_SKILLS:
                concept_skill_by_topic[topic.id] = skill_id

    edge_values: dict[tuple[int, int, str], dict[str, Any]] = {}
    for previous_topic, topic in zip(topics, topics[1:]):
        previous_concept_skill = concept_skill_by_topic.get(previous_topic.id)
        if previous_concept_skill is not None:
            topic_skill_values[(topic.id, previous_concept_skill, "prerequisite")] = {
                "topic_id": topic.id,
                "skill_id": previous_concept_skill,
                "role": "prerequisite",
                "weight": 1.0,
                "mastery_threshold": 0.8,
                "source": "inferred",
                "confidence": 0.9,
                "objective_id": None,
            }
        edge_values[(previous_topic.id, topic.id, "progression")] = {
            "from_topic_id": previous_topic.id,
            "to_topic_id": topic.id,
            "relation": "progression",
            "required_mastery": 0.8,
            "confidence": 0.9,
            "rationale": f"Освоение темы «{previous_topic.name}» подготавливает к теме «{topic.name}».",
            "source": "inferred",
        }

    if topic_skill_values:
        topic_skill_insert = insert(TopicSkill).values(list(topic_skill_values.values()))
        await db.execute(
            topic_skill_insert.on_conflict_do_nothing(
                index_elements=[TopicSkill.topic_id, TopicSkill.skill_id, TopicSkill.role],
            )
        )

    # A transferable skill links only nearby opportunities, avoiding a dense O(n²) graph.
    topic_by_id = {topic.id: topic for topic in topics}
    existing_pairs = {(topics[index].id, topics[index + 1].id) for index in range(len(topics) - 1)}
    transfer_edges = 0
    transfer_pairs: set[tuple[int, int]] = set()
    for skill_id, linked_topic_ids in skill_topics.items():
        # Very common competencies remain visible in the passport but are too
        # broad to justify opening a concrete topic on their own.
        frequency_limit = max(4, round(len(topics) * 0.15))
        if (
            skill_id in concept_skill_by_topic.values()
            or len(linked_topic_ids) < 2
            or len(linked_topic_ids) > frequency_limit
        ):
            continue
        for source_id, target_id in zip(linked_topic_ids, linked_topic_ids[1:]):
            if (source_id, target_id) in existing_pairs or (source_id, target_id) in transfer_pairs:
                continue
            transfer_pairs.add((source_id, target_id))
            source_topic, target_topic = topic_by_id[source_id], topic_by_id[target_id]
            edge_values[(source_id, target_id, "transfer")] = {
                "from_topic_id": source_id,
                "to_topic_id": target_id,
                "relation": "transfer",
                "required_mastery": 0.8,
                "confidence": 0.78,
                "rationale": f"Навык из темы «{source_topic.name}» переносится в тему «{target_topic.name}».",
                "source": "inferred",
            }
            transfer_edges += 1

    cross_edges = 0
    all_transfer_rows = (
        await db.execute(
            select(TopicSkill, Topic, Section, Subject, Skill)
            .join(Topic, Topic.id == TopicSkill.topic_id)
            .join(Section, Section.id == Topic.section_id)
            .join(Subject, Subject.id == Section.subject_id)
            .join(Skill, Skill.id == TopicSkill.skill_id)
            .where(TopicSkill.role == "outcome", Skill.subject_family == "transferable", Topic.archived_at.is_(None))
            .order_by(Subject.grade, Subject.id, Section.sort_order, Topic.sort_order)
        )
    ).all()
    by_skill: dict[int, list[tuple[Topic, Subject]]] = defaultdict(list)
    cross_skill_names: dict[int, str] = {}
    for link, topic, _section, linked_subject, linked_skill in all_transfer_rows:
        if linked_skill.name.casefold() in GENERIC_TRANSFER_SKILLS:
            continue
        by_skill[link.skill_id].append((topic, linked_subject))
        cross_skill_names[link.skill_id] = linked_skill.name
    added_cross_pairs: set[tuple[int, int]] = set()
    current_ids = set(topic_ids)
    for skill_id, linked_topics in by_skill.items():
        frequency_limit = 24 if cross_skill_names.get(skill_id, "").casefold() in CONTROLLED_CROSS_SKILLS else 12
        if len(linked_topics) > frequency_limit:
            continue
        for source_topic, source_subject in linked_topics:
            if source_topic.id not in current_ids:
                continue
            candidates = [
                (target_topic, target_subject)
                for target_topic, target_subject in linked_topics
                if target_subject.id != source_subject.id and target_topic.id != source_topic.id
                and supports_cross_subject_transfer(
                    cross_skill_names.get(skill_id, ""),
                    source_subject.name,
                    target_subject.name,
                )
            ][:2]
            for target_topic, target_subject in candidates:
                pair = (source_topic.id, target_topic.id)
                if pair in added_cross_pairs:
                    continue
                added_cross_pairs.add(pair)
                edge_values[(source_topic.id, target_topic.id, "cross_subject")] = {
                    "from_topic_id": source_topic.id,
                    "to_topic_id": target_topic.id,
                    "relation": "cross_subject",
                    "required_mastery": 0.8,
                    "confidence": 0.76,
                    "rationale": (
                        f"Навык из темы «{source_topic.name}» помогает начать тему "
                        f"«{target_topic.name}» по предмету «{target_subject.name}»."
                    ),
                    "source": "inferred",
                }
                cross_edges += 1
                reverse_pair = (target_topic.id, source_topic.id)
                if reverse_pair not in added_cross_pairs:
                    added_cross_pairs.add(reverse_pair)
                    edge_values[(target_topic.id, source_topic.id, "cross_subject")] = {
                        "from_topic_id": target_topic.id,
                        "to_topic_id": source_topic.id,
                        "relation": "cross_subject",
                        "required_mastery": 0.8,
                        "confidence": 0.76,
                        "rationale": (
                            f"Навык из темы «{target_topic.name}» помогает начать тему "
                            f"«{source_topic.name}» по предмету «{source_subject.name}»."
                        ),
                        "source": "inferred",
                    }
                    cross_edges += 1

    if edge_values:
        edge_insert = insert(TopicEdge).values(list(edge_values.values()))
        await db.execute(
            edge_insert.on_conflict_do_nothing(
                index_elements=[TopicEdge.from_topic_id, TopicEdge.to_topic_id, TopicEdge.relation],
            )
        )
    await db.flush()
    return {
        "topics": len(topics),
        "skills": len(unique_skill_ids),
        "edges": max(0, len(topics) - 1) + transfer_edges + cross_edges,
    }


def mastery_score_from_progress(*, status: str, mastery_status: str | None, score: float | None) -> float:
    if status != "completed":
        return 0.0
    if mastery_status == "mastered":
        return max(0.8, min(1.0, (score or 80) / 100))
    if mastery_status == "needs_practice":
        return min(0.59, max(0.25, (score or 50) / 100))
    return min(0.79, max(0.5, (score or 65) / 100))


def mastery_label(score: float) -> str:
    if score >= 0.8:
        return "mastered"
    if score >= 0.5:
        return "developing"
    return "emerging"


def progression_access_from_progress(
    *,
    status: str | None,
    mastery_status: str | None,
) -> tuple[float, str] | None:
    if status != "completed":
        return None
    if mastery_status == "mastered":
        return 1.0, "Предыдущая тема освоена."
    return (
        0.72,
        "Предыдущая тема пройдена. Можно продолжить, но рекомендуется повторить неосвоенные цели.",
    )


async def update_topic_skill_mastery(
    *,
    student_id: int,
    topic_id: int,
    score: float,
    evidence: dict[str, Any],
    db: AsyncSession,
) -> list[int]:
    frozen_map = evidence.get("objective_skill_map")
    if isinstance(frozen_map, dict):
        links = [SimpleNamespace(objective_id=objective_id, skill_id=skill_id)
                 for objective_id, skill_ids in frozen_map.items() for skill_id in skill_ids]
    else:
        links = list((await db.scalars(
            select(TopicSkill).where(TopicSkill.topic_id == topic_id, TopicSkill.role == "outcome")
        )).all())
    objective_mastery = evidence.get("objective_mastery") or {}
    objective_evidence = evidence.get("objective_evidence") or {}
    updated = []
    now = datetime.now(timezone.utc)
    for link in links:
        item = objective_mastery.get(link.objective_id)
        records = objective_evidence.get(link.objective_id, [])
        if not isinstance(item, dict) or not any(record.get("stage") == "assessment" for record in records):
            continue
        skill_score = max(0.0, min(1.0, float(item.get("score", 0)) / 100))
        statement = insert(StudentSkillMastery).values(
            student_id=student_id, skill_id=link.skill_id, mastery_score=skill_score,
            status=mastery_label(skill_score), evidence_count=1, source_topic_id=topic_id,
            evidence=evidence, last_evidence_at=now, updated_at=now,
        ).on_conflict_do_update(
            index_elements=[StudentSkillMastery.student_id, StudentSkillMastery.skill_id],
            set_={"mastery_score": skill_score, "status": mastery_label(skill_score),
                  "evidence_count": StudentSkillMastery.evidence_count + 1,
                  "source_topic_id": topic_id, "evidence": evidence,
                  "last_evidence_at": now, "updated_at": now},
        )
        await db.execute(statement)
        updated.append(link.skill_id)
    return updated


async def refresh_student_access(
    student_id: int,
    db: AsyncSession,
    *,
    source_topic_id: int | None = None,
) -> list[dict[str, Any]]:
    """Materialize topic readiness and return newly opened gates.

    The graph is a guidance layer, not a hard lock. A low-readiness topic remains
    visible as ``locked`` so the UI can warn the student, but published lessons
    can still be opened.
    """
    clear_curriculum_map_cache(student_id)
    from services.lessons import clear_student_manifest_state_cache

    # Пройденная тема открывает следующую: закэшированное «закрыто» у других тем устарело.
    clear_student_manifest_state_cache(student_id)
    student = await db.get(Student, student_id)
    if student is None:
        raise CurriculumGraphError(status_code=404, detail="Ученик не найден")
    # Карта нового ученика часто запрашивается несколько раз подряд: без блокировки
    # параллельные пересчёты пишут одни и те же строки и ждут друг друга до таймаута.
    await db.execute(text("SELECT pg_advisory_xact_lock(:namespace, :student_id)"),
                     {"namespace": ACCESS_LOCK_NAMESPACE, "student_id": student_id})

    topic_rows = (
        await db.execute(
            select(Topic, Section, Subject)
            .join(Section, Section.id == Topic.section_id)
            .join(Subject, Subject.id == Section.subject_id)
            .where(Subject.grade == student.grade, Topic.archived_at.is_(None))
            .order_by(Subject.id, Section.sort_order, Topic.sort_order, Topic.id)
        )
    ).all()
    eligible_topic_ids = [topic.id for topic, _section, _subject in topic_rows]
    stale_access = delete(StudentTopicAccess).where(
        StudentTopicAccess.student_id == student_id,
    )
    if eligible_topic_ids:
        stale_access = stale_access.where(StudentTopicAccess.topic_id.not_in(eligible_topic_ids))
    await db.execute(stale_access)
    if not topic_rows:
        return []
    topic_ids = eligible_topic_ids
    progress_rows = list((await db.scalars(
        select(Progress).where(Progress.student_id == student_id, Progress.topic_id.in_(topic_ids))
    )).all())
    progress_by_topic = {row.topic_id: row for row in progress_rows}
    mastery_rows = list((await db.scalars(
        select(StudentSkillMastery).where(StudentSkillMastery.student_id == student_id)
    )).all())
    skill_scores = {row.skill_id: float(row.mastery_score) for row in mastery_rows}
    prerequisites = list((await db.scalars(
        select(TopicSkill).where(TopicSkill.topic_id.in_(topic_ids), TopicSkill.role == "prerequisite")
    )).all())
    # Порядок задаёт граф темы. Тема без графа (граф предмета ещё не построен) не закрывается:
    # сервер её не проверяет, и ученик не должен видеть «Закрыто» навсегда.
    graph_topic_ids = set((await db.scalars(
        select(TopicSkill.topic_id).where(TopicSkill.topic_id.in_(topic_ids)).distinct()
    )).all())
    prereqs_by_topic: dict[int, list[TopicSkill]] = defaultdict(list)
    for item in prerequisites:
        prereqs_by_topic[item.topic_id].append(item)
    edges = list((await db.scalars(
        select(TopicEdge).where(TopicEdge.to_topic_id.in_(topic_ids))
    )).all())
    edges_by_target: dict[int, list[TopicEdge]] = defaultdict(list)
    for edge in edges:
        edges_by_target[edge.to_topic_id].append(edge)

    existing_access = list((await db.scalars(
        select(StudentTopicAccess).where(StudentTopicAccess.student_id == student_id)
    )).all())
    access_by_topic = {row.topic_id: row for row in existing_access}
    previous_states = {row.topic_id: row.state for row in existing_access}
    first_topic_by_subject: dict[int, int] = {}
    for topic, _section, subject in topic_rows:
        first_topic_by_subject.setdefault(subject.id, topic.id)

    mastered_topics = {
        row.topic_id for row in progress_rows
        if row.status == "completed" and row.mastery_status == "mastered"
    }
    now = datetime.now(timezone.utc)
    new_gates: list[dict[str, Any]] = []
    access_values: list[dict[str, Any]] = []
    topic_names = {topic.id: topic.name for topic, _section, _subject in topic_rows}
    for topic, _section, subject in topic_rows:
        progress = progress_by_topic.get(topic.id)
        state = "locked"
        readiness = 0.0
        reason = "Тема пока закрыта: сначала пройдите предыдущие темы."
        unlocked_by: int | None = None

        if topic.id in mastered_topics:
            state, readiness, reason = "mastered", 1.0, "Тема освоена."
        elif progress is not None and progress.status == "in_progress":
            state, reason = "in_progress", "Вы уже начали эту тему."
        elif progress is not None and progress.status == "completed":
            state, readiness = "available", 1.0
            reason = "Попытка завершена, но цели темы ещё не освоены. Пройдите урок ещё раз."
        elif first_topic_by_subject.get(subject.id) == topic.id:
            state, readiness, reason = "available", 1.0, "Стартовая тема курса."
        else:
            prereqs = prereqs_by_topic.get(topic.id, [])
            if prereqs:
                total_weight = sum(item.weight for item in prereqs) or 1.0
                readiness = sum(
                    min(1.0, skill_scores.get(item.skill_id, 0.0) / max(item.mastery_threshold, 0.01)) * item.weight
                    for item in prereqs
                ) / total_weight
            all_incoming = edges_by_target.get(topic.id, [])
            progression_edges = [edge for edge in all_incoming if edge.relation == "progression"]
            progression_unlocks = []
            for edge in progression_edges:
                source_progress = progress_by_topic.get(edge.from_topic_id)
                progression_access = progression_access_from_progress(
                    status=source_progress.status if source_progress is not None else None,
                    mastery_status=source_progress.mastery_status if source_progress is not None else None,
                )
                if progression_access is not None:
                    progression_readiness, progression_reason = progression_access
                    progression_unlocks.append((edge, progression_readiness, progression_reason))
            mastered_warp = [
                edge for edge in all_incoming
                if edge.relation in {"transfer", "cross_subject"}
                and edge.from_topic_id in mastered_topics
            ]
            if progression_edges and not progression_unlocks:
                previous = topic_names.get(progression_edges[0].from_topic_id)
                if previous:
                    reason = f"Откроется, когда будет пройдена тема «{previous}»."
            if progression_unlocks:
                _best, progression_readiness, progression_reason = max(
                    progression_unlocks,
                    key=lambda item: (item[1], item[0].confidence),
                )
                state, readiness = "available", max(readiness, progression_readiness)
                reason = progression_reason
            elif mastered_warp:
                best = max(mastered_warp, key=lambda edge: edge.confidence)
                readiness = max(readiness, best.confidence)
                if readiness >= 0.75:
                    state = "available"
                    unlocked_by = best.from_topic_id
                    reason = best.rationale
            elif not progression_edges and prereqs and readiness >= 1.0:
                state, reason = "available", "Необходимые навыки уже освоены."

        if state == "locked" and topic.id not in graph_topic_ids:
            state, readiness, reason = "available", 1.0, "Тема доступна."
        access_values.append({
            "student_id": student_id,
            "topic_id": topic.id,
            "state": state,
            "readiness_score": min(1.0, readiness),
            "reason": reason,
            "unlocked_by_topic_id": unlocked_by,
            "unlocked_at": now if state == "available" else None,
            "updated_at": now,
        })

        if state == "available" and previous_states.get(topic.id) not in {"available", "in_progress", "mastered"} and unlocked_by:
            trigger_skill_ids = [item.skill_id for item in prereqs_by_topic.get(topic.id, []) if skill_scores.get(item.skill_id, 0) >= item.mastery_threshold]
            event_statement = (
                insert(WarpGateEvent)
                .values(
                    student_id=student_id,
                    from_topic_id=unlocked_by,
                    to_topic_id=topic.id,
                    readiness_score=min(1.0, readiness),
                    trigger_skill_ids=trigger_skill_ids,
                    explanation=reason,
                )
                .on_conflict_do_nothing(index_elements=[WarpGateEvent.student_id, WarpGateEvent.from_topic_id, WarpGateEvent.to_topic_id])
            )
            await db.execute(event_statement)
            if source_topic_id is None or unlocked_by == source_topic_id:
                new_gates.append({
                    "from_topic_id": unlocked_by,
                    "to_topic_id": topic.id,
                    "topic_name": topic.name,
                    "subject_name": subject.name,
                    "readiness_score": round(min(1.0, readiness), 2),
                    "explanation": reason,
                    "trigger_skill_ids": trigger_skill_ids,
                })
    await _upsert_topic_access(db, access_values)
    return new_gates


# Ключ pg_advisory_xact_lock: пространство «доступ к темам», второй ключ — id ученика.
ACCESS_LOCK_NAMESPACE = 7301
# Одна вставка на пачку, а не на тему: у ученика старших классов сотни тем.
ACCESS_UPSERT_BATCH = 500


async def _upsert_topic_access(db: AsyncSession, values: list[dict[str, Any]]) -> None:
    for start in range(0, len(values), ACCESS_UPSERT_BATCH):
        statement = insert(StudentTopicAccess).values(values[start:start + ACCESS_UPSERT_BATCH])
        excluded = statement.excluded
        await db.execute(statement.on_conflict_do_update(
            index_elements=[StudentTopicAccess.student_id, StudentTopicAccess.topic_id],
            set_={
                "state": excluded.state,
                "readiness_score": excluded.readiness_score,
                "reason": excluded.reason,
                "unlocked_by_topic_id": excluded.unlocked_by_topic_id,
                # Закрытая тема сохраняет дату прежнего открытия.
                "unlocked_at": func.coalesce(excluded.unlocked_at, StudentTopicAccess.unlocked_at),
                "updated_at": excluded.updated_at,
            },
        ))


def _has_stale_lock(rows: list[Any]) -> bool:
    """Тема закрыта, хотя предыдущая в том же предмете уже пройдена — строки доступа устарели
    (например, записаны старой версией или пересчёт после урока не случился)."""
    previous_completed: dict[int, bool] = {}
    for _topic, _section, subject, access, _lesson_status, progress in rows:
        if access is not None and access.state == "locked" and previous_completed.get(subject.id):
            return True
        previous_completed[subject.id] = getattr(progress, "status", None) == "completed"
    return False


async def get_student_curriculum_map(
    student_id: int,
    db: AsyncSession,
    *,
    subject_id: int | None = None,
    refresh: bool = False,
) -> dict[str, Any]:
    if not refresh:
        cached = cached_curriculum_map(student_id, subject_id)
        if cached is not None:
            return cached
    student = await db.get(Student, student_id)
    if student is None:
        raise CurriculumGraphError(status_code=404, detail="Ученик не найден")

    async def load_rows():
        statement = (
            select(Topic, Section, Subject, StudentTopicAccess, GeneratedLesson.status, Progress)
            .join(Section, Section.id == Topic.section_id)
            .join(Subject, Subject.id == Section.subject_id)
            .outerjoin(
                StudentTopicAccess,
                (StudentTopicAccess.topic_id == Topic.id) & (StudentTopicAccess.student_id == student_id),
            )
            .outerjoin(GeneratedLesson, GeneratedLesson.topic_id == Topic.id)
            .outerjoin(
                Progress,
                (Progress.topic_id == Topic.id) & (Progress.student_id == student_id),
            )
            .where(Subject.grade == student.grade, Topic.archived_at.is_(None))
            .order_by(Subject.grade, Subject.name, Section.sort_order, Topic.sort_order, Topic.id)
        )
        if subject_id is not None:
            statement = statement.where(Subject.id == subject_id)
        return (await db.execute(statement)).all()

    rows = await load_rows()
    has_materialized_access = any(access is not None for _topic, _section, _subject, access, _lesson_status, _progress in rows)
    if refresh or (rows and not has_materialized_access) or _has_stale_lock(rows):
        await refresh_student_access(student_id, db)
        await db.flush()
        rows = await load_rows()
    topics = []
    for topic, section, subject, access, lesson_status, progress in rows:
        topics.append({
            "id": topic.id,
            "name": topic.name,
            "hours": topic.hours,
            "lesson_type": getattr(topic, "lesson_type", "study"),
            "covered_topic_ids": getattr(topic, "covered_topic_ids", None) or [],
            "source_assessment_topic_id": getattr(topic, "source_assessment_topic_id", None),
            "progress_status": getattr(progress, "status", "not_started"),
            "section_id": section.id,
            "section_name": section.name,
            "subject_id": subject.id,
            "subject_name": subject.name,
            "grade": subject.grade,
            "state": access.state if access is not None else "locked",
            "readiness_score": float(access.readiness_score) if access is not None else 0.0,
            "reason": access.reason if access is not None else "Тема пока закрыта: сначала пройдите предыдущие темы.",
            "unlocked_by_topic_id": access.unlocked_by_topic_id if access is not None else None,
            "lesson_status": "published" if lesson_status == "published" else "preparing",
            "mastery_status": progress.mastery_status if progress is not None else None,
            "attempts": progress.attempts if progress is not None else 0,
        })
    await db.commit()
    payload = {"student_id": student_id, "topics": topics}
    remember_curriculum_map(student_id, subject_id, payload)
    return payload


async def require_curriculum_topic_access(student_id: int, topic_id: int, db: AsyncSession) -> None:
    """Refresh graph access without using mastery as a hard lesson lock."""
    has_graph = await db.scalar(select(TopicSkill.topic_id).where(TopicSkill.topic_id == topic_id).limit(1))
    if has_graph is None:
        return
    access = await db.scalar(
        select(StudentTopicAccess).where(
            StudentTopicAccess.student_id == student_id,
            StudentTopicAccess.topic_id == topic_id,
        )
    )
    if access is not None and access.state != "locked":
        return
    # Начатую тему не закрываем: ученик не должен потерять попытку.
    started = await db.scalar(select(Progress.id).where(
        Progress.student_id == student_id, Progress.topic_id == topic_id,
    ).limit(1))
    if started is not None:
        return
    # Нет строки или «закрыто» (могло устареть) — пересчитываем и решаем по свежим данным.
    await refresh_student_access(student_id, db)
    await db.commit()
    state = await db.scalar(select(StudentTopicAccess.state).where(
        StudentTopicAccess.student_id == student_id,
        StudentTopicAccess.topic_id == topic_id,
    ))
    # Темы открываются строго по порядку: прогресс по закрытой теме не принимаем.
    if state == "locked":
        raise CurriculumGraphError(status_code=403, detail="Тема пока закрыта: сначала пройдите предыдущую тему.")


async def get_subject_graph(subject_id: int, db: AsyncSession) -> dict[str, Any]:
    subject = await db.get(Subject, subject_id)
    if subject is None:
        raise CurriculumGraphError(status_code=404, detail="Предмет не найден")
    rows = (
        await db.execute(
            select(Topic, Section)
            .join(Section, Section.id == Topic.section_id)
            .where(Section.subject_id == subject_id, Topic.archived_at.is_(None))
            .order_by(Section.sort_order, Topic.sort_order, Topic.id)
        )
    ).all()
    topic_ids = [topic.id for topic, _section in rows]
    skill_rows = []
    edge_rows = []
    cross_edge_rows = []
    if topic_ids:
        skill_rows = (await db.execute(
            select(TopicSkill, Skill)
            .join(Skill, Skill.id == TopicSkill.skill_id)
            .where(TopicSkill.topic_id.in_(topic_ids))
        )).all()
        edge_rows = list((await db.scalars(
            select(TopicEdge).where(TopicEdge.from_topic_id.in_(topic_ids), TopicEdge.to_topic_id.in_(topic_ids))
        )).all())
        cross_edge_rows = list((await db.scalars(
            select(TopicEdge).where(
                TopicEdge.relation == "cross_subject",
                (TopicEdge.from_topic_id.in_(topic_ids)) | (TopicEdge.to_topic_id.in_(topic_ids)),
            )
        )).all())
    cross_topic_ids = {
        topic_id
        for edge in cross_edge_rows
        for topic_id in (edge.from_topic_id, edge.to_topic_id)
    }
    cross_context: dict[int, tuple[Topic, Subject]] = {}
    if cross_topic_ids:
        context_rows = (
            await db.execute(
                select(Topic, Subject)
                .join(Section, Section.id == Topic.section_id)
                .join(Subject, Subject.id == Section.subject_id)
                .where(Topic.id.in_(cross_topic_ids), Topic.archived_at.is_(None))
            )
        ).all()
        cross_context = {topic.id: (topic, linked_subject) for topic, linked_subject in context_rows}
    skills_by_topic: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for link, skill in skill_rows:
        skills_by_topic[link.topic_id].append({"id": skill.id, "name": skill.name, "role": link.role})
    return {
        "subject": {"id": subject.id, "name": subject.name, "grade": subject.grade},
        "topics": [
            {
                "id": topic.id,
                "name": topic.name,
                "section": section.name,
                "objectives": topic.learning_objectives,
                "lesson_type": getattr(topic, "lesson_type", "study"),
                "covered_topic_ids": getattr(topic, "covered_topic_ids", None) or [],
                "source_assessment_topic_id": getattr(topic, "source_assessment_topic_id", None),
                "review_required": getattr(topic, "review_required", False),
                "skills": skills_by_topic.get(topic.id, []),
            }
            for topic, section in rows
        ],
        "edges": [
            {
                "id": edge.id,
                "from_topic_id": edge.from_topic_id,
                "to_topic_id": edge.to_topic_id,
                "relation": edge.relation,
                "confidence": edge.confidence,
                "rationale": edge.rationale,
            }
            for edge in edge_rows
        ],
        "cross_subject_opportunities": [
            {
                "from_topic_id": edge.from_topic_id,
                "from_topic_name": cross_context[edge.from_topic_id][0].name,
                "from_subject_name": cross_context[edge.from_topic_id][1].name,
                "to_topic_id": edge.to_topic_id,
                "to_topic_name": cross_context[edge.to_topic_id][0].name,
                "to_subject_name": cross_context[edge.to_topic_id][1].name,
                "confidence": edge.confidence,
                "rationale": edge.rationale,
            }
            for edge in cross_edge_rows
            if edge.from_topic_id in cross_context and edge.to_topic_id in cross_context
        ],
    }
