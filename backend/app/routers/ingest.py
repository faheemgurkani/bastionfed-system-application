from __future__ import annotations

from typing import Annotated

import anyio
from fastapi import APIRouter, Depends, Header, status

from app.auth.deps import AuthContext, require_tenant_admin
from app.errors import api_error
from app.models.api import (
    IngestEventRequest,
    IngestEventResponse,
    IngestSourceCreateRequest,
    IngestSourceListResponse,
    IngestSourceResponse,
)
from app.sse_bus import publish_alert
from app.store.tenant_store import tenant_store

router = APIRouter(tags=["ingest"])


@router.get("/ingest/sources", response_model=IngestSourceListResponse)
def list_ingest_sources(auth: Annotated[AuthContext, Depends(require_tenant_admin)]) -> IngestSourceListResponse:
    return IngestSourceListResponse(items=tenant_store.list_ingest_sources(auth.tenant_id))


@router.post("/ingest/sources", response_model=IngestSourceResponse, status_code=status.HTTP_201_CREATED)
def create_ingest_source(
    body: IngestSourceCreateRequest,
    auth: Annotated[AuthContext, Depends(require_tenant_admin)],
) -> IngestSourceResponse:
    source, secret = tenant_store.create_ingest_source(
        auth.tenant_id,
        name=body.name,
        source_type=body.source_type,
        connector_kind=body.connector_kind,
        actor_uid=auth.uid or "unknown",
    )
    return IngestSourceResponse(source=source, secret=secret)


@router.post("/ingest/sources/{source_id}/rotate-secret", response_model=IngestSourceResponse)
def rotate_ingest_source_secret(
    source_id: str,
    auth: Annotated[AuthContext, Depends(require_tenant_admin)],
) -> IngestSourceResponse:
    source, secret = tenant_store.rotate_ingest_source_secret(auth.tenant_id, source_id=source_id, actor_uid=auth.uid or "unknown")
    if not source or not secret:
        raise api_error(status.HTTP_404_NOT_FOUND, "Ingest source not found", "INGEST_SOURCE_NOT_FOUND")
    return IngestSourceResponse(source=source, secret=secret)


@router.post("/ingest/events", response_model=IngestEventResponse, status_code=status.HTTP_202_ACCEPTED)
def submit_ingest_event(
    body: IngestEventRequest,
    ingest_key: Annotated[str | None, Header(alias="X-BastionFed-Ingest-Key")] = None,
) -> IngestEventResponse:
    if not ingest_key:
        raise api_error(status.HTTP_401_UNAUTHORIZED, "Missing ingest key", "INGEST_KEY_REQUIRED")
    result = tenant_store.ingest_event(
        source_id=body.source_id,
        source_secret=ingest_key,
        external_id=body.external_id,
        event_type=body.event_type,
        payload=body.payload,
        occurred_at=body.occurred_at,
    )
    if not result:
        raise api_error(status.HTTP_401_UNAUTHORIZED, "Invalid ingest credentials", "INGEST_AUTH_FAILED")
    for target in result.normalized_targets:
        if target.get("type") == "alert":
            # Publish a lightweight alert write signal; subscribers will refetch scoped data.
            anyio.from_thread.run(publish_alert, result.tenant_id, {"type": "INGEST_ALERT", "alertId": target["id"], "sourceId": body.source_id})
            break
    return IngestEventResponse(result=result)
