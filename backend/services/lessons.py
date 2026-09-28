from copy import deepcopy
from datetime import datetime, timezone
from time import monotonic
from typing import Any, Awaitable, Callable

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ai.planner import build_topic_contract, select_lesson_shape
from errors import ApplicationError
from lesson_contracts import (
    adapt_legacy_blocks,
    flatten_lesson_document,
    normalize_lesson_document,
    validate_lesson_document,
)
from models import (
    AvatarProfile,
    GeneratedLesson,
    LessonAsset,
    LessonAttempt,
    LessonVersion,
    Progress,
    Section,
    Student,
    StudentTopicAccess,
    Subject,
    Teacher,
    Topic,
    TopicSkill,
)
from objectives import quality_report
from services.catalog import clear_subject_outline_cache_for_topic
from services.progress import serialize_progress

LessonGenerator = Callable[..., Awaitable[list[dict[str, Any]]]]
LESSON_MANIFEST_CACHE_TTL_SEC = 120
STUDENT_MANIFEST_STATE_CACHE_TTL_SEC = 30
_lesson_manifest_cache: dict[int, tuple[float, dict[str, Any]]] = {}
_student_manifest_state_cache: dict[tuple[int, int], tuple[float, dict[str, Any]]] = {}


class LessonServiceError(ApplicationError):
    pass


def clear_lesson_manifest_cache(topic_id: int | None = None) -> None:
    if topic_id is None:
        _lesson_manifest_cache.clear()
        _student_manifest_state_cache.clear()
    else:
        _lesson_manifest_cache.pop(topic_id, None)
        for key in [
            cache_key
            for cache_key in _student_manifest_state_cache
            if cache_key[1] == topic_id
        ]:
            _student_manifest_state_cache.pop(key, None)


def clear_student_manifest_state_cache(student_id: int, topic_id: int | None = None) -> None:
    if topic_id is None:
        for key in [
            cache_key
            for cache_key in _student_manifest_state_cache
            if cache_key[0] == student_id
        ]:
            _student_manifest_state_cache.pop(key, None)
        return
    _student_manifest_state_cache.pop((student_id, topic_id), None)


def cached_lesson_manifest(topic_id: int) -> dict[str, Any] | None:
    cached = _lesson_manifest_cache.get(topic_id)
    if cached is None:
        return None
    expires_at, payload = cached
    if expires_at <= monotonic():
        _lesson_manifest_cache.pop(topic_id, None)
        return None
    return deepcopy(payload)


def cached_student_manifest_state(student_id: int, topic_id: int) -> dict[str, Any] | None:
    cached = _student_manifest_state_cache.get((student_id, topic_id))
    if cached is None:
        return None
    expires_at, payload = cached
    if expires_at <= monotonic():
        _student_manifest_state_cache.pop((student_id, topic_id), None)
        return None
    return deepcopy(payload)


def remember_lesson_manifest(topic_id: int, payload: dict[str, Any]) -> None:
    _lesson_manifest_cache[topic_id] = (
        monotonic() + LESSON_MANIFEST_CACHE_TTL_SEC,
        deepcopy(payload),
    )


def remember_student_manifest_state(student_id: int, topic_id: int, payload: dict[str, Any]) -> None:
    _student_manifest_state_cache[(student_id, topic_id)] = (
        monotonic() + STUDENT_MANIFEST_STATE_CACHE_TTL_SEC,
        deepcopy(payload),
    )


async def clear_lesson_manifest_cache_for_version(
    lesson_version_id: int | None,
    db: AsyncSession,
) -> None:
    if lesson_version_id is None:
        return
    topic_id = await db.scalar(
        select(GeneratedLesson.topic_id).join(LessonVersion, LessonVersion.lesson_id == GeneratedLesson.id).where(LessonVersion.id == lesson_version_id)
    )
    if isinstance(topic_id, int):
        clear_lesson_manifest_cache(topic_id)


async def get_lesson_or_error(lesson_id: int, db: AsyncSession) -> GeneratedLesson:
    lesson = await db.get(GeneratedLesson, lesson_id)
    if lesson is None:
        raise LessonServiceError(status_code=404, detail="Урок не найден")
    return lesson


def serialize_lesson(lesson: GeneratedLesson) -> dict[str, Any]:
    lesson_document = getattr(lesson, "_lesson_document", None)
    if not isinstance(lesson_document, dict):
        lesson_document = adapt_legacy_blocks(lesson.blocks or [], lesson.lesson_metadata or {})
    return {
        "id": lesson.id,
        "topic_id": lesson.topic_id,
        "blocks": getattr(lesson, "_served_blocks", lesson.blocks or []),
        "lesson_metadata": getattr(lesson, "_served_metadata", lesson.lesson_metadata or {}),
        "status": lesson.status,
        "generated_at": lesson.generated_at,
        "published_at": lesson.published_at,
        "published_by": lesson.published_by,
        "model_used": lesson.model_used,
        "active_version_id": getattr(lesson, "_served_version_id", getattr(lesson, "active_version_id", None)),
        "published_version_id": getattr(lesson, "published_version_id", None),
        "has_unpublished_changes": bool(getattr(lesson, "published_version_id", None) and lesson.active_version_id != lesson.published_version_id),
        "lesson_document": lesson_document,
    }


async def attach_lesson_document(
    lesson: GeneratedLesson,
    db: AsyncSession,
    *,
    version_document: dict[str, Any] | None = None,
    hydrate_assets: bool = True,
    selected_version_id: int | None = None,
) -> dict[str, Any]:
    version = None
    version_id = selected_version_id or getattr(lesson, "active_version_id", None)
    if version_document is None and version_id:
        version = await db.get(LessonVersion, version_id)
    source_document = version_document if version_document is not None else (
        version.lesson_document if version is not None else None
    )
    document = deepcopy(normalize_lesson_document(
        source_document,
        lesson.blocks or [],
        lesson.lesson_metadata or {},
    ))
    profile_id = (document.get("avatar") or {}).get("profile_id")
    if profile_id is None and selected_version_id is None:
        profile_id = (lesson.lesson_metadata or {}).get("avatar_profile_id")
    if isinstance(profile_id, int):
        profile = await db.get(AvatarProfile, profile_id)
        if profile is not None and profile.is_active:
            document.setdefault("avatar", {}).update({
                "profile_id": profile.id,
                "profile_name": profile.name,
                "preview_image_url": profile.preview_image_url,
            })
    if hydrate_assets and version_id is not None:
        assets = (await db.scalars(select(LessonAsset).where(
            LessonAsset.lesson_version_id == version_id,
            LessonAsset.status == "ready",
        ).order_by(LessonAsset.created_at.desc()))).all()
        assets_by_scene: dict[str, list[LessonAsset]] = {}
        for asset in assets:
            if asset.scene_id:
                assets_by_scene.setdefault(asset.scene_id, []).append(asset)
        for episode in document.get("episodes", []):
            for scene in episode.get("scenes", []):
                scene_assets = assets_by_scene.get(scene.get("id"), [])
                if not scene_assets:
                    continue
                scene["assets"] = [
                    {
                        "id": asset.id,
                        "kind": asset.kind,
                        # Закрытое видео аватара — через сервер, он перенаправит на подписанную ссылку.
                        "url": f"/api/avatar/assets/{asset.id}/stream" if str(asset.source_url).startswith("storage:") else asset.source_url,
                        "mime_type": asset.mime_type,
                        "duration_ms": asset.duration_ms,
                        "poster_url": (asset.metadata_json or {}).get("thumbnail_url"),
                        "scene_id": asset.scene_id,
                        "beat_id": (asset.metadata_json or {}).get("beat_id"),
                        "slide_id": (asset.metadata_json or {}).get("slide_id"),
                        "cue_id": (asset.metadata_json or {}).get("cue_id"),
                        "pedagogical_role": (asset.metadata_json or {}).get("pedagogical_role"),
                        "placement": (asset.metadata_json or {}).get("placement"),
                    }
                    for asset in scene_assets
                    if asset.source_url
                ]
                avatar_assets = [
                    asset for asset in scene_assets if asset.kind == "avatar_video" and asset.source_url
                ]
                for cue in scene.get("avatar_cues", []):
                    avatar_asset = next((
                        asset for asset in avatar_assets
                        if (asset.metadata_json or {}).get("cue_id") == cue.get("id")
                    ), None)
                    if avatar_asset is None:
                        avatar_asset = next((
                            asset for asset in avatar_assets
                            if not (asset.metadata_json or {}).get("cue_id")
                        ), None)
                    if avatar_asset is not None:
                        cue["video_asset_id"] = avatar_asset.id
                        cue["video_url"] = f"/api/avatar/assets/{avatar_asset.id}/stream"
                        cue["poster_url"] = (avatar_asset.metadata_json or {}).get("thumbnail_url")
    lesson._lesson_document = document
    return document


async def set_lesson_avatar_profile(
    lesson_id: int,
    profile_id: int,
    db: AsyncSession,
) -> GeneratedLesson:
    lesson = await get_lesson_or_error(lesson_id, db)
    profile = await db.get(AvatarProfile, profile_id)
    if profile is None or not profile.is_active:
        raise LessonServiceError(status_code=404, detail="Профиль аватара не найден")
    await preserve_published_version(lesson, db)
    previous_version_id = lesson.active_version_id
    document = await attach_lesson_document(lesson, db, hydrate_assets=False)
    metadata = dict(lesson.lesson_metadata or {})
    metadata["avatar_profile_id"] = profile.id
    lesson.lesson_metadata = metadata
    document.setdefault("avatar", {}).update({"profile_id": profile.id, "profile_name": profile.name,
                                              "preview_image_url": profile.preview_image_url})
    version = await persist_lesson_version(lesson, document, db)
    await carry_forward_anchored_assets(previous_version_id, version, document, db)
    clear_lesson_manifest_cache(lesson.topic_id)
    await db.commit()
    await db.refresh(lesson)
    await attach_lesson_document(lesson, db, hydrate_assets=False)
    return lesson


async def persist_lesson_version(
    lesson: GeneratedLesson,
    document: dict[str, Any],
    db: AsyncSession,
    *,
    status: str = "ready",
) -> LessonVersion | None:
    """Create an immutable version when running against a real AsyncSession.

    Lightweight service fakes used by unit tests intentionally do not expose
    flush(); metadata and the transient document still exercise compatibility.
    """
    lesson._lesson_document = document
    if not hasattr(db, "flush"):
        return None
    errors = validate_lesson_document(document)
    if errors:
        raise LessonServiceError(status_code=422, detail={"message": "Некорректный lesson_document", "errors": errors})
    await db.flush()
    latest = await db.scalar(
        select(func.max(LessonVersion.version_number)).where(LessonVersion.lesson_id == lesson.id)
    )
    blueprint = deepcopy(lesson.lesson_metadata or {})
    if hasattr(db, "scalars"):
        links = (await db.scalars(select(TopicSkill).where(
            TopicSkill.topic_id == lesson.topic_id, TopicSkill.role == "outcome",
            TopicSkill.objective_id.is_not(None)))).all()
        skill_map: dict[str, list[int]] = {}
        for link in links:
            skill_map.setdefault(link.objective_id, []).append(link.skill_id)
        blueprint["objective_skill_map"] = skill_map
    version = LessonVersion(
        lesson_id=lesson.id,
        version_number=int(latest or 0) + 1,
        schema_version=2,
        status=status,
        blueprint=blueprint,
        lesson_document=document,
        generator_config={"provider_contract": "lesson-experience-v2"},
        model_used=lesson.model_used,
    )
    db.add(version)
    await db.flush()
    lesson.active_version_id = version.id
    return version


async def carry_forward_anchored_assets(
    source_version_id: int | None,
    target_version: LessonVersion | None,
    document: dict[str, Any],
    db: AsyncSession,
) -> None:
    """Keep generated content only when its semantic anchor still exists."""
    if not source_version_id or target_version is None or source_version_id == target_version.id:
        return
    valid_scenes: set[str] = set()
    valid_beats: set[str] = set()
    valid_cues: set[str] = set()
    for episode in document.get("episodes", []):
        if not isinstance(episode, dict):
            continue
        for scene in episode.get("scenes", []):
            if not isinstance(scene, dict):
                continue
            if isinstance(scene.get("id"), str):
                valid_scenes.add(scene["id"])
            valid_beats.update(
                beat["id"] for beat in scene.get("teaching_beats", [])
                if isinstance(beat, dict) and isinstance(beat.get("id"), str)
            )
            valid_cues.update(
                cue["id"] for cue in scene.get("avatar_cues", [])
                if isinstance(cue, dict) and isinstance(cue.get("id"), str)
            )
    assets = (await db.scalars(select(LessonAsset).where(
        LessonAsset.lesson_version_id == source_version_id,
        LessonAsset.status == "ready",
    ))).all()
    for asset in assets:
        metadata = dict(asset.metadata_json or {})
        if asset.scene_id and asset.scene_id not in valid_scenes:
            continue
        if metadata.get("beat_id") and metadata["beat_id"] not in valid_beats:
            continue
        if metadata.get("cue_id") and metadata["cue_id"] not in valid_cues:
            continue
        db.add(LessonAsset(
            lesson_version_id=target_version.id,
            generation_job_id=asset.generation_job_id,
            scene_id=asset.scene_id,
            kind=asset.kind,
            provider=asset.provider,
            provider_asset_id=asset.provider_asset_id,
            storage_bucket=asset.storage_bucket,
            storage_path=asset.storage_path,
            source_url=asset.source_url,
            mime_type=asset.mime_type,
            size_bytes=asset.size_bytes,
            duration_ms=asset.duration_ms,
            status=asset.status,
            metadata_json=metadata,
        ))


def lesson_needs_quality_refresh(lesson: GeneratedLesson) -> bool:
    metadata = lesson.lesson_metadata or {}
    report = metadata.get("quality_report")
    if not isinstance(metadata.get("objectives"), list) or not isinstance(report, dict):
        return True
    # Неопубликуемый урок с отчётом по старым правилам: проверки могли стать точнее — пересчитать.
    from objectives import QUALITY_CHECKS_VERSION

    return report.get("publishable") is False and report.get("checks_version") != QUALITY_CHECKS_VERSION


def lesson_topic_contract(lesson: GeneratedLesson, topic: Topic | None = None) -> dict[str, Any] | None:
    contract = (lesson.lesson_metadata or {}).get("topic_contract")
    result = dict(contract) if isinstance(contract, dict) else {}
    lesson_type = topic.lesson_type if topic is not None else (lesson.lesson_metadata or {}).get("lesson_type")
    if lesson_type:
        result["lesson_type"] = lesson_type
        if result.get("lesson_shape") or lesson_type in {"assessment", "review", "reflection", "project"}:
            result["lesson_shape"] = select_lesson_shape(result.get("volume", "standard"), result.get("learning_focus", "concept"), lesson_type)
    return result or None


async def preserve_published_version(lesson: GeneratedLesson, db: AsyncSession) -> None:
    """Snapshot legacy published lessons before their first draft edit."""
    if lesson.status != "published" or getattr(lesson, "published_version_id", None):
        return
    if not getattr(lesson, "active_version_id", None):
        await persist_lesson_version(
            lesson, adapt_legacy_blocks(lesson.blocks or [], lesson.lesson_metadata or {}),
            db, status="published",
        )
    lesson.published_version_id = lesson.active_version_id
    if lesson.published_version_id is not None and isinstance(db, AsyncSession):
        # Legacy rows had no version to pin at the time of their attempt. Capture
        # the old publication before any draft replaces its mutable block fields.
        await db.execute(update(Progress).where(
            Progress.topic_id == lesson.topic_id, Progress.lesson_version_id.is_(None),
        ).values(lesson_version_id=lesson.published_version_id))
        await db.execute(update(LessonAttempt).where(
            LessonAttempt.topic_id == lesson.topic_id, LessonAttempt.lesson_version_id.is_(None),
        ).values(lesson_version_id=lesson.published_version_id))


async def refresh_lesson_topic_draft(topic: Topic, db: AsyncSession) -> None:
    """Topic settings change the teacher draft, never an existing publication."""
    lesson = await db.scalar(select(GeneratedLesson).where(GeneratedLesson.topic_id == topic.id))
    if lesson is None:
        return
    await preserve_published_version(lesson, db)
    previous_version_id = lesson.active_version_id
    document = await attach_lesson_document(lesson, db, hydrate_assets=False)
    metadata = dict(lesson.lesson_metadata or {})
    metadata.update({
        "topic_name": topic.name, "lesson_type": topic.lesson_type,
        "learning_objectives": topic.learning_objectives,
        "covered_topic_ids": topic.covered_topic_ids or [],
        "source_assessment_topic_id": topic.source_assessment_topic_id,
        "topic_hours": topic.hours, "skills": topic.skills or [],
    })
    lesson.lesson_metadata = metadata
    contract = lesson_topic_contract(lesson, topic)
    if contract is not None:
        metadata["topic_contract"] = contract
    report = await refresh_quality_contract(lesson, db)
    document["title"] = topic.name
    document["objectives"] = report["objectives"]
    version = await persist_lesson_version(lesson, document, db)
    await carry_forward_anchored_assets(previous_version_id, version, document, db)
    clear_lesson_manifest_cache(topic.id)


async def ensure_lesson_media_draft(version_id: int, db: AsyncSession) -> int:
    """Media writes use a draft, including jobs completed after publication."""
    version = await db.get(LessonVersion, version_id)
    if version is None:
        raise LessonServiceError(status_code=404, detail="Версия урока не найдена")
    lesson = await get_lesson_or_error(version.lesson_id, db)
    topic = await db.get(Topic, lesson.topic_id)
    if topic is not None and getattr(topic, "archived_at", None):
        raise LessonServiceError(status_code=409, detail="Сначала восстановите тему из архива")
    if version_id != lesson.active_version_id:
        raise LessonServiceError(status_code=409, detail="Черновик урока изменился. Обновите редактор перед созданием медиа.")
    if version.status != "published" and version_id != lesson.published_version_id and lesson.status != "published":
        return version_id
    # Once a separate draft exists, further media can be attached to it.
    if lesson.published_version_id and version_id != lesson.published_version_id and version.status != "published":
        return version_id
    await preserve_published_version(lesson, db)
    document = deepcopy(version.lesson_document)
    target = await persist_lesson_version(lesson, document, db)
    if target is None:
        raise LessonServiceError(status_code=409, detail="Не удалось создать черновик для медиа")
    await carry_forward_anchored_assets(version_id, target, document, db)
    clear_lesson_manifest_cache(lesson.topic_id)
    await clear_subject_outline_cache_for_topic(lesson.topic_id, db)
    return target.id


async def student_version_payload(
    payload: dict[str, Any], progress: dict[str, Any] | None, db: AsyncSession,
) -> dict[str, Any]:
    """Resolve a student's attempt independently of the shared published cache."""
    version_id = (progress or {}).get("lesson_version_id") or payload.get("published_version_id")
    if not version_id or version_id == payload.get("active_version_id"):
        return deepcopy(payload)
    version = await db.get(LessonVersion, version_id)
    if version is None or version.lesson_id != payload["id"]:
        raise LessonServiceError(status_code=409, detail="Версия урока недоступна. Обновите страницу.")
    result = deepcopy(payload)
    result.update({
        "active_version_id": version.id,
        "lesson_document": deepcopy(version.lesson_document),
        "blocks": flatten_lesson_document(version.lesson_document),
        "lesson_metadata": deepcopy(version.blueprint or {}),
        "model_used": version.model_used,
        "has_unpublished_changes": False,
    })
    return result


def require_available_student_lesson(archived: bool, progress: dict[str, Any] | None, published: bool = True) -> None:
    if (archived or not published) and not (progress and progress.get("status") == "completed"):
        raise LessonServiceError(status_code=404, detail="Занятие убрано из программы")


def require_open_topic(access_state: str | None) -> None:
    """Темы открываются строго по порядку: закрытую нельзя открыть и по прямой ссылке."""
    if access_state == "locked":
        raise LessonServiceError(status_code=403, detail="Тема пока закрыта: сначала пройдите предыдущую тему.")


async def _refreshed_access_state(student_id: int, topic_id: int, db: AsyncSession) -> str | None:
    from services.curriculum_graph import refresh_student_access

    await refresh_student_access(student_id, db)
    # Сохраняем пересчёт: иначе строки доступа откатываются, а блокировка ученика держится до конца запроса.
    await db.commit()
    return await db.scalar(select(StudentTopicAccess.state).where(
        StudentTopicAccess.student_id == student_id, StudentTopicAccess.topic_id == topic_id,
    ))


async def create_lesson_draft(topic_id: int, teacher_id: int, db: AsyncSession) -> GeneratedLesson:
    topic = await db.get(Topic, topic_id)
    if topic is None:
        raise LessonServiceError(status_code=404, detail="Тема не найдена")
    if getattr(topic, "archived_at", None):
        raise LessonServiceError(status_code=409, detail="Сначала восстановите тему из архива")
    lesson = await db.scalar(select(GeneratedLesson).where(GeneratedLesson.topic_id == topic_id))
    if lesson is not None:
        await attach_lesson_document(lesson, db, hydrate_assets=False)
        return lesson
    lesson = GeneratedLesson(topic_id=topic_id, blocks=[], status="draft", lesson_metadata={
        "topic_name": topic.name, "lesson_type": topic.lesson_type,
        "learning_objectives": topic.learning_objectives, "teacher_id": teacher_id,
    })
    db.add(lesson)
    await refresh_quality_contract(lesson, db)
    await db.commit()
    await db.refresh(lesson)
    clear_lesson_manifest_cache(topic_id)
    await clear_subject_outline_cache_for_topic(topic_id, db)
    return lesson


async def get_lesson_by_topic(
    topic_id: int,
    role: str | None,
    db: AsyncSession,
    student_id: int | None = None,
) -> GeneratedLesson:
    if role == "student":
        if student_id is None:
            raise LessonServiceError(status_code=422, detail="student_id обязателен для ученика")
        manifest = await get_student_lesson_manifest(topic_id=topic_id, student_id=student_id, db=db)
        lesson = await db.scalar(select(GeneratedLesson).where(GeneratedLesson.topic_id == topic_id))
        if lesson is None:
            raise LessonServiceError(status_code=404, detail="Урок не найден")
        payload = manifest["lesson"]
        lesson._served_blocks = payload["blocks"]
        lesson._served_metadata = payload["lesson_metadata"]
        lesson._served_version_id = payload["active_version_id"]
        await attach_lesson_document(lesson, db, version_document=payload["lesson_document"],
                                     selected_version_id=payload["active_version_id"])
        return lesson
    statement = select(GeneratedLesson).where(GeneratedLesson.topic_id == topic_id)
    if role == "student":
        statement = statement.where(GeneratedLesson.status == "published")
    lesson = await db.scalar(statement)
    if lesson is None:
        detail = "Опубликованный урок пока не готов" if role == "student" else "Урок не найден"
        raise LessonServiceError(status_code=404, detail=detail)
    if lesson_needs_quality_refresh(lesson):
        await refresh_quality_contract(lesson, db)
    await attach_lesson_document(lesson, db)
    return lesson


async def get_student_lesson_manifest(
    *,
    topic_id: int,
    student_id: int,
    db: AsyncSession,
) -> dict[str, Any]:
    cached = cached_lesson_manifest(topic_id)
    if cached is not None:
        student_state = cached_student_manifest_state(student_id, topic_id)
        # Кэш процесса мог не узнать, что тема уже открылась (другой воркер): «закрыто» перепроверяем по базе.
        if student_state is not None and student_state.get("access_state") != "locked":
            if cached["subject_grade"] != student_state["student_grade"]:
                raise LessonServiceError(status_code=404, detail="Предмет недоступен для класса ученика")
            require_available_student_lesson(cached.get("archived", False), student_state.get("progress"), cached.get("published", True))
            if cached["has_graph"]:
                require_open_topic(student_state.get("access_state"))
            return {
                "lesson": await student_version_payload(cached["lesson"], student_state.get("progress"), db),
                "progress": student_state.get("progress"),
            }
        row = (await db.execute(
            select(
                Student.grade.label("student_grade"),
                StudentTopicAccess.state.label("access_state"),
                Progress,
            )
            .select_from(Student)
            .outerjoin(
                Progress,
                (Progress.student_id == student_id)
                & (Progress.topic_id == topic_id),
            )
            .outerjoin(
                StudentTopicAccess,
                (StudentTopicAccess.topic_id == topic_id)
                & (StudentTopicAccess.student_id == student_id),
            )
            .where(Student.id == student_id)
        )).first()
        if row is None:
            raise LessonServiceError(status_code=404, detail="Ученик не найден")
        student_grade, access_state, progress = row
        if cached["subject_grade"] != student_grade:
            raise LessonServiceError(status_code=404, detail="Предмет недоступен для класса ученика")
        if cached["has_graph"] and access_state is None:
            access_state = await _refreshed_access_state(student_id, topic_id, db)
        progress_payload = serialize_progress(progress) if progress is not None else None
        remember_student_manifest_state(student_id, topic_id, {
            "student_grade": student_grade,
            "access_state": access_state,
            "progress": progress_payload,
        })
        require_available_student_lesson(cached.get("archived", False), progress_payload, cached.get("published", True))
        if cached["has_graph"]:
            require_open_topic(access_state)
        return {
            "lesson": await student_version_payload(cached["lesson"], progress_payload, db),
            "progress": progress_payload,
        }

    graph_exists = select(TopicSkill.topic_id).where(TopicSkill.topic_id == topic_id).exists()
    row = (await db.execute(
        select(
            GeneratedLesson,
            Subject.grade.label("subject_grade"),
            Student.grade.label("student_grade"),
            StudentTopicAccess.state.label("access_state"),
            graph_exists.label("has_graph"),
            LessonVersion.lesson_document.label("version_document"),
            Progress,
        )
        .join(Topic, Topic.id == GeneratedLesson.topic_id)
        .join(Section, Section.id == Topic.section_id)
        .join(Subject, Subject.id == Section.subject_id)
        .join(Student, Student.id == student_id)
        .outerjoin(LessonVersion, LessonVersion.id == func.coalesce(GeneratedLesson.published_version_id, GeneratedLesson.active_version_id))
        .outerjoin(
            Progress,
            (Progress.student_id == student_id)
            & (Progress.topic_id == topic_id),
        )
        .outerjoin(
            StudentTopicAccess,
            (StudentTopicAccess.topic_id == topic_id)
            & (StudentTopicAccess.student_id == student_id),
        )
        .where(
            GeneratedLesson.topic_id == topic_id,
            or_(GeneratedLesson.status == "published", Progress.status == "completed"),
        )
    )).first()
    if row is None:
        raise LessonServiceError(status_code=404, detail="Опубликованный урок пока не готов")

    lesson, subject_grade, student_grade, access_state, has_graph, version_document, progress = row
    if subject_grade != student_grade:
        raise LessonServiceError(status_code=404, detail="Предмет недоступен для класса ученика")
    if has_graph and access_state is None:
        access_state = await _refreshed_access_state(student_id, topic_id, db)

    topic = await db.get(Topic, topic_id)
    archived = bool(getattr(topic, "archived_at", None))
    progress_payload = serialize_progress(progress) if progress is not None else None
    require_available_student_lesson(archived, progress_payload, lesson.status == "published")
    if has_graph:
        require_open_topic(access_state)
    # Never serve mutable draft blocks or metadata to a student.
    published_id = getattr(lesson, "published_version_id", None) or lesson.active_version_id
    await attach_lesson_document(lesson, db, version_document=version_document,
                                 hydrate_assets=False, selected_version_id=published_id)
    serialized_lesson = serialize_lesson(lesson)
    if published_id:
        version = await db.get(LessonVersion, published_id)
        if version is not None:
            serialized_lesson.update({
                "active_version_id": version.id,
                "lesson_metadata": deepcopy(version.blueprint or {}),
                "blocks": flatten_lesson_document(version.lesson_document),
                "has_unpublished_changes": False,
            })
    if topic is not None:
        for key, value in {
            "lesson_type": topic.lesson_type,
            "covered_topic_ids": getattr(topic, "covered_topic_ids", None) or [],
            "source_assessment_topic_id": getattr(topic, "source_assessment_topic_id", None),
        }.items():
            serialized_lesson["lesson_metadata"].setdefault(key, value)
    remember_lesson_manifest(topic_id, {
        "lesson": serialized_lesson,
        "subject_grade": subject_grade,
        "has_graph": has_graph,
        "archived": archived,
        "published": lesson.status == "published",
    })
    progress_payload = serialize_progress(progress) if progress is not None else None
    remember_student_manifest_state(student_id, topic_id, {
        "student_grade": student_grade,
        "access_state": access_state,
        "progress": progress_payload,
    })
    return {
        "lesson": await student_version_payload(serialized_lesson, progress_payload, db),
        "progress": progress_payload,
    }


_UNSET: Any = object()


async def with_textbook_warnings(report: dict[str, Any], db: AsyncSession, topic: Any, context: Any = _UNSET,
                                 subject_name: str | None = None) -> dict[str, Any]:
    """Добавить к проверке качества проверку по учебнику и по профилю предмета (например, у истории —
    хронология, источник, причины и последствия)."""
    from ai.subject_profiles import subject_warnings, textbook_source_warnings
    from ai.textbook_grounding import textbook_warnings
    from services.textbook_context import load_textbook_context, subject_has_textbook

    if context is _UNSET:
        context = await load_textbook_context(db, topic)
    available = bool(context) or await subject_has_textbook(db, topic)
    quality = report["quality_report"]
    quality["warnings"] = (list(quality.get("warnings") or []) + textbook_warnings(report["normalized_blocks"], context, available)
                           + subject_warnings(report["normalized_blocks"], subject_name, getattr(topic, "lesson_type", "study"))
                           + textbook_source_warnings(report["normalized_blocks"], subject_name, context))
    return report


async def refresh_quality_contract(lesson: GeneratedLesson, db: AsyncSession) -> dict[str, Any]:
    topic = await db.get(Topic, lesson.topic_id)
    if topic is None:
        raise LessonServiceError(status_code=404, detail="Тема урока не найдена")
    report = await with_textbook_warnings(quality_report(
        lesson.blocks or [],
        topic.learning_objectives,
        topic_contract=lesson_topic_contract(lesson, topic),
    ), db, topic, subject_name=(lesson.lesson_metadata or {}).get("subject_name"))
    metadata = dict(lesson.lesson_metadata or {})
    metadata["learning_objectives"] = topic.learning_objectives
    metadata["objectives"] = report["objectives"]
    metadata["quality_report"] = report["quality_report"]
    lesson.lesson_metadata = metadata
    lesson.blocks = report["normalized_blocks"]
    return report


async def update_lesson_blocks(
    lesson_id: int,
    blocks: list[dict[str, Any]],
    db: AsyncSession,
) -> GeneratedLesson:
    lesson = await get_lesson_or_error(lesson_id, db)
    await preserve_published_version(lesson, db)
    previous_version_id = getattr(lesson, "active_version_id", None)
    quality = await refresh_quality_contract_for_blocks(lesson, blocks, db)
    metadata = dict(lesson.lesson_metadata or {})
    metadata["learning_objectives"] = "; ".join(item["text"] for item in quality["objectives"])
    metadata["objectives"] = quality["objectives"]
    metadata["quality_report"] = quality["quality_report"]
    lesson.lesson_metadata = metadata
    lesson.blocks = quality["normalized_blocks"]
    document = adapt_legacy_blocks(lesson.blocks, metadata)
    version = await persist_lesson_version(
        lesson,
        document,
        db,
        status="ready",
    )
    await carry_forward_anchored_assets(previous_version_id, version, document, db)
    # Editing replaces only the draft. The published pointer stays unchanged.
    if lesson.status != "published":
        lesson.status = "draft"
    clear_lesson_manifest_cache(lesson.topic_id)
    await clear_subject_outline_cache_for_topic(lesson.topic_id, db)
    await db.commit()
    await db.refresh(lesson)
    return lesson


async def refresh_quality_contract_for_blocks(
    lesson: GeneratedLesson,
    blocks: list[dict[str, Any]],
    db: AsyncSession,
) -> dict[str, Any]:
    topic = await db.get(Topic, lesson.topic_id)
    if topic is None:
        raise LessonServiceError(status_code=404, detail="Тема урока не найдена")
    return await with_textbook_warnings(quality_report(
        blocks,
        topic.learning_objectives,
        topic_contract=lesson_topic_contract(lesson, topic),
    ), db, topic, subject_name=(lesson.lesson_metadata or {}).get("subject_name"))


async def get_lesson_quality(lesson_id: int, db: AsyncSession) -> dict[str, Any]:
    lesson = await get_lesson_or_error(lesson_id, db)
    topic = await db.get(Topic, lesson.topic_id)
    if topic is None:
        raise LessonServiceError(status_code=404, detail="Тема урока не найдена")
    return await with_textbook_warnings(quality_report(
        lesson.blocks or [],
        topic.learning_objectives,
        topic_contract=lesson_topic_contract(lesson, topic),
    ), db, topic, subject_name=(lesson.lesson_metadata or {}).get("subject_name"))


async def unpublish_lesson(lesson_id: int, db: AsyncSession) -> GeneratedLesson:
    lesson = await get_lesson_or_error(lesson_id, db)
    lesson.status = "draft"
    lesson.published_version_id = None
    lesson.published_at = None
    lesson.published_by = None
    clear_lesson_manifest_cache(lesson.topic_id)
    await clear_subject_outline_cache_for_topic(lesson.topic_id, db)
    # На карте ученика урок сразу «опубликован» или «готовится», а не через срок кэша.
    from services.curriculum_graph import clear_curriculum_map_cache
    clear_curriculum_map_cache()
    await db.commit()
    await db.refresh(lesson)
    return lesson


async def delete_lesson_record(lesson_id: int, db: AsyncSession) -> dict[str, str]:
    lesson = await get_lesson_or_error(lesson_id, db)
    if lesson.status == "published" or lesson.published_version_id:
        raise LessonServiceError(status_code=409, detail="Опубликованное занятие нельзя удалить вместе с историей. Используйте «Убрать из программы».")
    has_history = await db.scalar(select(or_(
        select(Progress.id).where(Progress.topic_id == lesson.topic_id).exists(),
        select(LessonAttempt.id).where(LessonAttempt.topic_id == lesson.topic_id).exists(),
    )))
    if has_history:
        raise LessonServiceError(status_code=409, detail="У занятия есть результаты учеников. Используйте «Убрать из программы», чтобы сохранить историю.")
    topic_id = lesson.topic_id
    await db.delete(lesson)
    clear_lesson_manifest_cache(topic_id)
    await clear_subject_outline_cache_for_topic(topic_id, db)
    await db.commit()
    return {"message": "Урок удалён"}


async def generate_lesson_draft(
    topic_id: int,
    teacher_id: int,
    db: AsyncSession,
    lesson_generator: LessonGenerator | None = None,
    model_choice: str | None = None,
) -> GeneratedLesson:
    from llm import TASK_LESSON, resolve_route
    from llm.catalog import ModelChoiceError, resolve_lesson_choice

    try:
        model_route = resolve_lesson_choice(model_choice)
    except ModelChoiceError as exc:
        raise LessonServiceError(status_code=422, detail=str(exc)) from exc
    if await db.get(Teacher, teacher_id) is None:
        raise LessonServiceError(status_code=404, detail="Преподаватель не найден")

    row = (
        await db.execute(
            select(Topic, Section, Subject)
            .join(Section, Topic.section_id == Section.id)
            .join(Subject, Section.subject_id == Subject.id)
            .where(Topic.id == topic_id)
        )
    ).first()
    if row is None:
        raise LessonServiceError(status_code=404, detail="Тема не найдена")
    topic, _section, subject = row
    if getattr(topic, "archived_at", None):
        raise LessonServiceError(status_code=409, detail="Сначала восстановите тему из архива")
    resources = topic.resources
    covered_ids = getattr(topic, "covered_topic_ids", None) or []
    if covered_ids:
        covered = (await db.scalars(select(Topic).where(Topic.id.in_(covered_ids)))).all()
        resources = "\n".join(filter(None, [resources, "Изученные темы: " + "; ".join(
            f"{item.name}: {item.learning_objectives or ''}" for item in covered
        )]))

    from ai.generator import MODEL, classify_subject, generate_lesson, select_archetype
    from ai.textbook_grounding import lesson_textbook_metadata
    from services.textbook_context import load_textbook_context

    generator = lesson_generator or generate_lesson
    # Подтверждённые параграфы учебника — основа урока; нет их — урок как раньше, с пометкой.
    textbook = await load_textbook_context(db, topic)
    plan = build_topic_contract(
        topic_name=topic.name,
        subject_name=subject.name,
        learning_objectives=topic.learning_objectives,
        skills=topic.skills,
        resources=resources,
        grade=subject.grade,
        hours=topic.hours,
        lesson_type=topic.lesson_type,
        content_language=subject.instruction_language,
        textbook_grounded=bool(textbook) and any(
            str(section.get("text") or "").strip()
            or any(str(item.get("text") or "").strip() for item in section.get("items") or [])
            for section in textbook.get("sections") or []
        ),
    )
    try:
        generated = await generator(
            topic_name=topic.name,
            subject_name=subject.name,
            learning_objectives=topic.learning_objectives,
            skills=topic.skills,
            resources=resources,
            grade=subject.grade,
            hours=topic.hours,
            lesson_type=topic.lesson_type,
            content_language=subject.instruction_language,
            topic_contract=plan["topic_contract"],
            component_plan=plan["component_plan"],
            # Старые генераторы (и тестовые подмены) аргумент не знают.
            **({"model_route": model_route} if model_route else {}),
            **({"textbook": textbook} if textbook else {}),
        )
    except Exception as exc:
        raise LessonServiceError(
            status_code=502,
            detail=f"Не удалось сгенерировать урок: {exc}",
        ) from exc

    if isinstance(generated, dict) and generated.get("schema_version") == 2:
        lesson_document = generated
        blocks = flatten_lesson_document(generated)
    else:
        blocks = generated
        lesson_document = None
    intro = getattr(generated, "intro", None)

    lesson = await db.scalar(select(GeneratedLesson).where(GeneratedLesson.topic_id == topic.id))
    if lesson is None:
        lesson = GeneratedLesson(topic_id=topic.id)
        db.add(lesson)

    await preserve_published_version(lesson, db)
    quality = await with_textbook_warnings(quality_report(
        blocks,
        topic.learning_objectives,
        topic_contract=plan["topic_contract"],
    ), db, topic, textbook, subject.name)
    lesson.blocks = quality["normalized_blocks"]
    profile = classify_subject(subject.name)
    archetype = select_archetype(
        str(profile["family"]),
        topic.name,
        topic.lesson_type,
        topic.learning_objectives,
    )
    used_route = model_route or resolve_route(TASK_LESSON)
    lesson.lesson_metadata = {
        # Какая книга и какие параграфы легли в основу урока (без текста книги); None — урок без учебника.
        "textbook": lesson_textbook_metadata(textbook),
        "subject_name": subject.name,
        "subject_grade": subject.grade,
        "content_language": subject.instruction_language,
        "subject_family": profile["family"],
        "subject_family_label": profile["family_label"],
        "lesson_archetype": archetype,
        "teacher_review_required": profile["teacher_review_required"],
        "topic_name": topic.name,
        "lesson_type": topic.lesson_type,
        "generation_model": {"provider": used_route.provider, "model": used_route.model},
        "covered_topic_ids": covered_ids,
        "source_assessment_topic_id": getattr(topic, "source_assessment_topic_id", None),
        "topic_hours": topic.hours,
        "learning_objectives": topic.learning_objectives,
        "objectives": quality["objectives"],
        "topic_contract": plan["topic_contract"],
        "lesson_shape": plan["topic_contract"]["lesson_shape"],
        "block_budget": plan["topic_contract"]["block_budget"],
        "component_plan": plan["component_plan"],
        "quality_report": quality["quality_report"],
        "skills": topic.skills or [],
        "teacher_id": teacher_id,
    }
    if isinstance(intro, dict) and intro:
        lesson.lesson_metadata["intro"] = intro
    lesson_document = normalize_lesson_document(
        lesson_document,
        lesson.blocks,
        lesson.lesson_metadata,
    )
    if lesson_document.get("source") == "legacy_adapter":
        lesson_document["source"] = "openrouter_planner_v2"
    if lesson.status != "published":
        lesson.status = "draft"
    lesson.generated_at = datetime.now(timezone.utc)
    lesson.model_used = MODEL
    await persist_lesson_version(lesson, lesson_document, db, status="ready")
    clear_lesson_manifest_cache(topic.id)
    await clear_subject_outline_cache_for_topic(topic.id, db)
    await db.commit()
    await db.refresh(lesson)
    return lesson


async def publish_lesson(
    lesson_id: int,
    teacher_id: int,
    acknowledge_warnings: bool,
    db: AsyncSession,
    override_errors: bool = False,
) -> GeneratedLesson:
    if await db.get(Teacher, teacher_id) is None:
        raise LessonServiceError(status_code=404, detail="Преподаватель не найден")
    lesson = await get_lesson_or_error(lesson_id, db)
    topic = await db.get(Topic, lesson.topic_id)
    if topic is None:
        raise LessonServiceError(status_code=404, detail="Тема урока не найдена")

    if getattr(topic, "archived_at", None):
        raise LessonServiceError(status_code=409, detail="Сначала восстановите тему из архива")

    quality = quality_report(
        lesson.blocks or [],
        topic.learning_objectives,
        topic_contract=lesson_topic_contract(lesson, topic),
    )
    report = quality["quality_report"]
    overridden = not report["publishable"] and override_errors and report.get("overridable")
    if not report["publishable"] and not overridden:
        raise LessonServiceError(
            status_code=422,
            detail={
                "message": "Урок нельзя опубликовать: исправьте покрытие целей и ошибки ответов",
                "quality_report": quality,
            },
        )

    warnings = quality["quality_report"]["warnings"]
    if warnings and not acknowledge_warnings:
        raise LessonServiceError(
            status_code=422,
            detail={
                "message": "Подтвердите некритические предупреждения перед публикацией",
                "warnings": warnings,
            },
        )

    metadata = dict(lesson.lesson_metadata or {})
    metadata["learning_objectives"] = "; ".join(item["text"] for item in quality["objectives"])
    metadata["objectives"] = quality["objectives"]
    metadata["quality_report"] = quality["quality_report"]
    metadata["quality_review"] = {
        "teacher_id": teacher_id,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "acknowledged_warning_codes": [
            item.get("code") for item in warnings if isinstance(item, dict)
        ],
        # Недочёты, с которыми учитель ознакомился и всё равно опубликовал.
        "overridden_error_codes": [
            item.get("code") for item in report["errors"] if isinstance(item, dict)
        ] + (["objective_gaps"] if report.get("gaps") else []) if overridden else [],
    }
    lesson.blocks = quality["normalized_blocks"]
    lesson.lesson_metadata = metadata
    lesson.status = "published"
    lesson.published_at = datetime.now(timezone.utc)
    lesson.published_by = teacher_id
    active_version = None
    if getattr(lesson, "active_version_id", None):
        active_version = await db.get(LessonVersion, lesson.active_version_id)
    if active_version is not None:
        if active_version.status != "published":
            active_version.blueprint = {**deepcopy(metadata), "objective_skill_map": (active_version.blueprint or {}).get("objective_skill_map", {})}
            document = deepcopy(active_version.lesson_document)
            document["objectives"] = quality["objectives"]
            active_version.lesson_document = document
        active_version.status = "published"
        active_version.published_at = lesson.published_at
    else:
        await persist_lesson_version(
            lesson,
            adapt_legacy_blocks(lesson.blocks, metadata),
            db,
            status="published",
        )
    lesson.published_version_id = lesson.active_version_id
    clear_lesson_manifest_cache(lesson.topic_id)
    await clear_subject_outline_cache_for_topic(lesson.topic_id, db)
    # На карте ученика урок сразу «опубликован» или «готовится», а не через срок кэша.
    from services.curriculum_graph import clear_curriculum_map_cache
    clear_curriculum_map_cache()
    await db.commit()
    await db.refresh(lesson)
    return lesson
