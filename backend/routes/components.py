import json
from pathlib import Path

from fastapi import APIRouter, Depends
from deps import require_staff

router = APIRouter(prefix="/api", tags=["components"], dependencies=[Depends(require_staff)])
REGISTRY = Path(__file__).resolve().parent.parent / "component_registry.json"


@router.get("/components")
async def components():
    return json.loads(REGISTRY.read_text(encoding="utf-8"))