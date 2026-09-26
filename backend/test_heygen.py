import asyncio
import base64
import hashlib
import hmac
import json
import unittest

from llm._http import AsyncClient, MockTransport, Response
from llm.heygen import HeyGenProvider, verify_webhook_signature


def run(coro):
    return asyncio.run(coro)


class HeyGenProviderTests(unittest.TestCase):
    def test_catalog_and_video_generation(self):
        seen = []

        def handler(request):
            seen.append((request.method, str(request.url), request.headers.get("x-api-key")))
            if request.method == "GET" and "/v2/avatars" in str(request.url):
                return Response(200, json={"data": {"avatars": [{"avatar_id": "avatar-1"}]}})
            if request.method == "GET" and "/v2/voices" in str(request.url):
                return Response(200, json={"data": {"voices": [{"voice_id": "voice-1"}]}})
            if request.method == "POST":
                body = json.loads(request.content)
                video_input = body["video_inputs"][0]
                self.assertEqual(video_input["character"]["avatar_id"], "avatar-1")
                self.assertEqual(video_input["voice"]["voice_id"], "voice-1")
                self.assertEqual(video_input["voice"]["input_text"], "Объяснение")
                return Response(200, json={"data": {"video_id": "video-1"}})
            return Response(200, json={"data": {
                "video_id": "video-1", "status": "completed",
                "video_url": "https://cdn/video.mp4",
            }})

        provider = HeyGenProvider(
            client=AsyncClient(transport=MockTransport(handler)), api_key="test-key",
        )
        avatars = run(provider.list_avatars())
        voices = run(provider.list_voices(language="ru"))
        submitted = run(provider.create_video(
            avatar_id="avatar-1", voice_id="voice-1", script="Объяснение",
        ))
        completed = run(provider.get_video(submitted.id))

        self.assertEqual(avatars[0]["avatar_id"], "avatar-1")
        self.assertEqual(voices[0]["voice_id"], "voice-1")
        self.assertEqual(completed.status, "completed")
        self.assertTrue(any("/v2/video/generate" in item[1] for item in seen))
        self.assertTrue(any("/v1/video_status.get?video_id=video-1" in item[1] for item in seen))
        self.assertTrue(all(item[2] == "test-key" for item in seen))

    def test_webhook_signature_and_replay_window(self):
        body = b'{"event_type":"avatar_video.success"}'
        secret = "secret"
        signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        self.assertTrue(verify_webhook_signature(body, signature, "1000", secret=secret, now=1100))
        self.assertFalse(verify_webhook_signature(body, signature, "1000", secret=secret, now=1401))
        self.assertFalse(verify_webhook_signature(body + b"x", signature, "1000", secret=secret, now=1100))

    def test_voice_language_filter_does_not_match_names(self):
        def handler(_request):
            return Response(200, json={"data": {"voices": [
                {"voice_id": "english", "language": "English", "name": "Ruben"},
                {"voice_id": "russian", "language": "Russian", "name": "Aleksandr"},
            ]}})

        provider = HeyGenProvider(
            client=AsyncClient(transport=MockTransport(handler)), api_key="test-key",
        )
        voices = run(provider.list_voices(language="ru"))

        self.assertEqual([voice["voice_id"] for voice in voices], ["russian"])

    def test_photo_avatar_creation_and_v3_video(self):
        seen = []

        def handler(request):
            seen.append((request.method, str(request.url), request.headers, request.content))
            if request.method == "POST" and str(request.url).endswith("/v3/avatars"):
                body = json.loads(request.content)
                self.assertEqual(body["type"], "photo")
                self.assertEqual(base64.b64decode(body["file"]["data"]), b"\x89PNG\r\n\x1a\nphoto")
                return Response(200, json={"data": {
                    "avatar_item": {
                        "id": "look-1", "group_id": "group-1", "status": "processing",
                        "preview_image_url": "https://cdn/avatar.png",
                    },
                    "avatar_group": {"id": "group-1"},
                }})
            if request.method == "GET" and "/v3/avatars/looks/look-1" in str(request.url):
                return Response(200, json={"data": {
                    "id": "look-1", "group_id": "group-1", "status": "completed",
                    "preview_image_url": "https://cdn/ready.png",
                }})
            if request.method == "POST" and str(request.url).endswith("/v3/videos"):
                body = json.loads(request.content)
                self.assertEqual(body["avatar_id"], "look-1")
                # Дешёвый движок явно: без engine HeyGen берёт дорогой Avatar IV.
                self.assertEqual(body["engine"], {"type": "avatar_iii"})
                return Response(200, json={"data": {"video_id": "video-v3", "status": "waiting"}})
            if request.method == "GET" and "/v3/videos/video-v3" in str(request.url):
                return Response(200, json={"data": {
                    "video_id": "video-v3", "status": "completed", "video_url": "https://cdn/v3.mp4",
                }})
            return Response(404)

        provider = HeyGenProvider(client=AsyncClient(transport=MockTransport(handler)), api_key="test-key")
        created = run(provider.create_photo_avatar(
            name="Мой ведущий",
            image=b"\x89PNG\r\n\x1a\nphoto",
            media_type="image/png",
            idempotency_key="photo-avatar:1:hash",
        ))
        ready = run(provider.get_avatar_look(created.id))
        submitted = run(provider.create_video(
            avatar_id=created.id, voice_id="voice-1", script="Текст", api_version="v3",
        ))
        video = run(provider.get_video(submitted.id, api_version="v3"))

        self.assertEqual(created.id, "look-1")
        self.assertEqual(ready.status, "completed")
        self.assertEqual(video.video_url, "https://cdn/v3.mp4")
        create_headers = next(item[2] for item in seen if item[1].endswith("/v3/avatars"))
        self.assertEqual(create_headers.get("idempotency-key"), "photo-avatar:1:hash")


if __name__ == "__main__":
    unittest.main()
