from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.auth.deps import AuthContext, require_read_auth
from app.errors import api_error
from app.models.api import MalwareSampleListResponse
from app.models.domain import RCAReport
from app.store.memory import state

router = APIRouter(tags=["forensics"])


@router.get("/forensics/samples", response_model=MalwareSampleListResponse)
def list_samples(
    _auth: Annotated[AuthContext, Depends(require_read_auth)],
    limit: int = 50,
    cursor: str | None = None,
    sample_status: str | None = Query(None, alias="status"),
    family: str | None = None,
):
    items, next_cursor, total = state.list_samples(
        limit=min(limit, 200), cursor=cursor, status=sample_status, family=family
    )
    return MalwareSampleListResponse(items=items, next_cursor=next_cursor, total=total)


@router.get("/forensics/rca/{rca_id}", response_model=RCAReport)
def get_rca(
    rca_id: str,
    _auth: Annotated[AuthContext, Depends(require_read_auth)],
):
    r = state.get_rca(rca_id)
    if not r:
        raise api_error(status.HTTP_404_NOT_FOUND, "RCA report not found", "RCA_NOT_FOUND")
    return r
