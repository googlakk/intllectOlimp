from fastapi import HTTPException

from errors import ApplicationError


def raise_http_error(error: ApplicationError) -> None:
    """Translate an application error at the HTTP adapter boundary."""
    raise HTTPException(status_code=error.status_code, detail=error.detail)
