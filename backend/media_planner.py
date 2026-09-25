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


def build_lesson_media_plan(
    blocks: list[dict[str, Any]], metadata: dict[str, Any] | None = None,
    lesson_document: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = metadata or {}
    subject = str(metadata.get("subject_name") or "")
    topic = str(metadata.get("topic_name") or "Урок")
    profile = subject_profile(subject)
    volume = str(metadata.get("lesson_shape") or metadata.get("topic_contract", {}).get("volume") or "standard")
    limit = {"micro": 1, "standard": 2, "extended": 3, "unit": 4}.get(volume, 2)
    scenes = {}
    for episode in (lesson_document or {}).get("episodes", []):
        for scene in episode.get("scenes", []):
            scenes[scene.get("original_block_index")] = scene.get("id")

    recommendations: list[dict[str, Any]] = []
    video_used = False
    for block_index, block in enumerate(blocks):
        if len(recommendations) >= limit:
            break
        component = str(block.get("component") or "")
        content = block.get("content") if isinstance(block.get("content"), dict) else {}
        if component not in EXPLANATION_COMPONENTS or component == "GeneratedMedia":
            continue
        scene_id = scenes.get(block_index)
        if component == "Presentation" and isinstance(content.get("slides"), list):
            for slide_index, raw_slide in enumerate(content["slides"]):
                if len(recommendations) >= limit or not isinstance(raw_slide, dict) or raw_slide.get("media"):
                    continue
                heading = _text(raw_slide.get("heading")) or _text(content.get("title")) or topic
                context = _text(raw_slide) or heading
                goal = _text(raw_slide.get("learning_point")) or heading
                rec = _recommendation(
                    index=len(recommendations), block_index=block_index, component=component,
                    heading=heading, context=context, learning_goal=goal, profile=profile,
                    scene_id=scene_id, slide_index=slide_index,
                    slide_id=str(raw_slide.get("id") or f"slide-{slide_index + 1}"), video_used=video_used,
                )
                video_used = video_used or rec["kind"] == "video"
                recommendations.append(rec)
        elif not content.get("url") and not content.get("data_url"):
            heading = _text(content.get("title")) or _text(content.get("term")) or topic
            context = _text(content) or heading
            rec = _recommendation(
                index=len(recommendations), block_index=block_index, component=component,
                heading=heading, context=context, learning_goal=heading, profile=profile,
                scene_id=scene_id, video_used=video_used,
            )
            video_used = video_used or rec["kind"] == "video"
            recommendations.append(rec)

    return {
        "subject": subject,
        "topic": topic,
        "subject_family": profile["family"],
        "strategy": f"{profile['family']} · {len(recommendations)} контекстных материала",
        "recommendations": recommendations,
    }
