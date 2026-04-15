"""Upload binaries to Supabase Storage (forensics / models / artifacts) + signed downloads + bucket catalog."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def _encode_storage_object_path(object_key: str) -> str:
    """Path segments for /sign/{bucket}/{path} — encode each segment."""
    parts = object_key.strip("/").split("/")
    return "/".join(quote(p, safe="") for p in parts if p)


def _normalize_object_key(object_name: str) -> str:
    return _encode_storage_object_path(object_name.replace("\\", "/").strip("/"))


def _base_url() -> str:
    base = (settings.supabase_url or "").rstrip("/")
    return base


def list_storage_buckets() -> list[dict[str, Any]]:
    """GET /storage/v1/bucket — returns raw bucket objects (id, name, public, …)."""
    if not settings.supabase_storage_enabled:
        return []
    base = _base_url()
    key = settings.supabase_service_key or ""
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.get(
                f"{base}/storage/v1/bucket",
                headers={"Authorization": f"Bearer {key}", "apikey": key},
            )
            r.raise_for_status()
            rows = r.json()
        return rows if isinstance(rows, list) else []
    except Exception as exc:
        logger.warning("Supabase list buckets failed: %s", exc)
        return []


def upload_to_bucket(*, bucket: str, object_name: str, data: bytes, timeout_s: float = 120.0) -> str | None:
    """
    Upload bytes to a named bucket. Returns `bucket/object_key` on success, else None.
    """
    if not settings.supabase_storage_enabled:
        return None
    base = _base_url()
    key = settings.supabase_service_key or ""
    object_key = _normalize_object_key(object_name)
    if not object_key:
        return None
    path = f"{bucket}/{object_key}"
    url = f"{base}/storage/v1/object/{quote(bucket, safe='')}/{object_key}"
    try:
        with httpx.Client(timeout=timeout_s) as client:
            r = client.post(
                url,
                content=data,
                headers={
                    "Authorization": f"Bearer {key}",
                    "apikey": key,
                    "Content-Type": "application/octet-stream",
                    "x-upsert": "true",
                },
            )
            r.raise_for_status()
        return path
    except httpx.HTTPStatusError as exc:
        detail = ""
        try:
            detail = (exc.response.text or "")[:800]
        except Exception:
            pass
        logger.warning(
            "Supabase upload failed bucket=%s key=%s: %s %s",
            bucket,
            object_key,
            exc,
            detail,
        )
        return None
    except Exception as exc:
        logger.warning("Supabase upload failed bucket=%s key=%s: %s", bucket, object_key, exc)
        return None


def upload_forensics_bytes(*, data: bytes, object_name: str) -> str | None:
    """
    Upload to `forensics` bucket. Returns storage object path (bucket-relative), or None if skipped.
    """
    return upload_to_bucket(
        bucket=settings.supabase_forensics_bucket,
        object_name=object_name,
        data=data,
        timeout_s=120.0,
    )


def upload_model_bytes(*, data: bytes, object_name: str, timeout_s: float | None = None) -> str | None:
    t = timeout_s if timeout_s is not None else max(300.0, min(3600.0, 30.0 + (len(data) / (1024 * 1024)) * 15.0))
    return upload_to_bucket(
        bucket=settings.supabase_models_bucket,
        object_name=object_name,
        data=data,
        timeout_s=t,
    )


def upload_artifact_bytes(*, data: bytes, object_name: str) -> str | None:
    """Client training artifacts (PNG/JSON) — single bucket, path encodes tenant/client/label."""
    return upload_to_bucket(
        bucket=settings.supabase_artifacts_bucket,
        object_name=object_name,
        data=data,
        timeout_s=120.0,
    )


def create_signed_download_url(
    *,
    bucket: str,
    object_key: str,
    expires_in: int | None = None,
) -> str | None:
    """
    Time-limited URL for a private object (POST /storage/v1/object/sign/{bucket}/{path}).
    Returns full HTTPS URL, or None if storage disabled / error.
    """
    if not settings.supabase_storage_enabled:
        return None
    base = _base_url()
    key = settings.supabase_service_key or ""
    ttl = int(expires_in if expires_in is not None else settings.storage_signed_url_expires_s)
    enc = _encode_storage_object_path(object_key)
    if not enc:
        return None
    url = f"{base}/storage/v1/object/sign/{quote(bucket, safe='')}/{enc}"
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.post(
                url,
                json={"expiresIn": ttl},
                headers={
                    "Authorization": f"Bearer {key}",
                    "apikey": key,
                    "Content-Type": "application/json",
                },
            )
            r.raise_for_status()
            data = r.json()
    except Exception as exc:
        logger.warning("Supabase signed URL failed: %s", exc)
        return None
    signed = data.get("signedURL") or data.get("signedUrl")
    if not signed:
        return None
    if signed.startswith("http://") or signed.startswith("https://"):
        return signed
    if signed.startswith("/"):
        return f"{base}{signed}"
    return f"{base}/{signed.lstrip('/')}"


def parse_bucket_and_object(storage_path: str) -> tuple[str, str] | None:
    """
    Parse values like `forensics/sample.bin` → (`forensics`, `sample.bin`).
    """
    s = (storage_path or "").strip().strip("/")
    if "/" not in s:
        return None
    bucket, _, obj = s.partition("/")
    if not bucket or not obj:
        return None
    return bucket, obj
