"""
Concept drift detection — multimodal (FV + Image).

FV drift:    mean absolute z-score across 320 features vs training distribution.
Image drift: cosine distance between incoming ResNet embedding and reference centroid.
Combined:    average of normalised FV score and image score.

Thresholds (data-driven, loaded from drift_reference.npz):
  tau_fv  = max(mean |z-score|) across all training feature vectors
  tau_img = max(cosine distance to centroid) across all training images

  STABLE:          score  <= 0.9 * tau
  MONITORING:      0.9*tau < score <= tau
  DRIFT_DETECTED:  score  >  tau
"""
from __future__ import annotations

import copy
import io
import logging
import time
from collections import deque
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torchvision import transforms

logger = logging.getLogger(__name__)

REFERENCE_PATH = Path(__file__).parent / "weights" / "drift_reference.npz"

TRANSFORM = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

STABLE     = "STABLE"
MONITORING = "MONITORING"
DRIFT      = "DRIFT_DETECTED"

_FV_TAU_FALLBACK  = 1.6
_IMG_TAU_FALLBACK = 0.15

_fv_tau:  float = _FV_TAU_FALLBACK
_img_tau: float = _IMG_TAU_FALLBACK

_fv_mean:       Optional[np.ndarray] = None
_fv_std:        Optional[np.ndarray] = None
_img_emb_mean:  Optional[np.ndarray] = None
_img_emb_std:   Optional[np.ndarray] = None

_embedder: Optional[nn.Module] = None

_fv_scores:  deque = deque(maxlen=200)
_img_scores: deque = deque(maxlen=200)
_last_updated: float = 0.0
_n_reference_images: int = 0

# Per-client score tracking: {fl_client_id: {"fv": deque, "img": deque, "last_updated": float}}
_client_scores: dict = {}

_loaded = False
_device = torch.device(
    "mps" if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available()
    else "cuda" if torch.cuda.is_available()
    else "cpu"
)


def _fv_status(score: float) -> str:
    if score <= 0.9 * _fv_tau:
        return STABLE
    if score <= _fv_tau:
        return MONITORING
    return DRIFT


def _img_status(score: float) -> str:
    if score <= 0.9 * _img_tau:
        return STABLE
    if score <= _img_tau:
        return MONITORING
    return DRIFT


def _combined_status(score: float) -> str:
    # Combined score is normalised to [0, 1] (each modality divided by its own tau)
    if score <= 0.9:
        return STABLE
    if score <= 1.0:
        return MONITORING
    return DRIFT


def load_drift_reference(resnet_model: nn.Module) -> None:
    global _fv_mean, _fv_std, _img_emb_mean, _img_emb_std
    global _embedder, _loaded, _n_reference_images
    global _fv_tau, _img_tau

    if _loaded:
        return

    if not REFERENCE_PATH.exists():
        try:
            from app.config import settings
            import httpx
            from urllib.parse import quote
            if settings.supabase_storage_enabled:
                base = (settings.supabase_url or "").rstrip("/")
                key = settings.supabase_service_key or ""
                bucket = settings.supabase_models_bucket
                url = f"{base}/storage/v1/object/{quote(bucket, safe='')}/global/drift_reference.npz"
                with httpx.Client(timeout=60.0) as client:
                    r = client.get(url, headers={"Authorization": f"Bearer {key}", "apikey": key})
                    r.raise_for_status()
                REFERENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
                REFERENCE_PATH.write_bytes(r.content)
                logger.info("Downloaded drift_reference.npz from Supabase (%d bytes)", len(r.content))
        except Exception as exc:
            logger.warning("Supabase drift_reference.npz download failed: %s", exc)
    if not REFERENCE_PATH.exists():
        logger.warning("drift_reference.npz not found — drift detection disabled")
        return

    data = np.load(REFERENCE_PATH)
    _fv_mean      = data["fv_mean"].astype(np.float32)
    _fv_std       = np.maximum(data["fv_std"].astype(np.float32), 1e-8)
    _img_emb_mean = data["img_emb_mean"].astype(np.float32)
    _img_emb_std  = np.maximum(data["img_emb_std"].astype(np.float32), 1e-8)
    _n_reference_images = int(data["n_images"])

    if "fv_tau" in data:
        _fv_tau = float(data["fv_tau"])
        logger.info("Data-driven fv_tau loaded: %.4f", _fv_tau)
    else:
        logger.warning("fv_tau not in npz — using fallback %.4f", _FV_TAU_FALLBACK)

    if "img_tau" in data:
        _img_tau = float(data["img_tau"])
        logger.info("Data-driven img_tau loaded: %.4f", _img_tau)
    else:
        logger.warning("img_tau not in npz — using fallback %.4f", _IMG_TAU_FALLBACK)

    class _Embedder(nn.Module):
        def __init__(self, base):
            super().__init__()
            self.backbone = nn.Sequential(*list(copy.deepcopy(base).children())[:-1])
        def forward(self, x):
            return self.backbone(x).squeeze(-1).squeeze(-1)

    _embedder = _Embedder(resnet_model).to(_device)
    _embedder.eval()

    _loaded = True
    logger.info(
        "Drift reference loaded — %d reference images, FV dim=%d, Emb dim=%d, fv_tau=%.4f, img_tau=%.4f",
        _n_reference_images, len(_fv_mean), len(_img_emb_mean), _fv_tau, _img_tau,
    )


def compute_and_record(
    feature_vector: Optional[list[float]],
    image_bytes: Optional[bytes],
    fl_client_id: Optional[str] = None,
    *,
    include_image_embedding_drift: bool = True,
) -> dict:
    global _last_updated

    if not _loaded:
        return {"available": False}

    result: dict = {"available": True}

    if feature_vector is not None:
        fv = np.array(feature_vector, dtype=np.float32)
        fv_score = float(np.mean(np.abs((fv - _fv_mean) / _fv_std)))
        _fv_scores.append(fv_score)
        result["fvDriftScore"]  = round(fv_score, 4)
        result["fvStatus"]      = _fv_status(fv_score)
        result["fvTau"]         = round(_fv_tau, 4)
    else:
        result["fvDriftScore"]  = None
        result["fvStatus"]      = "N/A"
        result["fvTau"]         = round(_fv_tau, 4)

    if (
        include_image_embedding_drift
        and image_bytes is not None
        and _embedder is not None
        and _img_emb_mean is not None
    ):
        with torch.no_grad():
            img     = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            tensor  = TRANSFORM(img).unsqueeze(0).to(_device)
            emb     = _embedder(tensor).cpu().numpy().squeeze().astype(np.float32)

        ref_norm  = _img_emb_mean / (np.linalg.norm(_img_emb_mean) + 1e-8)
        emb_norm  = emb / (np.linalg.norm(emb) + 1e-8)
        cos_sim   = float(np.dot(ref_norm, emb_norm))
        img_score = float(1.0 - cos_sim)
        img_score = max(0.0, min(1.0, img_score))

        _img_scores.append(img_score)
        result["imgDriftScore"] = round(img_score, 4)
        result["imgStatus"]     = _img_status(img_score)
        result["imgTau"]        = round(_img_tau, 4)
    else:
        result["imgDriftScore"] = None
        result["imgStatus"]     = "N/A" if include_image_embedding_drift else "N/A (non-global ResNet)"
        result["imgTau"]        = round(_img_tau, 4)

    fv_s  = result.get("fvDriftScore")
    img_s = result.get("imgDriftScore")
    normed = [s for s in [
        min(fv_s / _fv_tau, 1.0) if fv_s is not None else None,
        min(img_s / _img_tau, 1.0) if img_s is not None else None,
    ] if s is not None]
    combined = float(np.mean(normed)) if normed else 0.0
    result["combinedDriftScore"] = round(combined, 4)
    result["combinedStatus"]     = _combined_status(combined)

    _last_updated = time.time()

    # Per-client tracking
    if fl_client_id:
        if fl_client_id not in _client_scores:
            _client_scores[fl_client_id] = {
                "fv": deque(maxlen=200),
                "img": deque(maxlen=200),
                "last_updated": 0.0,
            }
        c = _client_scores[fl_client_id]
        if fv_s is not None:
            c["fv"].append(fv_s)
        if img_s is not None:
            c["img"].append(img_s)
        c["last_updated"] = _last_updated

    return result


def get_drift_report() -> dict:
    if not _loaded:
        return {
            "available": False,
            "message": "Drift reference not loaded — place drift_reference.npz in weights dir",
        }

    import datetime
    from datetime import timezone

    def _summary(buf: deque, label: str, status_fn, tau: float) -> dict:
        if not buf:
            return {"model": label, "score": 0.0, "status": STABLE,
                    "samples": 0, "lastEvent": "No data yet", "tau": round(tau, 4)}
        arr   = np.array(buf)
        score = float(np.mean(arr))
        peak  = float(np.max(arr))
        return {
            "model":     label,
            "score":     round(score, 4),
            "peakScore": round(peak, 4),
            "status":    status_fn(score),
            "samples":   len(buf),
            "lastEvent": _ago(_last_updated),
            "tau":       round(tau, 4),
        }

    fv_row  = _summary(_fv_scores,  "fl-dnn-v1 (FV branch)",       _fv_status,  _fv_tau)
    img_row = _summary(_img_scores, "fl-resnet-v1 (Image branch)",  _img_status, _img_tau)

    combined_scores = []
    for a, b in zip(_fv_scores, _img_scores):
        normed_a = min(a / _fv_tau, 1.0)
        normed_b = min(b / _img_tau, 1.0)
        combined_scores.append((normed_a + normed_b) / 2)
    combined_buf = deque(combined_scores, maxlen=200)
    meta_row = _summary(combined_buf, "fl-meta-v1 (Fusion)", _combined_status, 1.0)

    all_scores = list(_fv_scores) + list(_img_scores)
    overall    = float(np.mean(all_scores)) if all_scores else 0.0

    return {
        "available":             True,
        "driftScores":           [fv_row, img_row, meta_row],
        "overallDrift":          round(overall, 4),
        "overallStatus":         _combined_status(overall / max(_fv_tau, _img_tau)),
        "driftDetected":         overall > _fv_tau or overall > _img_tau,
        "nReferenceImages":      _n_reference_images,
        "samplesAnalyzed":       max(len(_fv_scores), len(_img_scores)),
        "thresholds": {
            "fvTau":       round(_fv_tau, 4),
            "imgTau":      round(_img_tau, 4),
            "fvMonitor":   round(0.9 * _fv_tau, 4),
            "imgMonitor":  round(0.9 * _img_tau, 4),
        },
        "checkedAt": datetime.datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def get_per_client_drift() -> dict:
    import datetime as _dt
    from datetime import timezone as _tz

    clients = []
    for fl_client_id, c in _client_scores.items():
        fv_arr  = np.array(c["fv"],  dtype=np.float32) if c["fv"]  else None
        img_arr = np.array(c["img"], dtype=np.float32) if c["img"] else None

        fv_score  = float(np.mean(fv_arr))  if fv_arr  is not None else None
        img_score = float(np.mean(img_arr)) if img_arr is not None else None

        normed_fv  = min(fv_score  / _fv_tau,  1.0) if fv_score  is not None and _fv_tau  else None
        normed_img = min(img_score / _img_tau, 1.0) if img_score is not None and _img_tau else None
        normed = [v for v in [normed_fv, normed_img] if v is not None]
        combined = round(float(np.mean(normed)), 4) if normed else 0.0

        clients.append({
            "clientId": fl_client_id,
            "fvDrift": {
                "score": round(fv_score, 4) if fv_score is not None else None,
                "status": _fv_status(fv_score) if fv_score is not None else "N/A",
                "tau": round(_fv_tau, 4),
            },
            "imgDrift": {
                "score": round(img_score, 4) if img_score is not None else None,
                "status": _img_status(img_score) if img_score is not None else "N/A",
                "tau": round(_img_tau, 4),
            },
            "combinedScore": combined,
            "combinedStatus": _combined_status(combined),
            "samplesAnalyzed": max(len(c["fv"]), len(c["img"])),
            "lastEvent": _ago(c["last_updated"]),
        })

    return {
        "available": True,
        "clients": clients,
        "checkedAt": _dt.datetime.now(_tz.utc).isoformat().replace("+00:00", "Z"),
    }


def drift_loaded() -> bool:
    return _loaded


def _ago(ts: float) -> str:
    if ts == 0:
        return "No data yet"
    diff = time.time() - ts
    if diff < 60:
        return f"{int(diff)}s ago"
    if diff < 3600:
        return f"{int(diff/60)}m ago"
    return f"{int(diff/3600)}h ago"
