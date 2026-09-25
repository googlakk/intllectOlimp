"""Educational media generation helpers.

Text lesson generation uses tool calls; educational visuals need the dedicated
image/video endpoints. Keep this small and HTTP-client injectable so tests never
touch the network.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from ._http import AsyncClient, HTTPError
from .base import LLMError
from .openrouter_provider import BASE_URL, TIMEOUT, OpenRouterProvider

DEFAULT_IMAGE_MODEL = "google/gemini-2.5-flash-image"
DEFAULT_VIDEO_MODEL = "google/veo-3.1"

# Медиа не объясняет текстом — объяснение уже есть в блоке урока. Оно
# делает идею видимой: показывает явление, место, устройство или момент,
# который трудно вообразить по словам.
VISUAL_INTENT_GUIDANCE = {
    "process": "capture the decisive moment of the process, or its before and after, so the change is seen and felt rather than described",
    "structure": "reveal the hidden inside or arrangement of the object through a cutaway, close-up or unusual viewpoint, using form, depth and colour instead of labels",
    "quantity": "make size, amount or ratio perceptible through concrete objects shown side by side at honest relative scale",
    "mistake": "stage a situation in which the intuitive expectation visibly fails, so the student notices the surprise",
    "cause_effect": "show cause and consequence inside one scene through composition, direction of movement and light",
    "source_context": "immerse the student in the place, era or world of the source: people, objects, setting and atmosphere",
}

DEFAULT_MEDIA_STYLE = (
    "tactile clay-and-paper editorial 3D illustration, warm soft light, cream and deep teal palette, "
    "rich but uncluttered detail"
)

NO_TEXT_RULE = (
    "Absolutely no text of any kind in the frame: no letters, words, labels, captions, callouts, named arrows, "
    "numbers, formulas, equations, units, charts, legends, speech bubbles, signs or watermarks. Surfaces that "
    "would normally carry writing (notebooks, boards, screens, signs, book pages) stay blank."
)


@dataclass
class ImageGenerationResult:
    model: str
    prompt: str
    media_type: str
    b64_json: str
    data_url: str
    url: str = ""
    usage: dict[str, Any] = field(default_factory=dict)


@dataclass
class VideoGenerationJob:
    id: str
    status: str
    model: str
    polling_url: str = ""
    generation_id: str = ""
    unsigned_urls: list[str] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)
    error: dict[str, Any] | None = None


@dataclass
class VideoContent:
    content: bytes
    media_type: str = "video/mp4"


def image_model(env: dict[str, str] | None = None) -> str:
    source = env if env is not None else os.environ
    return (
        source.get("OPENROUTER_IMAGE_MODEL")
        or source.get("LLM_MODEL_MEDIA_IMAGE")
        or DEFAULT_IMAGE_MODEL
    )


def video_model(env: dict[str, str] | None = None) -> str:
    source = env if env is not None else os.environ
    return (
        source.get("OPENROUTER_VIDEO_MODEL")
        or source.get("LLM_MODEL_MEDIA_VIDEO")
        or DEFAULT_VIDEO_MODEL
    )


def media_provider_name(env: dict[str, str] | None = None) -> str:
    source = env if env is not None else os.environ
    return (source.get("MEDIA_PROVIDER") or source.get("MEDIA_GENERATION_PROVIDER") or "openrouter").strip().lower()


def _clause(text: str) -> str:
    return text.strip().rstrip(".").strip()


def build_educational_media_prompt(
    *,
    topic: str,
    media_kind: str,
    subject: str | None = None,
    grade: int | None = None,
    concept: str | None = None,
    style: str | None = None,
    labels_language: str = "ru",
    prompt: str | None = None,
    learning_goal: str | None = None,
    visual_form: str | None = None,
    visual_intent: str | None = None,
    pedagogical_role: str | None = None,
    misconception_to_avoid: str | None = None,
    curriculum_context: str | None = None,
    source_context: str | None = None,
    must_include: list[str] | None = None,
    avoid: list[str] | None = None,
    success_check: str | None = None,
) -> str:
    grade_line = f"{grade} класс" if grade else "7-10 класс"
    default_form = "short continuous illustrative shot" if media_kind == "video" else "single illustrative scene or close-up"
    form = visual_form or default_form
    intent_guidance = VISUAL_INTENT_GUIDANCE.get((visual_intent or "").strip().lower())
    # labels_language и pedagogical_role остаются в сигнатуре ради старых
    # клиентов: подписей больше нет, роль у медиа одна — усилить блок.
    parts = [
        f"Create an illustration-story {media_kind} for a school lesson ({grade_line}).",
        "Its only job is to deepen understanding of one lesson block by making the idea visible and memorable. "
        "The lesson text next to it already carries every explanation, term and number, so the media must not "
        "repeat or replace it.",
        f"Topic: {_clause(topic)}.",
        f"Form: {_clause(form)}.",
    ]
    if subject:
        parts.append(f"Subject: {_clause(subject)}.")
    # Заголовок блока часто совпадает с целью и критерием — повтор модели не нужен.
    seen: list[str] = []

    def fresh(value: str | None) -> str:
        text = _clause(value or "")
        if not text or any(text.lower() in item.lower() for item in seen):
            return ""
        seen.append(text)
        return text

    if focus := fresh(concept):
        parts.append(f"Focus of this block: {focus}.")
    if goal := fresh(learning_goal):
        parts.append(f"After looking, the student should grasp (show it, never write it): {goal}.")
    if source_context:
        parts.append(
            "Lesson fragment this media accompanies (depict what it describes, add no unsupported facts): "
            f"{_clause(source_context)}."
        )
    if curriculum_context:
        parts.append(f"Wider lesson context, for accuracy only: {_clause(curriculum_context)}.")
    if intent_guidance:
        parts.append(f"Visual approach: {intent_guidance}.")
    parts.append(f"Visual style: {_clause(style or DEFAULT_MEDIA_STYLE)}.")
    include_items = [_clause(item) for item in (must_include or []) if isinstance(item, str) and item.strip()]
    avoid_items = [_clause(item) for item in (avoid or []) if isinstance(item, str) and item.strip()]
    if include_items:
        parts.append("Depict as things in the scene, not as written words: " + "; ".join(include_items[:6]) + ".")
    if avoid_items:
        parts.append("Avoid: " + "; ".join(avoid_items[:6]) + ".")
    parts.extend([
        NO_TEXT_RULE,
        "This is not a diagram, infographic, poster or presentation slide: one coherent scene or close-up with a "
        "single clear focal point, depth and breathing space.",
        "Accuracy still matters: correct proportions, materials, physics, anatomy and period details. If an exact "
        "value cannot be shown faithfully without numbers, show the qualitative relation instead (bigger or smaller, "
        "before or after, more or less).",
        "No fantasy creatures, brand logos, celebrities, stock-photo look, unsafe experiments, stereotypes or "
        "political persuasion.",
    ])
    if misconception_to_avoid:
        parts.append(f"The scene must not suggest this misconception: {_clause(misconception_to_avoid)}.")
    if success_check and not any(item.lower() in success_check.lower() for item in seen):
        parts.append(f"The media works if, after looking, the student can: {_clause(success_check)}.")
    if media_kind == "video":
        parts.append(
            "Show the phenomenon unfolding in one continuous shot or two calm shots, at a pace a student can follow, "
            "with stable framing and no distracting camera effects. No titles, subtitles or on-screen text."
        )
        parts.append("If audio is generated, use natural ambient sound only, without narration.")
    if prompt:
        parts.append(
            "Teacher wish (follow it where it is compatible with the rules above; the no-text rule may be relaxed only "
            f"if the teacher explicitly asks for a specific word or number to appear): {prompt.strip()}"
        )
    return " ".join(part for part in parts if part)


def media_provider(client: Any | None = None) -> Any:
    provider = media_provider_name()
    if provider == "openrouter":
        return OpenRouterMediaProvider(client=client)
    raise LLMError(
        "MEDIA_PROVIDER должен быть openrouter",
        provider=provider or "media",
    )


class OpenRouterMediaProvider:
    name = "openrouter"

    def __init__(self, client: Any | None = None) -> None:
        self._client = client
        self._auth = OpenRouterProvider(client=None)

    async def generate_image(
        self,
        *,
        prompt: str,
        model: str | None = None,
        aspect_ratio: str = "16:9",
        resolution: str = "1K",
        quality: str = "medium",
        output_format: str = "png",
        n: int = 1,
        provider: dict[str, Any] | None = None,
    ) -> ImageGenerationResult:
        selected_model = model or image_model()
        payload: dict[str, Any] = {
            "model": selected_model,
            "prompt": prompt,
            "n": n,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
            "quality": quality,
            "output_format": output_format,
        }
        # Известные модели получают только те параметры, которые принимают.
        from .catalog import image_supported_params

        supported = image_supported_params(selected_model)
        if supported is not None:
            for key in ("n", "aspect_ratio", "resolution", "quality", "output_format"):
                if key not in supported:
                    payload.pop(key, None)
        if provider:
            payload["provider"] = provider
        body = await self._post_json("/images", payload, selected_model)
        data = body.get("data") if isinstance(body.get("data"), list) else []
        first = data[0] if data and isinstance(data[0], dict) else {}
        b64_json = first.get("b64_json") if isinstance(first.get("b64_json"), str) else ""
        url = first.get("url") if isinstance(first.get("url"), str) else ""
        if not b64_json and not url:
            raise LLMError("OpenRouter не вернул изображение", provider=self.name, model=selected_model)
        media_type = first.get("media_type") if isinstance(first.get("media_type"), str) else f"image/{output_format}"
        usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
        served_model = body.get("model") if isinstance(body.get("model"), str) else selected_model
        return ImageGenerationResult(
            model=served_model,
            prompt=prompt,
            media_type=media_type,
            b64_json=b64_json,
            data_url=f"data:{media_type};base64,{b64_json}" if b64_json else "",
            url=url,
            usage=usage,
        )

    async def submit_video(
        self,
        *,
        prompt: str,
        model: str | None = None,
        aspect_ratio: str = "16:9",
        duration: int = 6,
        resolution: str = "720p",
        generate_audio: bool = False,
        provider: dict[str, Any] | None = None,
        seed: int | None = None,
    ) -> VideoGenerationJob:
        selected_model = model or video_model()
        payload: dict[str, Any] = {
            "model": selected_model,
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "duration": duration,
            "resolution": resolution,
            "generate_audio": generate_audio,
        }
        if provider:
            payload["provider"] = provider
        if seed is not None:
            payload["seed"] = seed
        body = await self._post_json("/videos", payload, selected_model)
        return self._to_video_job(body, selected_model)

    async def get_video_status(self, job_id_or_url: str, *, model: str | None = None) -> VideoGenerationJob:
        selected_model = model or video_model()
        url = self._video_status_url(job_id_or_url)
        body = await self._get_json(url, selected_model)
        return self._to_video_job(body, selected_model)

    async def get_video_content(self, job_id: str, *, index: int = 0, model: str | None = None) -> VideoContent:
        selected_model = model or video_model()
        if not job_id.strip():
            raise LLMError("Пустой id видео-задачи", provider=self.name, model=selected_model)
        url = f"{BASE_URL}/videos/{job_id.strip()}/content?index={index}"
        response = await self._get_response(url, selected_model)
        media_type = response.headers.get("content-type") or "video/mp4"
        return VideoContent(content=response.content, media_type=media_type.split(";")[0])

    def _video_status_url(self, job_id_or_url: str) -> str:
        value = job_id_or_url.strip()
        if not value:
            raise LLMError("Пустой id видео-задачи", provider=self.name)
        parsed = urlparse(value)
        if parsed.scheme in {"http", "https"}:
            return value
        if value.startswith("/"):
            return f"{BASE_URL}{value}"
        return f"{BASE_URL}/videos/{value}"

    async def _post_json(self, path: str, payload: dict[str, Any], model: str) -> dict[str, Any]:
        client = self._client
        own_client = client is None
        if own_client:
            client = AsyncClient(timeout=TIMEOUT)
        try:
            response = await client.post(f"{BASE_URL}{path}", json=payload, headers=self._auth._headers())
        except HTTPError as exc:
            raise LLMError(f"Запрос media API не прошёл: {exc}", provider=self.name, model=model) from exc
        finally:
            if own_client:
                await client.aclose()
        return self._read_json_response(response, model)

    async def _get_json(self, url: str, model: str) -> dict[str, Any]:
        response = await self._get_response(url, model)
        return self._read_json_response(response, model)

    async def _get_response(self, url: str, model: str) -> Any:
        client = self._client
        own_client = client is None
        if own_client:
            client = AsyncClient(timeout=TIMEOUT)
        try:
            response = await client.get(url, headers=self._auth._headers())
        except HTTPError as exc:
            raise LLMError(f"Запрос media API не прошёл: {exc}", provider=self.name, model=model) from exc
        finally:
            if own_client:
                await client.aclose()
        if response.status_code >= 400:
            raise LLMError(
                f"OpenRouter media API ответил {response.status_code}: {response.text[:300]}",
                provider=self.name,
                model=model,
            )
        return response

    def _read_json_response(self, response: Any, model: str) -> dict[str, Any]:
        if response.status_code >= 400:
            raise LLMError(
                f"OpenRouter media API ответил {response.status_code}: {response.text[:300]}",
                provider=self.name,
                model=model,
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise LLMError("OpenRouter media API вернул не JSON", provider=self.name, model=model) from exc
        if not isinstance(body, dict):
            raise LLMError("OpenRouter media API вернул неожиданный формат", provider=self.name, model=model)
        return body

    def _to_video_job(self, body: dict[str, Any], requested_model: str) -> VideoGenerationJob:
        job_id = body.get("id") or body.get("job_id") or body.get("generation_id")
        if not isinstance(job_id, str) or not job_id:
            raise LLMError("OpenRouter не вернул id видео-задачи", provider=self.name, model=requested_model)
        urls = body.get("unsigned_urls")
        unsigned_urls = [url for url in urls if isinstance(url, str)] if isinstance(urls, list) else []
        usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
        error = body.get("error") if isinstance(body.get("error"), dict) else None
        return VideoGenerationJob(
            id=job_id,
            status=body.get("status") if isinstance(body.get("status"), str) else "unknown",
            model=body.get("model") if isinstance(body.get("model"), str) else requested_model,
            polling_url=body.get("polling_url") if isinstance(body.get("polling_url"), str) else "",
            generation_id=body.get("generation_id") if isinstance(body.get("generation_id"), str) else "",
            unsigned_urls=unsigned_urls,
            usage=usage,
            error=error,
        )
