from typing import Any

from fastapi import HTTPException, status


def api_error(status_code: int, detail: str, code: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"detail": detail, "code": code},
    )


def validation_error(detail: str, code: str = "VALIDATION_ERROR") -> HTTPException:
    return api_error(status.HTTP_400_BAD_REQUEST, detail, code)
