from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings


class FirebaseAuthError(Exception):
    pass


@dataclass
class VerifiedFirebaseToken:
    uid: str
    email: str | None
    name: str | None
    picture: str | None
    claims: dict[str, Any]


class FirebaseTokenVerifier:
    def __init__(self, *, cert_url: str | None = None) -> None:
        self._cert_url = cert_url or settings.firebase_cert_url
        self._jwk_client: Any | None = None
        self._last_refresh = 0.0

    def verify(self, token: str) -> VerifiedFirebaseToken:
        project_id = settings.firebase_project_id
        if not project_id:
            raise FirebaseAuthError("FIREBASE_PROJECT_ID or NEXT_PUBLIC_FIREBASE_PROJECT_ID must be configured")

        if settings.firebase_auth_emulator_uid:
            return VerifiedFirebaseToken(
                uid=settings.firebase_auth_emulator_uid,
                email=f"{settings.firebase_auth_emulator_uid}@example.test",
                name=settings.firebase_auth_emulator_uid,
                picture=None,
                claims={"sub": settings.firebase_auth_emulator_uid},
            )

        try:
            import jwt
            from jwt import PyJWKClient

            signing_key = self._get_jwk_client().get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=project_id,
                issuer=f"https://securetoken.google.com/{project_id}",
            )
        except Exception as exc:  # pragma: no cover - exact jwt exceptions are exercised indirectly
            raise FirebaseAuthError("Invalid Firebase ID token") from exc

        uid = str(claims.get("sub") or "").strip()
        if not uid:
            raise FirebaseAuthError("Firebase token missing subject")

        return VerifiedFirebaseToken(
            uid=uid,
            email=_claim_str(claims, "email"),
            name=_claim_str(claims, "name"),
            picture=_claim_str(claims, "picture"),
            claims=claims,
        )

    def _get_jwk_client(self):
        # Refresh occasionally so long-lived processes pick up new Google keys.
        if self._jwk_client is None or (time.time() - self._last_refresh) > 3600:
            self._prime_cert_url()
            from jwt import PyJWKClient

            self._jwk_client = PyJWKClient(_jwks_url_for_google())
            self._last_refresh = time.time()
        return self._jwk_client

    def _prime_cert_url(self) -> None:
        # Google exposes x509 cert metadata at this URL; a lightweight GET keeps failure mode explicit.
        with httpx.Client(timeout=10.0) as client:
            response = client.get(self._cert_url)
            response.raise_for_status()


def _claim_str(claims: dict[str, Any], key: str) -> str | None:
    value = claims.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _jwks_url_for_google() -> str:
    return "https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com"
