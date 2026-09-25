"""Context-aware media recommendations for generated lesson blocks."""

from __future__ import annotations

import re
from typing import Any


EXPLANATION_COMPONENTS = {
    "ShortExplanation", "KeyConcept", "WorkedExample", "MindMap", "Timeline",
    "InteractiveGraph", "Illustration", "Presentation", "PredictionLab",
    "DataInvestigation", "PhysicsSandbox", "HotspotInvestigation",
}

PROCESS_WORDS = {
    "этап", "процесс", "цикл", "измен", "движ", "последователь", "алгоритм",
    "реакц", "развит", "ход событий", "преобраз", "опыт", "эксперимент",
}

# Медиа усиливает блок, а не дублирует его: сцена, крупный план или
# реконструкция без текста. Точные схемы, формулы и числа урок рисует сам.
SUBJECT_PROFILES: tuple[tuple[tuple[str, ...], dict[str, str]], ...] = (
    (("литератур", "язык", "русск", "кыргыз"), {
        "family": "humanities",
        "intent": "source_context",
        "image_form": "editorial literary illustration of a key moment, setting or mood of the work",
        "video_form": "quiet atmospheric scene from the world of the work, without depicting invented plot facts",
        "style": "book-illustration feel, expressive but faithful to the text and its era",
        "avoid": "invented quotations, inaccurate character appearance, book mockups, modern objects in a historical scene",
    }),
    (("истори", "обществ", "право"), {
        "family": "social_science",
        "intent": "cause_effect",
        "image_form": "artistic reconstruction of a place, everyday scene or turning point of the period",
        "video_form": "slow reconstruction of a historical setting or event unfolding, restrained and period-accurate",
        "style": "museum-quality reconstruction, neutral, period-accurate clothing, architecture and tools",
        "avoid": "anachronisms, political persuasion, invented flags or symbols, heroic propaganda",
    }),
    (("биолог", "хими", "естеств"), {
        "family": "natural_science",
        "intent": "structure",
        "image_form": "close-up or cutaway that reveals the hidden structure, organism or reaction at the right scale",
        "video_form": "short close-up of a living process or reaction changing over time at the correct scale",
        "style": "naturalistic, accurate proportions and colours, soft studio light",
        "avoid": "incorrect anatomy, mixed scales, impossible laboratory setups, decorative molecules",
    }),
    (("физик", "астроном"), {
        "family": "physics",
        "intent": "quantity",
        "image_form": "real-world scene or simple experiment where the physical effect is visible",
        "video_form": "stable-frame demonstration in which the physical effect visibly happens",
        "style": "clear, physically plausible scene with honest relative scale and materials",
        "avoid": "physically impossible motion, floating objects, cinematic camera movement",
    }),
    (("географ",), {
        "family": "geography",
        "intent": "cause_effect",
        "image_form": "landscape, aerial view or cross-section of terrain where the geographic process can be seen",
        "video_form": "aerial or landscape shot where a geographic process visibly unfolds",
        "style": "naturalistic landscape, accurate relief, climate and vegetation for the region",
        "avoid": "distorted geography, decorative globes, impossible landscapes",
    }),
    (("информат", "программ"), {
        "family": "computing",
        "intent": "process",
        "image_form": "concrete physical metaphor of the algorithm or data idea (objects being sorted, routed, stored)",
        "video_form": "physical metaphor of the algorithm running step by step with objects",
        "style": "clean tactile objects, clear arrangement, calm colours",
        "avoid": "fake code or interfaces, screens with writing, unexplained symbols",
    }),
    (("математ", "алгебр", "геометр"), {
        "family": "mathematics",
        "intent": "quantity",
        "image_form": "concrete objects or geometric shapes that embody the idea (tiles, blocks, lengths, areas)",
        "video_form": "objects or shapes transforming step by step so the mathematical idea becomes visible",
        "style": "precise shapes, honest proportions, minimal decoration",
        "avoid": "notation, ornamental formulas, inconsistent scale, answer-only posters",
    }),
)

DEFAULT_PROFILE = {
    "family": "general",
    "intent": "structure",
    "image_form": "single illustrative scene or close-up grounded in the lesson fragment",
    "video_form": "short illustrative shot showing one meaningful change over time",
    "style": "calm, clear illustration with one central idea",
    "avoid": "decorative filler, unrelated stock imagery, unsupported facts",
}

LESSON_VISUAL_SYSTEM = (
    "Use one coherent visual language across the whole lesson: 16:9 composition, tactile clay-and-paper editorial "
    "3D illustration, warm soft light, cream, sage, ochre and deep teal palette, rich but uncluttered detail, "
    "generous breathing space. Every image must look like part of the same illustrated story. No text, labels, "
    "numbers, logos, frames, gradients or stock-photo styling."
)


def subject_profile(subject: str | None) -> dict[str, str]:
    normalized = (subject or "").lower()
    for needles, profile in SUBJECT_PROFILES:
        if any(needle in normalized for needle in needles):
            return profile
    return DEFAULT_PROFILE


def _text(value: Any) -> str:
    if isinstance(value, str):
        return re.sub(r"\s+", " ", value).strip()
    if isinstance(value, list):
        return " ".join(part for item in value if (part := _text(item)))
    if isinstance(value, dict):
        preferred = ("title", "heading", "term", "text", "body", "description", "problem", "learning_point")
        return " ".join(part for key in preferred if (part := _text(value.get(key))))
    return ""


def _intent(profile: dict[str, str], context: str) -> str:
    lowered = context.lower()
    if any(word in lowered for word in PROCESS_WORDS):
        return "process"
    if any(word in lowered for word in ("ошиб", "невер", "заблужд")):
        return "mistake"
    if any(word in lowered for word in ("причин", "следств", "влия", "почему")):
        return "cause_effect"
    return profile["intent"]


def _kind(intent: str, video_used: bool, context: str) -> str:
    dynamic = intent == "process" and len(context) > 80
    return "video" if dynamic and not video_used else "image"


def _recommendation(
    *, index: int, block_index: int, component: str, heading: str, context: str,
    learning_goal: str, profile: dict[str, str], scene_id: str | None,
    slide_index: int | None = None, slide_id: str | None = None, video_used: bool = False,
    preferred_kind: str | None = None,
) -> dict[str, Any]:
    intent = _intent(profile, f"{heading} {context}")
    kind = preferred_kind if preferred_kind in {"image", "video"} else _kind(intent, video_used, context)
    visual_form = profile["video_form"] if kind == "video" else profile["image_form"]
    return {
        "id": f"media-{block_index + 1}-{slide_index + 1 if slide_index is not None else 0}",
        "kind": kind,
        "title": heading or "Контекстная визуализация",
        "reason": f"Поможет ученику увидеть {learning_goal or heading or 'главную связь'}, а не просто перечитать объяснение.",
        "subject_family": profile["family"],
        "block_index": block_index,
        "slide_index": slide_index,
        "scene_id": scene_id,
        "slide_id": slide_id,
        "beat_id": slide_id or scene_id,
        "heading": heading,
        "learning_goal": learning_goal or heading,
        "source_context": context[:1400],
        "visual_intent": intent,
        "visual_form": visual_form,
        "pedagogical_role": "visual reinforcement of the block",
        "style": f"{profile['style']}. {LESSON_VISUAL_SYSTEM}",
        "visual_system": LESSON_VISUAL_SYSTEM,
        "must_include": [],
        "avoid": [profile["avoid"], "unrelated visual metaphors", "any text, labels or numbers in the image"],
        "success_check": f"ученик может по визуализации объяснить: {learning_goal or heading}",
        "placement": "slide_visual" if slide_index is not None else "after_block",
        "component": component,
        "priority": index + 1,
    }


def build_block_media_plan(
    *, block: dict[str, Any], block_index: int, metadata: dict[str, Any] | None = None,
    scene_id: str | None = None, slide_index: int | None = None,
    preferred_kind: str | None = None,
) -> dict[str, Any]:
    metadata = metadata or {}
    subject = str(metadata.get("subject_name") or "")
    topic = str(metadata.get("topic_name") or "Урок")
    profile = subject_profile(subject)
    component = str(block.get("component") or "")
    content = block.get("content") if isinstance(block.get("content"), dict) else {}
    recommendations: list[dict[str, Any]] = []

    if component == "Presentation" and isinstance(content.get("slides"), list):
        indexed_slides = list(enumerate(content["slides"]))
        if slide_index is not None:
            indexed_slides = [item for item in indexed_slides if item[0] == slide_index]
        for current_index, raw_slide in indexed_slides:
            if not isinstance(raw_slide, dict):
                continue
            heading = _text(raw_slide.get("heading")) or _text(content.get("title")) or topic
            context = _text(raw_slide) or heading
            goal = _text(raw_slide.get("learning_point")) or heading
            recommendations.append(_recommendation(
                index=len(recommendations), block_index=block_index, component=component,
                heading=heading, context=context, learning_goal=goal, profile=profile,
                scene_id=scene_id, slide_index=current_index,
                slide_id=str(raw_slide.get("id") or f"slide-{current_index + 1}"),
                preferred_kind=preferred_kind,
            ))
    elif component in EXPLANATION_COMPONENTS:
        heading = _text(content.get("title")) or _text(content.get("term")) or topic
        context = _text(content) or heading
        recommendations.append(_recommendation(
            index=0, block_index=block_index, component=component,
            heading=heading, context=context, learning_goal=heading, profile=profile,
            scene_id=scene_id, preferred_kind=preferred_kind,
        ))

    return {
        "subject": subject,
        "topic": topic,
        "subject_family": profile["family"],
        "visual_system": LESSON_VISUAL_SYSTEM,
        "recommendations": recommendations,
    }


# Где картинка помогает понять, а не подсказывает ответ. Порядок — приоритет:
# сначала слайды объяснения, потом понятия, потом сцены задач и опытов.
ILLUSTRATED_COMPONENTS: dict[str, str] = {
    "Presentation": "slide",
    "ShortExplanation": "concept",
    "KeyConcept": "concept",
    "WorkedExample": "task_scene",
    "PredictionLab": "experiment_setup",
    "BranchingScenario": "situation",
    "GuidedPractice": "task_scene",
    "IndependentProblem": "task_scene",
    "Timeline": "cover",
}
_ROLE_PRIORITY = {"slide": 0, "concept": 1, "cover": 2, "situation": 3, "experiment_setup": 3, "task_scene": 4}
# Для задач и опытов картинка показывает условие, но не ответ и не результат.
NO_SPOILER_ROLES = {"task_scene", "experiment_setup", "situation"}
NO_SPOILER_RULE = "the answer, the solution, the result or the outcome of the task or experiment"
# Картинки ставятся во все уместные места урока. Потолок только страховочный:
# чтобы урок не ушёл случайно в десятки платных генераций.
MEDIA_SAFETY_CAP = 24


def media_limit(metadata: dict[str, Any]) -> int:
    return MEDIA_SAFETY_CAP


def _has_media(content: dict[str, Any]) -> bool:
    media = content.get("media") if isinstance(content.get("media"), dict) else {}
    return bool(media.get("url") or content.get("url") or content.get("data_url"))


def _slot(content: dict[str, Any]) -> dict[str, Any] | None:
    slot = content.get("media_slot")
    return slot if isinstance(slot, dict) else None


def _strings(value: Any) -> list[str]:
    return [item.strip() for item in value if isinstance(item, str) and item.strip()] if isinstance(value, list) else []


def _block_heading(content: dict[str, Any], topic: str) -> str:
    for key in ("title", "term", "heading", "problem", "question", "context"):
        if (value := _text(content.get(key))):
            return value[:120]
    return topic


def build_lesson_media_plan(
    blocks: list[dict[str, Any]], metadata: dict[str, Any] | None = None,
    lesson_document: dict[str, Any] | None = None, *, allow_video: bool = True,
) -> dict[str, Any]:
    """Места под картинки урока: все уместные блоки и слайды.

    Каждый подходящий блок получает картинку; разметка генератора (media_slot)
    уточняет, что на ней показать. В презентации, где генератор разметил
    слайды, берём только размеченные: так он пропускает мини-проверку и
    слайды, где картинка подсказала бы ответ. Заполненные места не повторяем.
    """
    metadata = metadata or {}
    subject = str(metadata.get("subject_name") or "")
    topic = str(metadata.get("topic_name") or "Урок")
    profile = subject_profile(subject)
    limit = media_limit(metadata)
    scenes = {}
    for episode in (lesson_document or {}).get("episodes", []):
        for scene in episode.get("scenes", []):
            scenes[scene.get("original_block_index")] = scene.get("id")

    candidates: list[dict[str, Any]] = []
    for block_index, block in enumerate(blocks):
        component = str(block.get("component") or "")
        role = ILLUSTRATED_COMPONENTS.get(component)
        content = block.get("content") if isinstance(block.get("content"), dict) else {}
        if role is None:
            continue
        if component == "Presentation" and isinstance(content.get("slides"), list):
            marked = any(isinstance(slide, dict) and _slot(slide) for slide in content["slides"])
            for slide_index, raw_slide in enumerate(content["slides"]):
                if not isinstance(raw_slide, dict) or _has_media(raw_slide):
                    continue
                if marked and not _slot(raw_slide):
                    continue
                heading = _text(raw_slide.get("heading")) or _text(content.get("title")) or topic
                candidates.append({
                    "role": role, "block_index": block_index, "slide_index": slide_index, "component": component,
                    "slot": _slot(raw_slide), "heading": heading, "context": _text(raw_slide) or heading,
                    "goal": _text(raw_slide.get("learning_point")) or heading,
                    "slide_id": str(raw_slide.get("id") or f"slide-{slide_index + 1}"),
                })
        elif not _has_media(content):
            heading = _block_heading(content, topic)
            slot = _slot(content)
            candidates.append({
                "role": role, "block_index": block_index, "slide_index": None, "component": component,
                "slot": slot, "heading": heading, "context": _text(content) or heading,
                "goal": _text((slot or {}).get("learning_purpose")) or heading, "slide_id": None,
            })

    # Если сработает потолок, первыми остаются места, размеченные генератором.
    candidates.sort(key=lambda item: (item["slot"] is None, _ROLE_PRIORITY[item["role"]], item["block_index"], item["slide_index"] or 0))

    recommendations: list[dict[str, Any]] = []
    video_used = not allow_video
    for item in candidates[:limit]:
        slot = item["slot"] or {}
        rec = _recommendation(
            index=len(recommendations), block_index=item["block_index"], component=item["component"],
            heading=item["heading"], context=item["context"], learning_goal=item["goal"], profile=profile,
            scene_id=scenes.get(item["block_index"]), slide_index=item["slide_index"], slide_id=item["slide_id"],
            video_used=video_used, preferred_kind=None if allow_video else "image",
        )
        video_used = video_used or rec["kind"] == "video"
        rec["media_role"] = item["role"]
        rec["media_slot_id"] = str(slot.get("id") or rec["id"])
        rec["must_include"] = _strings(slot.get("must_show"))
        rec["avoid"] = [*rec["avoid"], *_strings(slot.get("must_not_show"))]
        if item["role"] in NO_SPOILER_ROLES:
            rec["avoid"].append(NO_SPOILER_RULE)
        if item["slide_index"] is None:
            rec["placement"] = "block_visual"
        recommendations.append(rec)

    return {
        "subject": subject,
        "topic": topic,
        "subject_family": profile["family"],
        "limit": limit,
        "strategy": f"{profile['family']} · {len(recommendations)} из {limit} иллюстраций",
        "recommendations": recommendations,
    }
