"""Admin client-provisioning service.

Orchestrates:
  1. Generating a strong random password for PERSON clients.
  2. Creating the Firebase Auth user (via Admin SDK).
  3. Inserting the fl_client record into the store (with node_name, client_type).
  4. Wiring the Firebase UID to the tenant membership so the new user already has
     scoped access on first login (no invite-accept step needed).
  5. Sending a credentials email to the person-client.
"""

from __future__ import annotations

import logging
import secrets
import string
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


def _generate_password(length: int = 18) -> str:
    """Return a cryptographically random password meeting complexity requirements."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.islower() for c in pwd)
            and any(c.isupper() for c in pwd)
            and any(c.isdigit() for c in pwd)
            and any(c in "!@#$%^&*" for c in pwd)
        ):
            return pwd


@dataclass
class ClientProvisionInput:
    node_name: str
    client_type: str  # "PERSON" | "DEVICE"
    email: str | None = None
    department: str | None = None  # falls back to node_name when absent


@dataclass
class ClientProvisionResult:
    node_name: str
    client_type: str
    status: str  # "created" | "error" | "email_failed"
    client_id: str | None = None
    email: str | None = None
    firebase_uid: str | None = None
    error: str | None = None
    email_error: str | None = None
    identity_only: bool = False


def provision_clients(
    tenant_id: str,
    tenant_name: str,
    admin_uid: str,
    inputs: list[ClientProvisionInput],
) -> list[ClientProvisionResult]:
    """Provision a batch of clients on behalf of an admin.

    For each input:
    - DEVICE: creates an fl_clients registry row (empty metrics).
    - PERSON: if ``identity_only_provisioning``: same DB row only — no Firebase user,
      email, or membership wiring. Otherwise: Firebase user + fl_client + membership + email.

    Always returns a result per input; failures for one client do not abort the rest.
    """
    from app.services import email_sender, firebase_admin_sdk
    from app.config import settings
    from app.models.domain import FLClientStatus, FLClientType
    from app.store.tenant_store import tenant_store

    results: list[ClientProvisionResult] = []

    for item in inputs:
        node_slug = item.node_name.lower().replace(" ", "-")
        client_id = f"{node_slug}-{secrets.token_hex(4)}"
        department = item.department or item.node_name

        if item.client_type == "PERSON":
            if not item.email or not item.email.strip():
                results.append(
                    ClientProvisionResult(
                        node_name=item.node_name,
                        client_type=item.client_type,
                        status="error",
                        error="Email address is required for PERSON client type.",
                    )
                )
                continue

            # Identity-only: empty FL client row in Postgres only (no Firebase / email / membership data).
            if settings.identity_only_provisioning:
                try:
                    tenant_store.create_fl_client(
                        tenant_id=tenant_id,
                        client_id=client_id,
                        node_name=item.node_name,
                        department=department,
                        client_type=FLClientType.PERSON,
                        email=item.email.strip() if item.email else None,
                        firebase_uid=None,
                        created_by_uid=admin_uid,
                    )
                except Exception as exc:
                    logger.exception("create_fl_client failed (identity-only PERSON) for %s", item.node_name)
                    results.append(
                        ClientProvisionResult(
                            node_name=item.node_name,
                            client_type=item.client_type,
                            status="error",
                            email=item.email,
                            error=f"Failed to create FL client record: {exc}",
                        )
                    )
                    continue
                results.append(
                    ClientProvisionResult(
                        node_name=item.node_name,
                        client_type=item.client_type,
                        status="created",
                        client_id=client_id,
                        email=item.email.strip(),
                        firebase_uid=None,
                        identity_only=True,
                    )
                )
                continue

            password = _generate_password()
            firebase_uid: str | None = None
            firebase_error: str | None = None

            try:
                firebase_uid = firebase_admin_sdk.create_firebase_user(
                    email=item.email.strip(),
                    password=password,
                    display_name=item.node_name,
                )
            except firebase_admin_sdk.EmailAlreadyExistsError:
                # Email already in Firebase — fl_client record and membership are still
                # created; the client signs in with their existing account.
                logger.info("Firebase user already exists for %s; continuing.", item.email)
                firebase_uid = None
                firebase_error = None
            except firebase_admin_sdk.OperationNotAllowedError as exc:
                # Email/Password provider is disabled — surface a clear actionable error.
                firebase_error = str(exc)
                logger.error("Firebase OPERATION_NOT_ALLOWED for %s: %s", item.email, exc)
            except Exception as exc:  # pragma: no cover
                firebase_error = str(exc)
                logger.warning(
                    "Firebase user creation failed for %s: %s", item.email, exc
                )

            if firebase_error:
                results.append(
                    ClientProvisionResult(
                        node_name=item.node_name,
                        client_type=item.client_type,
                        status="error",
                        email=item.email,
                        error=firebase_error,
                    )
                )
                continue

            # Create fl_client record
            try:
                tenant_store.create_fl_client(
                    tenant_id=tenant_id,
                    client_id=client_id,
                    node_name=item.node_name,
                    department=department,
                    client_type=FLClientType.PERSON,
                    email=item.email.strip() if item.email else None,
                    firebase_uid=firebase_uid,
                    created_by_uid=admin_uid,
                )
            except Exception as exc:
                logger.exception("create_fl_client failed for %s", item.node_name)
                results.append(
                    ClientProvisionResult(
                        node_name=item.node_name,
                        client_type=item.client_type,
                        status="error",
                        email=item.email,
                        error=f"Failed to create FL client record: {exc}",
                    )
                )
                continue

            # Wire Firebase UID → tenant membership + client scope (if UID was obtained)
            if firebase_uid:
                try:
                    tenant_store.provision_client_user_access(
                        tenant_id=tenant_id,
                        firebase_uid=firebase_uid,
                        email=item.email.strip() if item.email else None,
                        display_name=item.node_name,
                        fl_client_ids=[client_id],
                    )
                except Exception as exc:
                    logger.warning(
                        "provision_client_user_access failed for %s: %s",
                        firebase_uid,
                        exc,
                    )
                    # Non-fatal; user can still accept an invite later.

            # Send credentials email
            email_error: str | None = None
            try:
                email_sender.send_client_credentials(
                    to_email=item.email.strip(),
                    node_name=item.node_name,
                    login_url=settings.frontend_base_url,
                    username=item.email.strip(),
                    password=password,
                    tenant_name=tenant_name,
                )
            except Exception as exc:
                email_error = str(exc)
                logger.warning("Email delivery failed for %s: %s", item.email, exc)

            results.append(
                ClientProvisionResult(
                    node_name=item.node_name,
                    client_type=item.client_type,
                    status="created" if not email_error else "email_failed",
                    client_id=client_id,
                    email=item.email,
                    firebase_uid=firebase_uid,
                    email_error=email_error,
                    identity_only=False,
                )
            )

        else:  # DEVICE
            try:
                tenant_store.create_fl_client(
                    tenant_id=tenant_id,
                    client_id=client_id,
                    node_name=item.node_name,
                    department=department,
                    client_type=FLClientType.DEVICE,
                    email=None,
                    firebase_uid=None,
                    created_by_uid=admin_uid,
                )
            except Exception as exc:
                logger.exception("create_fl_client (DEVICE) failed for %s", item.node_name)
                results.append(
                    ClientProvisionResult(
                        node_name=item.node_name,
                        client_type=item.client_type,
                        status="error",
                        error=f"Failed to create FL client record: {exc}",
                    )
                )
                continue

            results.append(
                ClientProvisionResult(
                    node_name=item.node_name,
                    client_type=item.client_type,
                    status="created",
                    client_id=client_id,
                    identity_only=settings.identity_only_provisioning,
                )
            )

    return results
