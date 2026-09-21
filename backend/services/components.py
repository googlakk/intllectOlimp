import json
from pathlib import Path
from typing import Any

from errors import ApplicationError

REGISTRY = Path(__file__).resolve().parent.parent / "component_registry.json"
REQUIRED_FIELDS = {
    "id",
    "code",
    "category",
    "subjects",
    "purpose",
    "is_assessment",
    "content_schema",
    "rendering_notes",
}


class ComponentRegistryError(ApplicationError):
    pass


def validate_component_registry(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("Component registry must be a list")
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"Component registry item #{index + 1} must be an object")
        missing = sorted(REQUIRED_FIELDS - set(item))
        if missing:
            raise ValueError(
                f"Component registry item #{index + 1} is missing fields: {', '.join(missing)}"
            )
    return value


def load_component_registry(path: Path = REGISTRY) -> list[dict[str, Any]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return validate_component_registry(raw)
    except ValueError as exc:
        raise ComponentRegistryError(
            status_code=500,
            detail=f"Некорректный registry компонентов: {exc}",
        ) from exc
    except OSError as exc:
        raise ComponentRegistryError(
            status_code=500,
            detail="Registry компонентов недоступен",
        ) from exc
