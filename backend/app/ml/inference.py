"""
FL inference: global bundle (legacy) + registry-backed weights from Supabase (per tenant).

Global defaults: BASTIONFED_WEIGHTS_DIR or app/ml/weights/.
Registry: downloads model_registry.storage_path (bucket/object) via service role, LRU-cached on disk.
"""
from __future__ import annotations

import hashlib
import io
import logging
import os
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any, Optional

import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image
from torchvision import transforms

from app.ml.data import load_dataset
from app.ml.models import DeepDNN, MetaFusionNet, build_resnet

logger = logging.getLogger(__name__)

WEIGHTS_DIR = Path(os.environ.get("BASTIONFED_WEIGHTS_DIR", str(Path(__file__).parent / "weights")))
MODEL_CACHE_DIR = Path(os.environ.get("BASTIONFED_MODEL_CACHE_DIR", str(WEIGHTS_DIR / "registry_cache")))
DNN_INPUT_DIM = 320
_MAX_REGISTRY_BUNDLES = max(1, int(os.environ.get("BASTIONFED_REGISTRY_CACHE_MAX", "8")))

DEVICE = torch.device(
    "mps" if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available()
    else "cuda" if torch.cuda.is_available()
    else "cpu"
)

TRANSFORM = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

_resnet: Optional[nn.Module] = None
_dnn: Optional[nn.Module] = None
_meta: Optional[nn.Module] = None
_fv_scaler = None
_loaded = False

_SUPABASE_MODEL_FILES = {
    "global/fl_global_resnet_fp16.pth": "fl_global_resnet.pth",
    "global/fl_global_dnn.pth": "fl_global_dnn.pth",
    "global/fl_global_meta.pth": "fl_global_meta.pth",
}

LEGACY_GLOBAL_MODEL_NAMES = frozenset({"fl-meta-v1", "fl-resnet-v1", "fl-dnn-v1"})

_registry_cache: OrderedDict[str, tuple[nn.Module, Optional[nn.Module], Optional[nn.Module], str]] = OrderedDict()
_registry_lock = threading.Lock()


def _download_from_supabase(object_key: str, dest: Path) -> bool:
    from app.config import settings
    from app.services.supabase_storage import download_storage_path_to_path

    full = f"{settings.supabase_models_bucket}/{object_key.strip().lstrip('/')}"
    return download_storage_path_to_path(full, dest)


def _ensure_weights() -> bool:
    needed = {
        "fl_global_resnet.pth": None,
        "fl_global_dnn.pth": None,
        "fl_global_meta.pth": None,
    }
    for supabase_key, local_name in _SUPABASE_MODEL_FILES.items():
        dest = WEIGHTS_DIR / local_name
        if dest.exists():
            needed[local_name] = dest
            continue
        if _download_from_supabase(supabase_key, dest):
            needed[local_name] = dest

    missing = [name for name, path in needed.items() if path is None or not (WEIGHTS_DIR / name).exists()]
    if missing:
        logger.warning("Missing model weights: %s — ML inference disabled", missing)
        return False
    return True


def load_models() -> None:
    global _resnet, _dnn, _meta, _fv_scaler, _loaded
    if _loaded:
        return

    load_dataset()

    if not _ensure_weights():
        return

    resnet_path = WEIGHTS_DIR / "fl_global_resnet.pth"
    dnn_path = WEIGHTS_DIR / "fl_global_dnn.pth"
    meta_path = WEIGHTS_DIR / "fl_global_meta.pth"

    logger.info("Loading FL model weights from %s", WEIGHTS_DIR)

    _resnet = build_resnet().to(DEVICE)
    _resnet.load_state_dict(torch.load(resnet_path, map_location=DEVICE, weights_only=False))
    _resnet.eval()

    _dnn = DeepDNN(DNN_INPUT_DIM).to(DEVICE)
    _dnn.load_state_dict(torch.load(dnn_path, map_location=DEVICE, weights_only=False))
    _dnn.eval()

    _meta = MetaFusionNet().to(DEVICE)
    _meta.load_state_dict(torch.load(meta_path, map_location=DEVICE, weights_only=False))
    _meta.eval()

    scaler_path = WEIGHTS_DIR / "fv_scaler.pkl"
    if scaler_path.exists():
        import joblib
        global _fv_scaler
        _fv_scaler = joblib.load(scaler_path)
        logger.info("FV scaler loaded from %s", scaler_path)
    else:
        logger.warning("fv_scaler.pkl not found — DNN will run on raw (unscaled) features")

    _loaded = True
    logger.info("FL models loaded on %s", DEVICE)

    from app.ml.drift import load_drift_reference
    load_drift_reference(_resnet)


def models_loaded() -> bool:
    return _loaded


def _cache_file_for_storage_path(storage_path: str) -> Path:
    h = hashlib.sha256(storage_path.encode()).hexdigest()[:28]
    tail = Path(storage_path.replace("\\", "/")).name
    return MODEL_CACHE_DIR / f"{h}__{tail}"


def _ensure_storage_file_local(storage_path: str) -> Path | None:
    dest = _cache_file_for_storage_path(storage_path)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    from app.services.supabase_storage import download_storage_path_to_path

    MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if download_storage_path_to_path(storage_path, dest):
        return dest
    return None


def _registry_cache_key(tenant_id: str, model_name: str, paths: tuple[str, ...]) -> str:
    return f"{tenant_id}::{model_name}::" + "::".join(paths)


def _load_torch_module(path: Path, factory: Any) -> nn.Module:
    m = factory().to(DEVICE) if callable(factory) else factory
    m.load_state_dict(torch.load(path, map_location=DEVICE, weights_only=False))
    m.eval()
    return m


def _get_registry_bundle_modules(
    tenant_id: str,
    model_name: str,
    payloads: list[dict[str, Any]],
) -> tuple[nn.Module, Optional[nn.Module], Optional[nn.Module], str]:
    """
    Returns (resnet_or_stub, dnn_or_none, meta_or_none, mode) where mode is fusion|image|fv.
    resnet is a real ResNet for image/fusion; for fv-only a placeholder Identity is returned for the first slot.
    """
    paths = tuple(sorted(str(p.get("storagePath") or "") for p in payloads))
    key = _registry_cache_key(tenant_id, model_name, paths)
    types = {str(p.get("type") or "").lower(): p for p in payloads}

    with _registry_lock:
        if key in _registry_cache:
            _registry_cache.move_to_end(key)
            r, d, m, mode = _registry_cache[key]
            return r, d, m, mode

    local_paths: dict[str, Path] = {}
    for p in payloads:
        sp = (p.get("storagePath") or "").strip()
        t = str(p.get("type") or "").lower()
        if not sp:
            raise ValueError("missing_storage_path")
        lp = _ensure_storage_file_local(sp)
        if lp is None:
            raise ValueError(f"download_failed:{sp}")
        local_paths[t] = lp

    if len(types) == 3 and "fusion" in types and "image" in types and "fv" in types:
        resnet = _load_torch_module(local_paths["image"], build_resnet)
        dnn = _load_torch_module(local_paths["fv"], lambda: DeepDNN(DNN_INPUT_DIM))
        meta = _load_torch_module(local_paths["fusion"], MetaFusionNet)
        bundle = (resnet, dnn, meta, "fusion")
    elif "image" in types and len(types) == 1:
        resnet = _load_torch_module(local_paths["image"], build_resnet)
        bundle = (resnet, None, None, "image")
    elif "fv" in types and len(types) == 1:
        dnn = _load_torch_module(local_paths["fv"], lambda: DeepDNN(DNN_INPUT_DIM))
        stub = nn.Identity().to(DEVICE)
        bundle = (stub, dnn, None, "fv")
    else:
        p0 = payloads[0]
        t0 = str(p0.get("type") or "").lower()
        lp0 = local_paths.get(t0) or next(iter(local_paths.values()))
        if t0 in ("dnn", "cnn", "custom") or "dnn" in model_name.lower():
            dnn = _load_torch_module(lp0, lambda: DeepDNN(DNN_INPUT_DIM))
            stub = nn.Identity().to(DEVICE)
            bundle = (stub, dnn, None, "fv")
        else:
            resnet = _load_torch_module(lp0, build_resnet)
            bundle = (resnet, None, None, "image")

    with _registry_lock:
        _registry_cache[key] = bundle
        _registry_cache.move_to_end(key)
        while len(_registry_cache) > _MAX_REGISTRY_BUNDLES:
            _registry_cache.popitem(last=False)

    r, d, m, mode = bundle
    return r, d, m, mode


def _predict_with_globals(
    image_bytes: bytes | None,
    feature_vector: Optional[list[float]],
    model_name: str,
    fl_client_id: Optional[str],
) -> dict:
    global _resnet, _dnn, _meta, _fv_scaler
    load_models()
    if not models_loaded() or _resnet is None or _dnn is None or _meta is None:
        return {
            "prediction": "BENIGN",
            "confidence": 0.0,
            "threatScore": 50.0,
            "imgProb": None,
            "dnnProb": None,
            "modelUsed": model_name,
            "dnnAvailable": False,
            "drift": {"available": False, "reason": "models_not_loaded"},
        }

    img_prob: float | None = None
    dnn_prob: float | None = None

    base_type = model_name
    if model_name.startswith("client-"):
        parts = model_name.split("-")
        base_type = parts[2] if len(parts) > 2 else model_name

    needs_image = base_type in ("resnet", "meta", "fl-resnet-v1", "fl-meta-v1")
    needs_fv = base_type in ("dnn", "meta", "fl-dnn-v1", "fl-meta-v1")

    if needs_image and image_bytes:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img_tensor = TRANSFORM(img).unsqueeze(0).to(DEVICE)
        img_prob = F.softmax(_resnet(img_tensor), dim=1)[0, 1].item()

    if needs_fv and feature_vector is not None and len(feature_vector) == DNN_INPUT_DIM:
        import numpy as np

        fv_arr = np.array([feature_vector], dtype=np.float32)
        if _fv_scaler is not None:
            fv_arr = _fv_scaler.transform(fv_arr)
        fv = torch.tensor(fv_arr, dtype=torch.float32).to(DEVICE)
        dnn_prob = torch.sigmoid(_dnn(fv)).squeeze().item()

    if base_type in ("fl-resnet-v1", "resnet"):
        final_prob = img_prob if img_prob is not None else 0.5
    elif base_type in ("fl-dnn-v1", "dnn"):
        final_prob = dnn_prob if dnn_prob is not None else 0.5
    else:
        img_val = img_prob if img_prob is not None else 0.5
        dnn_val = dnn_prob if dnn_prob is not None else 0.5
        meta_input = torch.tensor([[dnn_val, img_val]], dtype=torch.float32).to(DEVICE)
        final_prob = _meta(meta_input).item()

    prediction = "MALWARE" if final_prob >= 0.5 else "BENIGN"
    confidence = final_prob if prediction == "MALWARE" else 1.0 - final_prob

    from app.ml.drift import compute_and_record

    drift = compute_and_record(feature_vector, image_bytes, fl_client_id=fl_client_id, include_image_embedding_drift=True)

    return {
        "prediction": prediction,
        "confidence": round(confidence * 100, 2),
        "threatScore": round(final_prob * 100, 2),
        "imgProb": round(img_prob, 4) if img_prob is not None else None,
        "dnnProb": round(dnn_prob, 4) if dnn_prob is not None else None,
        "modelUsed": model_name,
        "dnnAvailable": feature_vector is not None,
        "drift": drift,
    }


@torch.no_grad()
def _predict_registry(
    tenant_id: str,
    model_name: str,
    image_bytes: bytes | None,
    feature_vector: Optional[list[float]],
    fl_client_id: Optional[str],
) -> dict:
    from app.store.tenant_store import PostgresTenantStore, tenant_store

    if not isinstance(tenant_store, PostgresTenantStore):
        raise ValueError("postgres_required")
    payloads = tenant_store.resolve_inference_registry_payloads(tenant_id, model_name)
    if not payloads:
        raise ValueError("registry_resolve_failed")

    resnet_m, dnn_m, meta_m, mode = _get_registry_bundle_modules(tenant_id, model_name, payloads)
    img_prob: float | None = None
    dnn_prob: float | None = None

    fv_scaler = None
    scaler_path = WEIGHTS_DIR / "fv_scaler.pkl"
    if scaler_path.exists():
        import joblib

        fv_scaler = joblib.load(scaler_path)

    if mode in ("fusion", "image") and image_bytes:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img_tensor = TRANSFORM(img).unsqueeze(0).to(DEVICE)
        img_prob = F.softmax(resnet_m(img_tensor), dim=1)[0, 1].item()

    if mode in ("fusion", "fv") and dnn_m is not None and feature_vector is not None and len(feature_vector) == DNN_INPUT_DIM:
        import numpy as np

        fv_arr = np.array([feature_vector], dtype=np.float32)
        if fv_scaler is not None:
            fv_arr = fv_scaler.transform(fv_arr)
        fv = torch.tensor(fv_arr, dtype=torch.float32).to(DEVICE)
        dnn_prob = torch.sigmoid(dnn_m(fv)).squeeze().item()

    if mode == "image":
        final_prob = img_prob if img_prob is not None else 0.5
    elif mode == "fv":
        final_prob = dnn_prob if dnn_prob is not None else 0.5
    else:
        img_val = img_prob if img_prob is not None else 0.5
        dnn_val = dnn_prob if dnn_prob is not None else 0.5
        if meta_m is None:
            final_prob = 0.5 * (img_val + dnn_val)
        else:
            meta_input = torch.tensor([[dnn_val, img_val]], dtype=torch.float32).to(DEVICE)
            final_prob = meta_m(meta_input).item()

    prediction = "MALWARE" if final_prob >= 0.5 else "BENIGN"
    confidence = final_prob if prediction == "MALWARE" else 1.0 - final_prob

    from app.ml.drift import compute_and_record

    drift = compute_and_record(
        feature_vector,
        image_bytes,
        fl_client_id=fl_client_id,
        include_image_embedding_drift=False,
    )

    return {
        "prediction": prediction,
        "confidence": round(confidence * 100, 2),
        "threatScore": round(final_prob * 100, 2),
        "imgProb": round(img_prob, 4) if img_prob is not None else None,
        "dnnProb": round(dnn_prob, 4) if dnn_prob is not None else None,
        "modelUsed": model_name,
        "dnnAvailable": feature_vector is not None,
        "drift": drift,
    }


@torch.no_grad()
def predict_from_image(
    image_bytes: bytes | None = None,
    feature_vector: Optional[list[float]] = None,
    model_name: str = "fl-meta-v1",
    fl_client_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
) -> dict:
    load_dataset()
    use_legacy = tenant_id is None or model_name in LEGACY_GLOBAL_MODEL_NAMES
    if use_legacy:
        return _predict_with_globals(image_bytes, feature_vector, model_name, fl_client_id)
    try:
        return _predict_registry(tenant_id, model_name, image_bytes, feature_vector, fl_client_id)
    except ValueError as exc:
        logger.warning("Registry inference failed (%s), falling back to globals if possible", exc)
        if model_name in LEGACY_GLOBAL_MODEL_NAMES:
            return _predict_with_globals(image_bytes, feature_vector, model_name, fl_client_id)
        return {
            "prediction": "BENIGN",
            "confidence": 0.0,
            "threatScore": 50.0,
            "imgProb": None,
            "dnnProb": None,
            "modelUsed": model_name,
            "dnnAvailable": False,
            "drift": {"available": False, "reason": str(exc)},
        }
