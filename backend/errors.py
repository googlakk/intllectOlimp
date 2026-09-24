from typing import Any


class ApplicationError(Exception):
    """Base application error that routes can translate to HTTP responses."""

    def __init__(self, status_code: int, detail: Any, *, code: str | None = None):
        self.status_code = status_code
        self.detail = detail
        self.code = code
        super().__init__(str(detail))
