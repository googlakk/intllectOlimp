import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from static_site import mount_frontend


class StaticSiteTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.dist = base / "dist"
        (self.dist / "assets").mkdir(parents=True)
        (self.dist / "index.html").write_text("<html>shell</html>", encoding="utf-8")
        (self.dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
        (base / "secret.txt").write_text("secret", encoding="utf-8")

        app = FastAPI()

        @app.get("/api/healthz")
        async def health():
            return {"status": "ok"}

        self.mounted = mount_frontend(app, self.dist)
        self.client = TestClient(app)

    def tearDown(self):
        self._tmp.cleanup()

    def test_api_routes_keep_priority(self):
        self.assertTrue(self.mounted)
        self.assertEqual(self.client.get("/api/healthz").json(), {"status": "ok"})

    def test_unknown_api_path_is_json_404(self):
        response = self.client.get("/api/missing")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Not Found"})

    def test_spa_routes_return_index(self):
        for path in ("/", "/teacher/lessons/5", "/visual/density"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn("shell", response.text)
            self.assertEqual(response.headers["cache-control"], "no-cache")

    def test_assets_are_served_with_long_cache(self):
        response = self.client.get("/assets/app.js")
        self.assertEqual(response.text, "console.log(1)")
        self.assertIn("immutable", response.headers["cache-control"])

    def test_path_traversal_does_not_leak_files(self):
        response = self.client.get("/%2e%2e/secret.txt")
        self.assertNotIn("secret", response.text)

    def test_missing_build_mounts_nothing(self):
        app = FastAPI()
        self.assertFalse(mount_frontend(app, Path(self._tmp.name) / "absent"))


if __name__ == "__main__":
    unittest.main()
