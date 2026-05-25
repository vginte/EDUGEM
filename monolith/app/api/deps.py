from fastapi import HTTPException


def raise_not_found(detail: str = "Recurso no encontrado") -> None:
    raise HTTPException(status_code=404, detail=detail)


def raise_bad_request(detail: str) -> None:
    raise HTTPException(status_code=400, detail=detail)


def raise_conflict(detail: str) -> None:
    raise HTTPException(status_code=409, detail=detail)
