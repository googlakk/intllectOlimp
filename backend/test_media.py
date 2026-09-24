import asyncio
import json
import os
import unittest

from llm import LLMError
from llm._http import AsyncClient, MockTransport, Response
from llm.media import (
    OpenRouterMediaProvider,
    build_educational_media_prompt,
    image_model,
    video_model,
)


def run(coro):
    return asyncio.run(coro)


def media_client(handler):
    return AsyncClient(transport=MockTransport(handler))


class Env:
    def __init__(self, **values):
        self.values = values
        self.saved = {}

    def __enter__(self):
        self.saved = dict(os.environ)
        for key, value in self.values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def __exit__(self, *args):
        os.environ.clear()
        os.environ.update(self.saved)


class MediaPromptTests(unittest.TestCase):
    def test_prompt_includes_classroom_context(self):
        prompt = build_educational_media_prompt(
            topic="Строение клетки",
            media_kind="image",
            subject="Биология",
            grade=7,
            concept="органоиды",
            visual_intent="structure",
            pedagogical_role="conceptual structure explanation support",
            must_include=["ядро", "митохондрии"],
            avoid=["декоративный фон"],
            success_check="назвать роль органоидов",
            source_context="Митохондрии участвуют в получении энергии клетки",
            labels_language="ru",
            prompt="Показать ядро и митохондрии",
        )
        self.assertIn("7 класс", prompt)
        self.assertIn("Биология", prompt)
        self.assertIn("Строение клетки", prompt)
        self.assertIn("ru", prompt)
        self.assertIn("Показать ядро", prompt)
        self.assertIn("Must include: ядро; митохондрии", prompt)
        self.assertIn("Avoid: декоративный фон", prompt)
        self.assertIn("Do not reveal only the final answer", prompt)
        self.assertIn("student can: назвать роль органоидов", prompt)
        self.assertIn("Source lesson fragment", prompt)
        self.assertIn("Митохондрии участвуют", prompt)
        self.assertIn("cannot override them", prompt)

    def test_model_env_overrides(self):
        self.assertEqual(image_model({"OPENROUTER_IMAGE_MODEL": "image/custom"}), "image/custom")
        self.assertEqual(video_model({"LLM_MODEL_MEDIA_VIDEO": "video/custom"}), "video/custom")


class OpenRouterMediaTests(unittest.TestCase):
    def test_generate_image_posts_to_images_and_returns_data_url(self):
        seen = {}

        def handler(request):
            seen["url"] = str(request.url)
            seen["auth"] = request.headers.get("authorization")
            seen["body"] = json.loads(request.content)
            return Response(200, json={
                "model": "image/served",
                "data": [{"b64_json": "aGVsbG8=", "media_type": "image/png"}],
                "usage": {"cost": 0.01},
            })

        with Env(OPENROUTER_API_KEY="sk-or-test"):
            provider = OpenRouterMediaProvider(client=media_client(handler))
            result = run(provider.generate_image(prompt="cell", model="image/requested"))

        self.assertTrue(seen["url"].endswith("/images"))
        self.assertEqual(seen["auth"], "Bearer sk-or-test")
        self.assertEqual(seen["body"]["prompt"], "cell")
        self.assertEqual(result.model, "image/served")
        self.assertEqual(result.data_url, "data:image/png;base64,aGVsbG8=")
        self.assertEqual(result.usage["cost"], 0.01)

    def test_generate_image_accepts_url_response(self):
        def handler(request):
            return Response(200, json={
                "model": "image/served",
                "data": [{"url": "https://cdn.example/image.png", "media_type": "image/png"}],
            })

        with Env(OPENROUTER_API_KEY="sk-or-test"):
            provider = OpenRouterMediaProvider(client=media_client(handler))
            result = run(provider.generate_image(prompt="cell", model="image/requested"))

        self.assertEqual(result.url, "https://cdn.example/image.png")
        self.assertEqual(result.data_url, "")

    def test_submit_video_returns_job(self):
        def handler(request):
            body = json.loads(request.content)
            self.assertEqual(body["duration"], 6)
            return Response(202, json={
                "id": "job_1",
                "status": "queued",
                "polling_url": "/api/v1/videos/job_1",
                "generation_id": "gen_1",
            })

        with Env(OPENROUTER_API_KEY="sk-or-test"):
            provider = OpenRouterMediaProvider(client=media_client(handler))
            job = run(provider.submit_video(prompt="atom", model="video/requested", duration=6))

        self.assertEqual(job.id, "job_1")
        self.assertEqual(job.status, "queued")
        self.assertEqual(job.polling_url, "/api/v1/videos/job_1")

    def test_video_status_accepts_job_id(self):
        seen = {}

        def handler(request):
            seen["url"] = str(request.url)
            return Response(200, json={
                "id": "job_1",
                "status": "completed",
                "unsigned_urls": ["https://cdn.example/video.mp4"],
                "usage": {"cost": 1.2},
            })

        with Env(OPENROUTER_API_KEY="sk-or-test"):
            provider = OpenRouterMediaProvider(client=media_client(handler))
            job = run(provider.get_video_status("job_1", model="video/requested"))

        self.assertTrue(seen["url"].endswith("/videos/job_1"))
        self.assertEqual(job.status, "completed")
        self.assertEqual(job.unsigned_urls, ["https://cdn.example/video.mp4"])

    def test_video_content_downloads_with_authorization(self):
        seen = {}

        def handler(request):
            seen["url"] = str(request.url)
            seen["auth"] = request.headers.get("authorization")
            return Response(200, content=b"mp4-bytes", headers={"content-type": "video/mp4"})

        with Env(OPENROUTER_API_KEY="sk-or-test"):
            provider = OpenRouterMediaProvider(client=media_client(handler))
            content = run(provider.get_video_content("job_1", model="video/requested"))

        self.assertTrue(seen["url"].endswith("/videos/job_1/content?index=0"))
        self.assertEqual(seen["auth"], "Bearer sk-or-test")
        self.assertEqual(content.content, b"mp4-bytes")
        self.assertEqual(content.media_type, "video/mp4")

    def test_missing_api_key_is_readable(self):
        def handler(request):
            return Response(200, json={})

        with Env(OPENROUTER_API_KEY=""):
            provider = OpenRouterMediaProvider(client=media_client(handler))
            with self.assertRaises(LLMError) as ctx:
                run(provider.generate_image(prompt="cell", model="image/requested"))

        self.assertIn("OPENROUTER_API_KEY", str(ctx.exception))
