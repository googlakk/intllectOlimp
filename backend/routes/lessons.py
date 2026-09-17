from fastapi import APIRouter

router = APIRouter(prefix="/api/lessons", tags=["lessons"])


@router.post("/generate")
async def generate():
    return {"status": "not_implemented"}