from fastapi import APIRouter

from routes.http_errors import raise_http_error
from services.components import ComponentRegistryError, load_component_registry

router = APIRouter(prefix="/api", tags=["components"])

@router.get("/components")
async def components():
    try:
        return load_component_registry()
    except ComponentRegistryError as exc:
        raise_http_error(exc)
