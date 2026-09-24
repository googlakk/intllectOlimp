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

SUBJECT_PROFILES: tuple[tuple[tuple[str, ...], dict[str, str]], ...] = (
    (("литератур", "язык", "русск", "кыргыз"), {
        "family": "humanities",
        "intent": "source_context",
        "image_form": "editorial literary illustration, motif map, character relationship map, or historical context scene",
        "video_form": "restrained animated literary timeline or narrated contextual sequence without depicting invented facts",
        "style": "school literature edition, expressive but historically grounded, readable Russian labels",
        "avoid": "invented quotations, inaccurate character appearance, decorative book mockups, modern objects in a historical scene",
    }),
    (("истори", "обществ", "право"), {
        "family": "social_science",
        "intent": "cause_effect",
        "image_form": "historical source map, causal diagram, annotated artefact, or chronological scene",
        "video_form": "clear chronological animation showing causes, turning point, and consequences",
        "style": "museum education graphic, source-aware, neutral and historically accurate",
        "avoid": "anachronisms, political persuasion, invented flags or quotations, heroic propaganda",
    }),
    (("биолог", "хими", "естеств"), {
        "family": "natural_science",
        "intent": "structure",
        "image_form": "scientifically accurate labeled cutaway, comparison, or process diagram",
        "video_form": "short scientific animation showing change over time at the correct scale",
        "style": "modern school atlas, accurate proportions, restrained color coding, readable Russian labels",
        "avoid": "incorrect anatomy, mixed scales, impossible laboratory setup, decorative molecules",
    }),
    (("физик", "астроном"), {
        "family": "physics",
        "intent": "quantity",
        "image_form": "physical model with vectors, forces, measured quantities, and a real-world reference",
        "video_form": "stable-frame motion demonstration with visible cause, trajectory, and measured change",
        "style": "clean physics textbook diagram with consistent vectors and units",
        "avoid": "physically impossible motion, inconsistent vectors, missing units, cinematic camera movement",
    }),
    (("географ",), {
        "family": "geography",
        "intent": "cause_effect",
        "image_form": "annotated map, cross-section, spatial comparison, or geographic process diagram",
        "video_form": "map-based animation showing spatial change, flow, or geographic process over time",
        "style": "school geographic atlas, accurate orientation, legend, scale, and Russian labels",
        "avoid": "distorted borders, missing legend, decorative globe, geographically impossible placement",
    }),
    (("информат", "программ"), {
        "family": "computing",
        "intent": "process",
        "image_form": "algorithm trace, data-flow diagram, interface state sequence, or memory model",
        "video_form": "step-by-step algorithm trace with highlighted state changes",
        "style": "clear computing diagram, monospaced code fragments, accessible color coding",
        "avoid": "unreadable code, fake interfaces, syntax errors, unexplained output",
    }),
    (("математ", "алгебр", "геометр"), {
        "family": "mathematics",
        "intent": "quantity",
        "image_form": "mathematical visual model, number line, geometric construction, or graph tied to the reasoning",
        "video_form": "step-by-step mathematical transformation with one change highlighted at a time",
        "style": "precise school mathematics diagram, correct notation, high contrast, minimal decoration",
        "avoid": "incorrect notation, answer-only poster, ornamental formulas, inconsistent scale",
    }),
)

DEFAULT_PROFILE = {
    "family": "general",
    "intent": "structure",
    "image_form": "labeled explanatory model or comparison grounded in the lesson text",
    "video_form": "short explanatory sequence showing one meaningful change over time",
    "style": "clean academic school visual with readable Russian labels and one central idea",
    "avoid": "decorative filler, unrelated stock imagery, dense paragraphs, unsupported facts",
}

LESSON_VISUAL_SYSTEM = (
    "Use one coherent visual language across the whole lesson: 16:9 composition, warm white or very light gray "
    "background, deep navy text, indigo as the primary accent, teal or amber only for semantic contrast, "
    "consistent line weight, generous empty space, and the same label hierarchy. The result must look like a "
    "part of one modern school presentation, not an isolated poster. No gradients, logos, decorative frames, "
    "photorealistic stock-photo styling, or dense paragraphs inside the visual."
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
        "pedagogical_role": "contextual explanation support",
        "style": f"{profile['style']}. {LESSON_VISUAL_SYSTEM}",
        "visual_system": LESSON_VISUAL_SYSTEM,
        "must_include": [item for item in (heading, learning_goal) if item][:4],
        "avoid": [profile["avoid"], "unrelated visual metaphors", "text copied from the lesson as a poster"],
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
