import tempfile
import unittest
from pathlib import Path

from services.components import (
    ComponentRegistryError,
    load_component_registry,
    validate_component_registry,
)


VALID_COMPONENT = {
    "id": "short-explanation",
    "code": "C01",
    "category": "explain",
    "subjects": ["math"],
    "purpose": "Explain",
    "is_assessment": False,
    "content_schema": {"type": "object"},
    "rendering_notes": "Notes",
}


class ComponentRegistryTests(unittest.TestCase):
    def test_valid_registry_is_returned_unchanged(self):
        registry = [VALID_COMPONENT]

        self.assertEqual(validate_component_registry(registry), registry)

    def test_default_registry_contains_interactive_engine_components(self):
        ids = {item["id"] for item in load_component_registry()}

        self.assertTrue({
            "sort-and-classify",
            "process-builder",
            "argument-map",
            "branching-scenario",
            "misconception-debugger",
            "prediction-lab",
            "data-investigation",
            "physics-sandbox",
            "hotspot-investigation",
            "code-blocks-lab",
        }.issubset(ids))

    def test_registry_is_enriched_with_pedagogical_metadata(self):
        registry = load_component_registry()
        generated_media = next(item for item in registry if item["id"] == "generated-media")
        process_builder = next(item for item in registry if item["id"] == "process-builder")

        self.assertIn("explain", generated_media["roles"])
        self.assertFalse(generated_media["heavy_engine"])
        self.assertTrue(process_builder["heavy_engine"])

    def test_registry_must_be_a_list(self):
        with self.assertRaises(ValueError) as ctx:
            validate_component_registry({"items": []})

        self.assertIn("must be a list", str(ctx.exception))

    def test_registry_items_must_have_required_fields(self):
        self.assertEqual(validate_component_registry([{**VALID_COMPONENT, "purpose": None}])[0]["purpose"], None)
        with self.assertRaises(ValueError) as missing_ctx:
            validate_component_registry([{key: value for key, value in VALID_COMPONENT.items() if key != "purpose"}])
        self.assertIn("purpose", str(missing_ctx.exception))
        self.assertIn("item #1", str(missing_ctx.exception))

    def test_load_component_registry_wraps_json_errors(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "registry.json"
            path.write_text("{bad json", encoding="utf-8")

            with self.assertRaises(ComponentRegistryError) as ctx:
                load_component_registry(path)

        self.assertEqual(ctx.exception.status_code, 500)
        self.assertIn("Некорректный registry", ctx.exception.detail)

    def test_load_component_registry_wraps_missing_file(self):
        with self.assertRaises(ComponentRegistryError) as ctx:
            load_component_registry(Path("/tmp/not-a-real-component-registry.json"))

        self.assertEqual(ctx.exception.status_code, 500)
        self.assertEqual(ctx.exception.detail, "Registry компонентов недоступен")


if __name__ == "__main__":
    unittest.main()
