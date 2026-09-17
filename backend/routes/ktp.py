from fastapi import APIRouter

router = APIRouter(prefix="/api/ktp", tags=["ktp"])


@router.post("/upload")
async def upload_ktp():
    return {"status": "not_implemented"}