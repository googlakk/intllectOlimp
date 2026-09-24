import asyncio
import unittest
from types import SimpleNamespace

from lesson_contracts import adapt_legacy_blocks
from models import LessonAsset
from services.lessons import carry_forward_anchored_assets


class _ScalarRows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class _Session:
    def __init__(self, rows):
        self.rows = rows
        self.added = []

    async def scalars(self, _statement):
        return _ScalarRows(self.rows)

    def add(self, value):
        self.added.append(value)


def _asset(*, beat_id, cue_id=None):
    return LessonAsset(
        lesson_version_id=1,
        scene_id="scene-1",
        kind="avatar_video" if cue_id else "image",
        provider="test",
        source_url="https://cdn.example/asset",
        status="ready",
        metadata_json={"beat_id": beat_id, "cue_id": cue_id},
    )


class LessonAssetSyncTests(unittest.TestCase):
    def test_only_assets_with_live_semantic_anchors_are_carried_forward(self):
        document = adapt_legacy_blocks([{"component": "Presentation", "content": {
            "title": "Тема",
            "slides": [{"id": "slide-1", "heading": "Шаг", "body": "Текст", "avatar_script": "Пояснение"}],
        }}])
        valid_cue = document["episodes"][0]["scenes"][0]["avatar_cues"][0]["id"]
        db = _Session([
            _asset(beat_id="slide-1", cue_id=valid_cue),
            _asset(beat_id="deleted-slide"),
        ])

        asyncio.run(carry_forward_anchored_assets(1, SimpleNamespace(id=2), document, db))

        self.assertEqual(len(db.added), 1)
        self.assertEqual(db.added[0].lesson_version_id, 2)
        self.assertEqual(db.added[0].metadata_json["beat_id"], "slide-1")


if __name__ == "__main__":
    unittest.main()
