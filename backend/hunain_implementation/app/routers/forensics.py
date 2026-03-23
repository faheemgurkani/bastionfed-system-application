from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.auth.deps import AuthContext, require_read_auth
from app.errors import api_error
from app.models.domain import MalwareSample
from app.store.memory import state

router = APIRouter(tags=["forensics"])


@router.get("/forensics/samples/{sample_id}", response_model=MalwareSample)
def get_sample(
    sample_id: str,
    _auth: Annotated[AuthContext, Depends(require_read_auth)],
):
    s = state.get_sample(sample_id)
    if not s:
        raise api_error(status.HTTP_404_NOT_FOUND, "Sample not found", "SAMPLE_NOT_FOUND")
    return s
