"""
FL inference service.
Loads fl_global_resnet.pth + fl_global_meta.pth at startup.
Accepts a bi-gram DCT PNG image and returns malware/benign prediction.
DNN branch requires a 320-dim feature vector; pass None to use neutral 0.5 placeholder.
"""
from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Optional

import torch
import torch.nn.functional as F
from PIL import Image
from torchvision import transforms

from app.ml.models import DeepDNN, MetaFusionNet, build_resnet

from app.ml.data import get_feature_vector, load_dataset

logger = logging.getLogger(__name__)

WEIGHTS_DIR = Path(__file__).parent / "weights"
DNN_INPUT_DIM = 320  # inferred from fl_global_dnn.pth first layer shape [1024, 320]

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

TRANSFORM = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

_resnet: Optional[torch.nn.Module] = None
_dnn: Optional[torch.nn.Module] = None
_meta: Optional[torch.nn.Module] = None
_loaded = False


def load_models() -> None:
    global _resnet, _dnn, _meta, _loaded
    if _loaded:
        return

    load_dataset()
    logger.info("Loading FL model weights from %s", WEIGHTS_DIR)

    _resnet = build_resnet().to(DEVICE)
    _resnet.load_state_dict(
        torch.load(WEIGHTS_DIR / "fl_global_resnet.pth", map_location=DEVICE, weights_only=False)
    )
    _resnet.eval()

    _dnn = DeepDNN(DNN_INPUT_DIM).to(DEVICE)
    _dnn.load_state_dict(
        torch.load(WEIGHTS_DIR / "fl_global_dnn.pth", map_location=DEVICE, weights_only=False)
    )
    _dnn.eval()

    _meta = MetaFusionNet().to(DEVICE)
    _meta.load_state_dict(
        torch.load(WEIGHTS_DIR / "fl_global_meta.pth", map_location=DEVICE, weights_only=False)
    )
    _meta.eval()

    _loaded = True
    logger.info("FL models loaded on %s", DEVICE)

    # Load drift reference (needs _resnet to build embedder)
    from app.ml.drift import load_drift_reference
    load_drift_reference(_resnet)


@torch.no_grad()
def predict_from_image(
    image_bytes: bytes | None = None,
    feature_vector: Optional[list[float]] = None,
    model_name: str = "fl-meta-v1",
) -> dict:
    load_models()

    img_prob: float | None = None
    dnn_prob: float | None = None

    # Map client-specific model names to their base model type
    # e.g. "client-2-resnet" → base_type="resnet", client_id=2
    base_type = model_name
    client_id: int | None = None
    if model_name.startswith("client-"):
        parts = model_name.split("-")  # ["client", "2", "resnet"]
        client_id = int(parts[1])
        base_type = parts[2]  # "meta", "resnet", or "dnn"

    needs_image = base_type in ("resnet", "meta", "fl-resnet-v1", "fl-meta-v1")
    needs_fv = base_type in ("dnn", "meta", "fl-dnn-v1", "fl-meta-v1")

    if needs_image and image_bytes:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img_tensor = TRANSFORM(img).unsqueeze(0).to(DEVICE)
        img_prob = F.softmax(_resnet(img_tensor), dim=1)[0, 1].item()

    if needs_fv and feature_vector is not None and len(feature_vector) == DNN_INPUT_DIM:
        fv = torch.tensor([feature_vector], dtype=torch.float32).to(DEVICE)
        dnn_prob = torch.sigmoid(_dnn(fv)).squeeze().item()

    # --- Compute final prediction based on active model ---
    if base_type in ("fl-resnet-v1", "resnet"):
        prob = img_prob if img_prob is not None else 0.5
        final_prob = prob
    elif base_type in ("fl-dnn-v1", "dnn"):
        prob = dnn_prob if dnn_prob is not None else 0.5
        final_prob = prob
    else:
        img_val = img_prob if img_prob is not None else 0.5
        dnn_val = dnn_prob if dnn_prob is not None else 0.5
        meta_input = torch.tensor([[dnn_val, img_val]], dtype=torch.float32).to(DEVICE)
        final_prob = _meta(meta_input).item()

    prediction = "MALWARE" if final_prob >= 0.5 else "BENIGN"
    confidence = final_prob if prediction == "MALWARE" else 1.0 - final_prob

    from app.ml.drift import compute_and_record
    drift = compute_and_record(feature_vector, image_bytes)

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


def models_loaded() -> bool:
    return _loaded
