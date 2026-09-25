import json
from pathlib import Path
from typing import Any

from errors import ApplicationError
from objectives import RETIRED_COMPONENTS

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

COMPONENT_METADATA: dict[str, dict[str, Any]] = {
    "RetrievalCheck": {"roles": ["diagnose", "assess"], "cognitive_actions": ["remember"], "heavy_engine": False, "best_for_volume": ["micro", "standard", "extended"]},
    "ShortExplanation": {"roles": ["explain"], "cognitive_actions": ["understand"], "heavy_engine": False, "best_for_volume": ["micro", "standard", "extended"]},
    "KeyConcept": {"roles": ["explain"], "cognitive_actions": ["define", "compare"], "heavy_engine": False, "best_for_volume": ["micro", "standard"]},
    "Illustration": {"roles": ["explain"], "cognitive_actions": ["visualise"], "heavy_engine": False, "best_for_volume": ["micro", "standard", "extended"]},
    "GeneratedMedia": {"roles": ["explain"], "cognitive_actions": ["visualise", "observe"], "heavy_engine": False, "best_for_volume": ["standard", "extended", "unit"]},
    "WorkedExample": {"roles": ["model"], "cognitive_actions": ["follow_procedure"], "heavy_engine": False, "best_for_volume": ["micro", "standard", "extended"]},
    "GuidedPractice": {"roles": ["practice"], "cognitive_actions": ["apply"], "heavy_engine": False, "best_for_volume": ["micro", "standard", "extended"]},
    "IndependentProblem": {"roles": ["apply", "assess"], "cognitive_actions": ["transfer"], "heavy_engine": False, "best_for_volume": ["micro", "standard", "extended"]},
    "MasteryCheck": {"roles": ["assess"], "cognitive_actions": ["demonstrate_mastery"], "heavy_engine": False, "best_for_volume": ["micro", "standard", "extended", "unit"]},
    "Reflection": {"roles": ["reflect"], "cognitive_actions": ["metacognition"], "heavy_engine": False, "best_for_volume": ["micro", "standard", "extended", "unit"]},
}

HEAVY_COMPONENT_CODES = {
    "ProcessBuilder", "ArgumentMap", "BranchingScenario", "PredictionLab",
    "DataInvestigation", "PhysicsSandbox", "HotspotInvestigation", "CodeBlocksLab",
}

REGISTRY_ID_TO_COMPONENT = {
    "retrieval-check": "RetrievalCheck",
    "short-explanation": "ShortExplanation",
    "key-concept": "KeyConcept",
    "illustration": "Illustration",
    "generated-media": "GeneratedMedia",
    "worked-example": "WorkedExample",
    "guided-practice": "GuidedPractice",
    "independent-problem": "IndependentProblem",
    "mastery-check": "MasteryCheck",
    "reflection": "Reflection",
    "process-builder": "ProcessBuilder",
    "argument-map": "ArgumentMap",
    "branching-scenario": "BranchingScenario",
    "prediction-lab": "PredictionLab",
    "data-investigation": "DataInvestigation",
    "physics-sandbox": "PhysicsSandbox",
    "hotspot-investigation": "HotspotInvestigation",
    "code-blocks-lab": "CodeBlocksLab",
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


def enrich_component_registry(value: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = []
    for item in value:
        code = REGISTRY_ID_TO_COMPONENT.get(str(item.get("id")), str(item.get("code")))
        metadata = COMPONENT_METADATA.get(code, {})
        if not metadata and code in HEAVY_COMPONENT_CODES:
            metadata = {
                "roles": ["practice", "apply"],
                "cognitive_actions": ["interact", "construct"],
                "heavy_engine": True,
                "best_for_volume": ["standard", "extended", "unit"],
            }
        enriched.append({
            **item,
            "roles": metadata.get("roles", ["explain" if not item.get("is_assessment") else "practice"]),
            "cognitive_actions": metadata.get("cognitive_actions", ["understand"]),
            "heavy_engine": metadata.get("heavy_engine", False),
            "best_for_volume": metadata.get("best_for_volume", ["micro", "standard", "extended"]),
        })
    return enriched


def load_component_registry(path: Path = REGISTRY) -> list[dict[str, Any]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        registry = enrich_component_registry(validate_component_registry(raw))
        # Выведенные из употребления компоненты не предлагаем в конструкторе и каталоге.
        return [
            item for item in registry
            if REGISTRY_ID_TO_COMPONENT.get(str(item.get("id")), str(item.get("code"))) not in RETIRED_COMPONENTS
        ]
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
