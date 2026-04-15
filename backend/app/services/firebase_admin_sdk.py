"""Firebase user-provisioning via the Identity Toolkit REST API.

Uses the web API key (NEXT_PUBLIC_FIREBASE_API_KEY / FIREBASE_API_KEY) that is
already in .env — no service-account key or Admin SDK setup is required.

Endpoints used:
  POST /v1/accounts:signUp?key=…   — create a new email/password user
  POST /v1/accounts:delete?key=…   — delete a user (cleanup / rollback)
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_TOOLKIT_BASE = "https://identitytoolkit.googleapis.com/v1"


# ── Custom exceptions ──────────────────────────────────────────────────────────

class FirebaseUserError(Exception):
    """Raised when the Identity Toolkit API returns an error."""
    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code


class EmailAlreadyExistsError(FirebaseUserError):
    """The email is already registered in this Firebase project."""


class OperationNotAllowedError(FirebaseUserError):
    """Email/Password sign-in is disabled in the Firebase Console.

    Fix: Firebase Console → Authentication → Sign-in method → Email/Password → Enable.
    """


# ── Internal helpers ───────────────────────────────────────────────────────────

def _api_key() -> str:
    from app.config import settings  # noqa: PLC0415

    key = settings.firebase_api_key
    if not key or not key.strip():
        raise RuntimeError(
            "Firebase API key is not configured. "
            "Set NEXT_PUBLIC_FIREBASE_API_KEY (or FIREBASE_API_KEY) in your .env file."
        )
    return key.strip()


def _parse_error(body: dict[str, Any]) -> str:
    """Extract the error message string from an Identity Toolkit error response."""
    err = body.get("error", {})
    return str(err.get("message", "UNKNOWN_ERROR"))


# ── Public API ─────────────────────────────────────────────────────────────────

def create_firebase_user(
    email: str,
    password: str,
    display_name: str | None = None,  # noqa: ARG001 — not settable via signUp; kept for API compat
) -> str:
    """Create a Firebase Auth email/password user and return their UID.

    Uses POST /v1/accounts:signUp with the project's web API key.
    The created account is unverified (emailVerified=false); the client will
    sign in via the credential-entry form and verify later if required.

    Raises:
        RuntimeError:            NEXT_PUBLIC_FIREBASE_API_KEY not set.
        EmailAlreadyExistsError: email already registered.
        FirebaseUserError:       any other Identity Toolkit error.
        httpx.HTTPError:         network-level failure.
    """
    key = _api_key()
    url = f"{_TOOLKIT_BASE}/accounts:signUp?key={key}"
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": False,
    }

    with httpx.Client(timeout=15) as client:
        resp = client.post(url, json=payload)

    if resp.status_code == 200:
        data: dict[str, Any] = resp.json()
        uid = data.get("localId")
        if not uid:
            raise FirebaseUserError(
                "Firebase returned 200 but response contained no localId"
            )
        logger.info("Created Firebase user uid=%s email=%s", uid, email)
        return str(uid)

    # Error path
    try:
        body: dict[str, Any] = resp.json()
    except Exception:
        body = {}

    code = _parse_error(body)
    msg = f"Firebase user creation failed ({code}): {email}"

    if code == "EMAIL_EXISTS":
        raise EmailAlreadyExistsError(msg, code=code)

    if code == "OPERATION_NOT_ALLOWED":
        raise OperationNotAllowedError(
            "Email/Password sign-in is disabled in Firebase. "
            "Go to Firebase Console → Authentication → Sign-in method → "
            "Email/Password → Enable, then try again.",
            code=code,
        )

    raise FirebaseUserError(msg, code=code)


def firebase_admin_available() -> bool:
    """Return True if the Firebase API key is configured (best-effort check)."""
    try:
        _api_key()
        return True
    except RuntimeError:
        return False
