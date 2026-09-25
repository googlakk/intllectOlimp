from typing import Any

from fastapi import APIRouter

from llm.catalog import model_catalog

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/models")
async def list_models() -> dict[str, Any]:
    """Модели, доступные учителю для генерации урока и изображений."""
    return model_catalog()
