"""Versioned lesson-document contract shared by generation and delivery."""

from __future__ import annotations

import re
from typing import Any

from narration import fallback_avatar_script, is_screen_duplicate, spoken_text

SCHEMA_VERSION = 2
PHASE_ORDER = ("orient", "activate", "explain", "investigate", "practice", "assess", "reflect")


def _slug(value: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug[:80] or fallback


def _objective_ids(block: dict[str, Any]) -> list[str]:
    content = block.get("content") if isinstance(block.get("content"), dict) else {}
    raw = content.get("objective_ids", [])
    if isinstance(raw, str):
        return [raw]
    return [item for item in raw if isinstance(item, str)] if isinstance(raw, list) else []


def _phase(block: dict[str, Any]) -> str:
    content = block.get("content") if isinstance(block.get("content"), dict) else {}
    stage = content.get("evidence_stage")
    component = block.get("component")
    if stage == "diagnostic":
        return "activate"
    if stage == "assessment" or component == "MasteryCheck":
        return "assess"
    if component == "Reflection":
        return "reflect"
    if stage == "practice":
        return "practice"
    if component in {"PredictionLab", "DataInvestigation", "PhysicsSandbox", "HotspotInvestigation"}:
        return "investigate"
    return "explain"


def _block_title(block: dict[str, Any], index: int) -> str:
    content = block.get("content") if isinstance(block.get("content"), dict) else {}
    for key in ("title", "term", "question", "problem", "prompt"):
        value = content.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    labels = {
        "ShortExplanation": "Объяснение",
        "Presentation": "Презентация",
        "WorkedExample": "Разобранный пример",
        "GuidedPractice": "Практика с поддержкой",
        "IndependentProblem": "Самостоятельная практика",
        "MasteryCheck": "Итоговая проверка",
        "Reflection": "Рефлексия",
    }
    return labels.get(str(block.get("component")), f"Шаг {index + 1}")


def _compact_text(value: Any, limit: int = 900) -> str:
    return re.sub(r"\s+", " ", value).strip()[:limit] if isinstance(value, str) else ""


def _compact_script(value: Any) -> str:
    return spoken_text(value)


def _presentation_script(slide: dict[str, Any]) -> str:
    script = _compact_script(slide.get("avatar_script"))
    visible = [slide.get("heading"), slide.get("body"), slide.get("learning_point"), slide.get("visual")]
    if not script or is_screen_duplicate(script, visible):
        return fallback_avatar_script("Presentation", slide)
    return script


def _visible_content_values(content: dict[str, Any]) -> list[Any]:
    keys = {
        "title", "term", "text", "definition", "example", "non_example", "problem",
        "question", "prompt", "instruction", "description", "context", "task", "callout",
        "explanation", "caption", "scale_question",
    }
    values: list[Any] = []
    for key, value in content.items():
        if key not in keys:
            continue
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, list):
            values.extend(item for item in value if isinstance(item, str))
    return values


def _presentation_beats(block: dict[str, Any], scene_id: str, index: int) -> list[dict[str, Any]]:
    content = block.get("content") if isinstance(block.get("content"), dict) else {}
    slides = content.get("slides") if isinstance(content.get("slides"), list) else []
    beats: list[dict[str, Any]] = []
    for slide_index, raw_slide in enumerate(slides):
        if not isinstance(raw_slide, dict):
            continue
        slide = raw_slide
        slide_id = slide.get("id") if isinstance(slide.get("id"), str) else f"slide-{slide_index + 1}"
        slide["id"] = slide_id
        script = _presentation_script(slide)
        cue = None
        if script:
            cue = {
                "id": f"cue-{index + 1}-{slide_id}",
                "scene_id": scene_id,
                "beat_id": slide_id,
                "slide_id": slide_id,
                "phase": "explain",
                "role": "explain",
                "script": script,
                "trigger": "scene_start",
                "autoplay": False,
                "fallback_text": script,
            }
        media_slot = slide.get("media_slot") if isinstance(slide.get("media_slot"), dict) else None
        beats.append({
            "id": slide_id,
            "objective_ids": _objective_ids(block),
            "title": _compact_text(slide.get("heading"), 240) or f"Слайд {slide_index + 1}",
            "learning_point": _compact_text(slide.get("learning_point")),
            "avatar_cue_ids": [cue["id"]] if cue else [],
            "media_slot_ids": [media_slot.get("id")] if media_slot and isinstance(media_slot.get("id"), str) else [],
        })
    return beats


def _avatar_cues(block: dict[str, Any], scene_id: str, index: int) -> list[dict[str, Any]]:
    component = block.get("component")
    content = block.get("content") if isinstance(block.get("content"), dict) else {}
    if component == "Presentation":
        beats = _presentation_beats(block, scene_id, index)
        slides = content.get("slides") if isinstance(content.get("slides"), list) else []
        cues = []
        for beat, slide in zip(beats, slides):
            if not isinstance(slide, dict):
                continue
            script = _presentation_script(slide)
            if script:
                cues.append({
                    "id": beat["avatar_cue_ids"][0], "scene_id": scene_id,
                    "beat_id": beat["id"], "slide_id": beat["id"],
                    "phase": "explain", "role": "explain", "script": script,
                    "trigger": "scene_start", "autoplay": False, "fallback_text": script,
                })
        return cues
    script = _compact_script(content.get("avatar_script"))
    if not script or is_screen_duplicate(script, _visible_content_values(content)):
        script = fallback_avatar_script(str(component), content)
    if not script:
        return []
    return [{
        "id": f"cue-{index + 1}",
        "scene_id": scene_id,
        "beat_id": scene_id,
        "phase": "recap" if component == "Reflection" else "prompt" if _phase(block) in {"activate", "practice", "assess"} else "explain",
        "role": "prompt" if _phase(block) in {"activate", "practice", "assess"} else "explain",
        "script": script,
        "trigger": "scene_start",
        "autoplay": False,
        "fallback_text": script,
    }]


def adapt_legacy_blocks(
    blocks: list[dict[str, Any]],
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Group flat v1 blocks into semantic episodes without losing block identity."""
    metadata = metadata or {}
    objective_catalog = metadata.get("objectives") if isinstance(metadata.get("objectives"), list) else []
    objective_titles = {
        item.get("id"): item.get("text")
        for item in objective_catalog
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    grouped: dict[tuple[str, str], list[tuple[int, dict[str, Any]]]] = {}
    for index, block in enumerate(blocks):
        if not isinstance(block, dict):
            continue
        phase = _phase(block)
        objective_id = (_objective_ids(block) or ["general"])[0]
        grouped.setdefault((phase, objective_id), []).append((index, block))

    episodes: list[dict[str, Any]] = []
    for phase in PHASE_ORDER:
        for (candidate_phase, objective_id), entries in grouped.items():
            if candidate_phase != phase:
                continue
            episode_id = f"{phase}-{_slug(objective_id, str(len(episodes) + 1))}"
            scenes = []
            for index, block in entries:
                scene_id = f"scene-{index + 1}"
                cues = _avatar_cues(block, scene_id, index)
                beats = _presentation_beats(block, scene_id, index) if block.get("component") == "Presentation" else [{
                    "id": scene_id,
                    "objective_ids": _objective_ids(block),
                    "title": _block_title(block, index),
                    "learning_point": "",
                    "avatar_cue_ids": [cue["id"] for cue in cues],
                    "media_slot_ids": [],
                }]
                scenes.append({
                    "id": scene_id,
                    "original_block_index": index,
                    "purpose": phase,
                    "title": _block_title(block, index),
                    "objective_ids": _objective_ids(block),
                    "block": block,
                    "teaching_beats": beats,
                    "avatar_cues": cues,
                    "completion_rule": "interaction" if phase in {"activate", "practice", "assess"} else "viewed",
                })
            title = objective_titles.get(objective_id) or {
                "activate": "Разминка",
                "explain": "Разберём идею",
                "investigate": "Исследование",
                "practice": "Попробуем",
                "assess": "Проверим понимание",
                "reflect": "Подведём итог",
            }.get(phase, "Учебный эпизод")
            episodes.append({
                "id": episode_id,
                "title": title,
                "phase": phase,
                "objective_ids": [] if objective_id == "general" else [objective_id],
                "estimated_minutes": max(1, len(scenes) * 2),
                "scenes": scenes,
            })

    contract = metadata.get("topic_contract") if isinstance(metadata.get("topic_contract"), dict) else {}
    hours = contract.get("hours") if isinstance(contract.get("hours"), int) else 1
    return {
        "schema_version": SCHEMA_VERSION,
        "source": "legacy_adapter",
        "title": metadata.get("topic_name") or "Урок",
        "format": contract.get("volume") or "standard",
        "estimated_minutes": max(5, min(90, hours * 20)),
        "objectives": objective_catalog,
        "episodes": episodes,
        "avatar": {
            "enabled": True,
            "mode": "scripted",
            "language": metadata.get("content_language") or "ru",
        },
    }


def normalize_lesson_document(
    document: dict[str, Any] | None,
    blocks: list[dict[str, Any]],
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if isinstance(document, dict) and document.get("schema_version") == SCHEMA_VERSION:
        episodes = document.get("episodes")
        if isinstance(episodes, list) and episodes:
            return synchronize_teaching_beats(document)
    return adapt_legacy_blocks(blocks, metadata)


def synchronize_teaching_beats(document: dict[str, Any]) -> dict[str, Any]:
    """Upgrade early v2 documents with deterministic beat-level orchestration."""
    for episode in document.get("episodes", []):
        if not isinstance(episode, dict):
            continue
        for scene_index, scene in enumerate(episode.get("scenes", [])):
            if not isinstance(scene, dict):
                continue
            block = scene.get("block") if isinstance(scene.get("block"), dict) else {}
            scene_id = scene.get("id") if isinstance(scene.get("id"), str) else f"scene-{scene_index + 1}"
            original_index = scene.get("original_block_index")
            block_index = original_index if isinstance(original_index, int) else scene_index
            if block.get("component") == "Presentation":
                scene["teaching_beats"] = _presentation_beats(block, scene_id, block_index)
                scene["avatar_cues"] = _avatar_cues(block, scene_id, block_index)
            else:
                existing_cues = scene.get("avatar_cues") if isinstance(scene.get("avatar_cues"), list) else []
                for cue in existing_cues:
                    if isinstance(cue, dict):
                        cue["script"] = _compact_script(cue.get("script") or cue.get("fallback_text"))
                        cue["fallback_text"] = cue["script"]
                if not existing_cues:
                    scene["avatar_cues"] = _avatar_cues(block, scene_id, block_index)
            if block.get("component") != "Presentation" and (not isinstance(scene.get("teaching_beats"), list) or not scene["teaching_beats"]):
                cues = scene.get("avatar_cues") if isinstance(scene.get("avatar_cues"), list) else []
                for cue in cues:
                    if isinstance(cue, dict) and not cue.get("beat_id"):
                        cue["beat_id"] = scene_id
                scene["teaching_beats"] = [{
                    "id": scene_id,
                    "objective_ids": scene.get("objective_ids") or [],
                    "title": scene.get("title") or _block_title(block, block_index),
                    "learning_point": "",
                    "avatar_cue_ids": [cue.get("id") for cue in cues if isinstance(cue, dict) and cue.get("id")],
                    "media_slot_ids": [],
                }]
    return document


def flatten_lesson_document(document: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for episode in document.get("episodes", []):
        if not isinstance(episode, dict):
            continue
        for scene in episode.get("scenes", []):
            if isinstance(scene, dict) and isinstance(scene.get("block"), dict):
                blocks.append(scene["block"])
    return blocks


def validate_lesson_document(document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if document.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version должен быть равен 2")
    episodes = document.get("episodes")
    if not isinstance(episodes, list) or not episodes:
        errors.append("урок должен содержать хотя бы один эпизод")
        return errors
    seen: set[str] = set()
    for episode in episodes:
        if not isinstance(episode, dict) or not isinstance(episode.get("id"), str):
            errors.append("каждый эпизод должен иметь id")
            continue
        if episode["id"] in seen:
            errors.append(f"повторяющийся id эпизода: {episode['id']}")
        seen.add(episode["id"])
        scenes = episode.get("scenes")
        if not isinstance(scenes, list) or not scenes:
            errors.append(f"эпизод {episode['id']} не содержит сцен")
            continue
        for scene in scenes:
            if not isinstance(scene, dict) or not isinstance(scene.get("id"), str):
                errors.append(f"эпизод {episode['id']} содержит сцену без id")
                continue
            cues = scene.get("avatar_cues") if isinstance(scene.get("avatar_cues"), list) else []
            cue_ids = {
                cue.get("id") for cue in cues
                if isinstance(cue, dict) and isinstance(cue.get("id"), str)
            }
            beats = scene.get("teaching_beats") if isinstance(scene.get("teaching_beats"), list) else []
            beat_ids: set[str] = set()
            for beat in beats:
                if not isinstance(beat, dict) or not isinstance(beat.get("id"), str):
                    errors.append(f"сцена {scene['id']} содержит учебный шаг без id")
                    continue
                if beat["id"] in beat_ids:
                    errors.append(f"повторяющийся id учебного шага в сцене {scene['id']}: {beat['id']}")
                beat_ids.add(beat["id"])
                for cue_id in beat.get("avatar_cue_ids", []):
                    if cue_id not in cue_ids:
                        errors.append(f"учебный шаг {beat['id']} ссылается на неизвестную реплику {cue_id}")
            for cue in cues:
                if not isinstance(cue, dict):
                    continue
                beat_id = cue.get("beat_id")
                if beat_id and beats and beat_id not in beat_ids:
                    errors.append(f"реплика {cue.get('id')} ссылается на неизвестный учебный шаг {beat_id}")
            block = scene.get("block") if isinstance(scene.get("block"), dict) else {}
            content = block.get("content") if isinstance(block.get("content"), dict) else {}
            slides = content.get("slides") if block.get("component") == "Presentation" and isinstance(content.get("slides"), list) else []
            if slides and len(beats) != len(slides):
                errors.append(f"сцена {scene['id']}: каждый слайд Presentation должен иметь учебный шаг")
    return errors
