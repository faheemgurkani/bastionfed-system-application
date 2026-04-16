from typing import Annotated, Any
import anyio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status

from app.auth.deps import AuthContext, require_read_auth, require_tenant_admin, require_user, scoped_fl_client_ids
from app.errors import api_error
from app.models.api import FLClientPatchBody, FLClientsResponse, FLModelActivateResponse, FLRoundsResponse
from app.models.domain import FLClient
from app.sse_bus import publish_fl
from app.store.tenant_store import PostgresTenantStore, tenant_store

router = APIRouter(tags=["fl"])


@router.get("/fl/status")
def fl_status(auth: Annotated[AuthContext, Depends(require_read_auth)]) -> dict[str, Any]:
    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    return tenant_store.fl_status_dict(auth.tenant_id, fl_client_ids=scoped_fl_client_ids(auth))


@router.get("/fl/clients/{client_id}", response_model=FLClient)
def get_fl_client(
    client_id: str,
    auth: Annotated[AuthContext, Depends(require_read_auth)],
):
    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    c = tenant_store.get_fl_client(auth.tenant_id, client_id, fl_client_ids=scoped_fl_client_ids(auth))
    if not c:
        raise api_error(status.HTTP_404_NOT_FOUND, "Client not found", "FL_CLIENT_NOT_FOUND")
    return c


@router.get("/fl/rounds", response_model=FLRoundsResponse)
def list_fl_rounds(auth: Annotated[AuthContext, Depends(require_read_auth)]) -> FLRoundsResponse:
    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    rounds, session_id = tenant_store.list_fl_rounds(auth.tenant_id)
    return FLRoundsResponse(rounds=rounds, session_id=session_id)


@router.get("/fl/clients", response_model=FLClientsResponse)
def list_fl_clients(auth: Annotated[AuthContext, Depends(require_read_auth)]) -> FLClientsResponse:
    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    return FLClientsResponse(clients=tenant_store.list_fl_clients(auth.tenant_id, fl_client_ids=scoped_fl_client_ids(auth)))


@router.patch("/fl/clients/{client_id}", response_model=FLClient)
def patch_fl_client(
    client_id: str,
    body: FLClientPatchBody,
    auth: Annotated[AuthContext, Depends(require_tenant_admin)],
):
    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    updated = tenant_store.patch_fl_client(auth.tenant_id, client_id, client_type=body.client_type)
    if not updated:
        raise api_error(status.HTTP_404_NOT_FOUND, "Client not found", "FL_CLIENT_NOT_FOUND")
    return updated


@router.get("/fl/drift", response_model=dict)
def drift(auth: Annotated[AuthContext, Depends(require_read_auth)]) -> dict:
    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    return tenant_store.fl_drift_dict(auth.tenant_id, fl_client_ids=scoped_fl_client_ids(auth))


@router.get("/fl/drift/clients", response_model=dict)
def client_drift(auth: Annotated[AuthContext, Depends(require_read_auth)]) -> dict:
    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    payload = tenant_store.fl_drift_dict(auth.tenant_id, fl_client_ids=scoped_fl_client_ids(auth))
    entries = payload.get("entries", [])
    clients = [
        {
            "clientId": entry["clientId"],
            "department": entry["department"],
            "fvDrift": {"score": entry["driftScore"], "status": "DEMO", "tau": 0.08},
            "imgDrift": {"score": entry["driftScore"], "status": "DEMO", "tau": 0.08},
            "combinedScore": entry["driftScore"],
            "combinedStatus": "DEMO_RESEARCH",
            "samplesAnalyzed": max(1, 12 - int(entry["roundsAgo"])),
            "lastEvent": f"{entry['roundsAgo']} rounds ago",
        }
        for entry in entries
    ]
    return {
        "available": True,
        "scope": payload.get("scope", "DEMO_RESEARCH"),
        "message": payload.get("operatorUse"),
        "driftMethod": payload.get("driftMethod"),
        "driftMethodDescription": payload.get("driftMethodDescription"),
        "zScoreFvDriftNote": payload.get("zScoreFvDriftNote"),
        "documentationRef": payload.get("documentationRef"),
        "clients": clients,
        "checkedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


@router.get("/fl/models", response_model=dict)
def models(auth: Annotated[AuthContext, Depends(require_read_auth)]) -> dict:
    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    sc = scoped_fl_client_ids(auth)
    if isinstance(tenant_store, PostgresTenantStore):
        return tenant_store.fl_models_dict(auth.tenant_id, fl_client_ids=sc)
    return tenant_store.fl_models_dict(auth.tenant_id)


@router.post("/fl/models/upload", status_code=status.HTTP_201_CREATED)
async def upload_fl_model(
    auth: Annotated[AuthContext, Depends(require_tenant_admin)],
    file: UploadFile = File(...),
    name: str = Form(...),
    modelType: str = Form(...),
    description: str = Form(""),
    trainedOn: str = Form(""),
    sizeLabel: str = Form(""),
    accuracy: float = Form(0.0),
    fpRate: float = Form(0.0),
    flClientId: str | None = Form(None),
):
    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    if not isinstance(tenant_store, PostgresTenantStore):
        raise api_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Model upload requires Postgres persistence",
            "POSTGRES_REQUIRED",
        )
    data = await file.read()
    fl_client_id = (flClientId or "").strip() or None

    class _Buf:
        filename = file.filename or "model.bin"

        def read(self) -> bytes:
            return data

    row = tenant_store.upload_fl_model_file(
        auth.tenant_id,
        file=_Buf(),
        name=name,
        model_type=modelType,
        description=description,
        trained_on=trainedOn or datetime.now(timezone.utc).isoformat(),
        size_label=sizeLabel or f"{len(data)} bytes",
        accuracy=accuracy,
        fp_rate=fpRate,
        fl_client_id=fl_client_id,
        actor_uid=auth.uid or "unknown",
    )
    if not row:
        raise api_error(status.HTTP_400_BAD_REQUEST, "Model upload failed", "MODEL_UPLOAD_FAILED")
    return row


@router.post("/fl/models/sync-global-bundles", response_model=dict)
def sync_global_model_bundles(auth: Annotated[AuthContext, Depends(require_tenant_admin)]) -> dict[str, Any]:
    """Upload `backend/data/models/pytorch/global/*.pth` (+ drift npz) to the models bucket under `global/` and register .pth rows. Layout: `backend/DATA_DIRECTORY.md`."""
    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    if not isinstance(tenant_store, PostgresTenantStore):
        raise api_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Model sync requires Postgres persistence",
            "POSTGRES_REQUIRED",
        )
    return tenant_store.sync_global_model_bundles_from_disk(auth.tenant_id, actor_uid=auth.uid or "unknown")


@router.post("/fl/models/{model_name}/activate", response_model=FLModelActivateResponse)
def activate_fl_model(
    model_name: str,
    auth: Annotated[AuthContext, Depends(require_user)],
    fl_client_id: str | None = Query(None, alias="flClientId"),
):
    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    if fl_client_id:
        if auth.role == "client_user":
            allowed = auth.fl_client_ids or frozenset()
            if fl_client_id not in allowed:
                raise api_error(status.HTTP_403_FORBIDDEN, "Not allowed for this FL client", "FL_CLIENT_FORBIDDEN")
        elif auth.role not in ("owner", "admin"):
            raise api_error(status.HTTP_403_FORBIDDEN, "Owner or admin required", "TENANT_ADMIN_REQUIRED")
    else:
        if auth.role not in ("owner", "admin"):
            raise api_error(status.HTTP_403_FORBIDDEN, "Owner or admin required", "TENANT_ADMIN_REQUIRED")
    prev, now_iso, ok = tenant_store.activate_fl_model(
        auth.tenant_id,
        model_name,
        auth.uid or "unknown",
        fl_client_id=fl_client_id,
    )
    if not ok:
        raise api_error(status.HTTP_404_NOT_FOUND, "Model not found or not allowed for this client", "MODEL_NOT_FOUND")
    payload: dict[str, Any] = {"type": "MODEL_ACTIVATED", "modelName": model_name, "switchedAt": now_iso}
    if fl_client_id:
        payload["flClientId"] = fl_client_id
    anyio.from_thread.run(publish_fl, auth.tenant_id, payload)

    return FLModelActivateResponse(
        activated=model_name,
        previously_active=prev,
        switched_at=now_iso,
    )
