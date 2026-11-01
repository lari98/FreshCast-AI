"""Upload your own sales (and stock) CSV and get a forecast and order proposals.

Files are processed in memory and never stored; row contents are never logged
(only counts), which keeps personal-data exposure low. Intended for small
files (see limits in ``freshcast.byod.ingest``); large chains use the batch
pipeline instead.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from freshcast.byod.analyze import analyze
from freshcast.byod.ingest import MAX_BYTES, IngestError
from freshcast_api.security import Principal, Role, require_role

router = APIRouter(prefix="/v1", tags=["analyze"])

Operator = Annotated[Principal, Depends(require_role(Role.STORE_MANAGER, Role.ADMIN))]


def _read(upload: UploadFile) -> bytes:
    data = upload.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"{upload.filename or 'file'} is larger than {MAX_BYTES // 2**20} MB",
        )
    return data


@router.post("/analyze")
def analyze_upload(
    _who: Operator,
    sales: Annotated[UploadFile, File(description="Sales CSV")],
    stock: Annotated[UploadFile | None, File(description="Stock-lot CSV")] = None,
    as_of: Annotated[date | None, Form()] = None,
) -> dict[str, Any]:
    """Validate the upload, train on it and return the dashboard payload."""
    try:
        return analyze(_read(sales), _read(stock) if stock else None, as_of)
    except IngestError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, {"problems": exc.problems}
        ) from exc
