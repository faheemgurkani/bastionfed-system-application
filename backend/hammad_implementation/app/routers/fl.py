from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth.deps import AuthContext, require_read_auth
from app.store.memory import state

router = APIRouter(tags=["fl"])


@router.get("/fl/drift", response_model=dict)
def drift(_auth: Annotated[AuthContext, Depends(require_read_auth)]) -> dict:
    return state.fl_drift_dict()


@router.get("/fl/models", response_model=dict)
def models(_auth: Annotated[AuthContext, Depends(require_read_auth)]) -> dict:
    return state.fl_models_dict()
