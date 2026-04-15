"""Admin-only client-provisioning endpoint.

POST /api/onboarding/clients
  Body: list of ClientProvisionInput objects (node_name, client_type, email?)
  Returns: per-client results including status, errors, and email delivery info.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.auth.deps import AuthContext, require_tenant_admin
from app.config import settings
from app.errors import api_error
from app.models.api import (
    OnboardingClientResult,
    OnboardingClientsRequest,
    OnboardingClientsResponse,
    OnboardingLimitsResponse,
)
from app.services.client_onboarding import ClientProvisionInput, provision_clients
from app.store.tenant_store import tenant_store

router = APIRouter(tags=["onboarding"])


@router.get("/onboarding/limits", response_model=OnboardingLimitsResponse)
def onboarding_limits(
    auth: Annotated[AuthContext, Depends(require_tenant_admin)],
) -> OnboardingLimitsResponse:
    """Return how many clients this admin has already provisioned vs the per-admin cap."""
    if not auth.tenant_id or not auth.uid:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    existing = tenant_store.count_fl_clients_by_creator(auth.tenant_id, auth.uid)
    remaining = max(0, settings.max_clients_per_admin - existing)
    return OnboardingLimitsResponse(
        max_clients_per_admin=settings.max_clients_per_admin,
        already_provisioned=existing,
        remaining=remaining,
    )


@router.post("/onboarding/clients", response_model=OnboardingClientsResponse)
def provision_initial_clients(
    body: OnboardingClientsRequest,
    auth: Annotated[AuthContext, Depends(require_tenant_admin)],
) -> OnboardingClientsResponse:
    """Provision FL clients for this tenant.

    When ``BASTIONFED_IDENTITY_ONLY_PROVISIONING`` is true: only empty ``fl_clients``
    rows — no Firebase users, emails, or membership wiring for PERSON.

    When false: PERSON gets Firebase Auth user, credentials email, and membership scopes;
    DEVICE still only creates the FL client record.

    Requires owner or admin role. Returns per-client results even when some fail.
    """
    if not auth.tenant_id or not auth.uid:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")

    if not body.clients:
        raise api_error(status.HTTP_400_BAD_REQUEST, "At least one client must be specified", "NO_CLIENTS")

    # Resolve tenant display name for the credential email
    tenant_name = body.tenant_name
    if not tenant_name:
        tenant_name = tenant_store.get_tenant_name(auth.tenant_id) or "BastionFed"

    inputs = [
        ClientProvisionInput(
            node_name=c.node_name.strip(),
            client_type=c.client_type.upper(),
            email=c.email.strip() if c.email else None,
            department=c.department,
        )
        for c in body.clients
        if c.node_name.strip()
    ]

    if not inputs:
        raise api_error(status.HTTP_400_BAD_REQUEST, "All client entries have empty node names", "NO_CLIENTS")

    existing = tenant_store.count_fl_clients_by_creator(auth.tenant_id, auth.uid)
    remaining = settings.max_clients_per_admin - existing
    if len(inputs) > remaining:
        raise api_error(
            status.HTTP_400_BAD_REQUEST,
            f"You have already provisioned {existing} client(s) for this tenant. "
            f"You may add up to {remaining} more (maximum {settings.max_clients_per_admin} per admin account).",
            "CLIENT_LIMIT_REACHED",
        )

    raw_results = provision_clients(
        tenant_id=auth.tenant_id,
        tenant_name=tenant_name,
        admin_uid=auth.uid,
        inputs=inputs,
    )

    results = [
        OnboardingClientResult(
            node_name=r.node_name,
            client_type=r.client_type,
            status=r.status,
            client_id=r.client_id,
            email=r.email,
            firebase_uid=r.firebase_uid,
            error=r.error,
            email_error=r.email_error,
            identity_only=r.identity_only,
        )
        for r in raw_results
    ]

    created = sum(1 for r in results if r.status in ("created", "email_failed"))
    errors = sum(1 for r in results if r.status == "error")

    return OnboardingClientsResponse(
        results=results,
        created_count=created,
        error_count=errors,
    )
