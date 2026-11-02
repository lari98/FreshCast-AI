"""Upload your own sales (and stock) CSV and get a forecast and order proposals.

Files are processed in memory and never stored; row contents are never logged
(only counts), which keeps personal-data exposure low. Intended for small
files (see limits in ``freshcast.byod.ingest``); large chains use the batch
pipeline instead.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)

from freshcast.byod.analyze import analyze
from freshcast.byod.ingest import MAX_BYTES, IngestError
from freshcast.security.upload_guard import UploadRejected, guard_upload
from freshcast_api.config import Settings
from freshcast_api.efficiency import Busy, cache_key
from freshcast_api.security import Principal, Role, require_role

router = APIRouter(prefix="/v1", tags=["analyze"])

Operator = Annotated[Principal, Depends(require_role(Role.STORE_MANAGER, Role.ADMIN))]


def _read(upload: UploadFile, settings: Settings) -> bytes:
    data = upload.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"{upload.filename or 'file'} is larger than {MAX_BYTES // 2**20} MB",
        )
    clamd = (settings.clamd_host, settings.clamd_port) if settings.clamd_host else None
    try:
        guard_upload(data, upload.filename or "", clamd)
    except UploadRejected as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"problems": [f"{upload.filename or 'file'}: {exc.reason}"]},
        ) from exc
    return data


@router.post("/analyze")
def analyze_upload(
    request: Request,
    _who: Operator,
    sales: Annotated[UploadFile, File(description="Sales CSV")],
    stock: Annotated[UploadFile | None, File(description="Stock-lot CSV")] = None,
    as_of: Annotated[date | None, Form()] = None,
) -> dict[str, Any]:
    """Validate the upload, train on it and return the dashboard payload."""
    try:
        settings: Settings = request.app.state.settings
        sales_data = _read(sales, settings)
        stock_data = _read(stock, settings) if stock else None
        key = cache_key(sales_data, stock_data, as_of or date.today())
        cache = request.app.state.analyze_cache
        cached: dict[str, Any] | None = cache.get(key)
        if cached is not None:
            return cached  # same upload again: no training, no processor load
        try:
            with request.app.state.analyze_gate.slot():
                result = analyze(sales_data, stock_data, as_of)
        except Busy as exc:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "analysis capacity is in use, try again in a few seconds",
                headers={"Retry-After": "5"},
            ) from exc
        cache.put(key, result)
        return result
    except IngestError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, {"problems": exc.problems}
        ) from exc
