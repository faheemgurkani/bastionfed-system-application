from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import torch

from app.ml.models import DeepDNN


FEATURE_COLS = [f"feature_{i}" for i in range(320)]


@dataclass(frozen=True)
class ModelMetric:
    accuracy: float
    samples: int
    source: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _default_weights_dir() -> Path:
    return _repo_root() / "FL" / "weights"


def _default_client_csv_dir() -> Path:
    return _repo_root() / "FL"


def _parse_label_to_int(val: Any) -> int:
    s = str(val).strip().lower()
    if s in ("malware", "1", "true", "yes"):
        return 1
    if s in ("benign", "0", "false", "no"):
        return 0
    return 1 if "mal" in s else 0


@torch.no_grad()
def _eval_dnn_weight(weight_path: Path, csv_path: Path) -> ModelMetric:
    df = pd.read_csv(csv_path)
    missing = [c for c in (["label"] + FEATURE_COLS) if c not in df.columns]
    if missing:
        raise RuntimeError(f"CSV missing columns: {missing}")

    X = torch.tensor(df[FEATURE_COLS].values, dtype=torch.float32)
    y = torch.tensor([_parse_label_to_int(v) for v in df["label"].values], dtype=torch.int64)

    model = DeepDNN(input_dim=320)
    state = torch.load(weight_path, map_location="cpu")
    if isinstance(state, dict) and "state_dict" in state and isinstance(state["state_dict"], dict):
        state = state["state_dict"]
    model.load_state_dict(state, strict=True)
    model.eval()

    logits = model(X).squeeze(1)
    probs = torch.sigmoid(logits)
    pred = (probs >= 0.5).to(torch.int64)
    acc = float((pred == y).float().mean().item())

    return ModelMetric(accuracy=acc, samples=int(len(df)), source=str(csv_path.name))


@torch.no_grad()
def _eval_dnn_weight_many_csvs(weight_path: Path, csv_paths: list[Path]) -> ModelMetric:
    if not csv_paths:
        raise RuntimeError("No CSVs provided")
    frames = []
    for p in csv_paths:
        frames.append(pd.read_csv(p))
    df = pd.concat(frames, ignore_index=True)
    missing = [c for c in (["label"] + FEATURE_COLS) if c not in df.columns]
    if missing:
        raise RuntimeError(f"CSV missing columns: {missing}")

    X = torch.tensor(df[FEATURE_COLS].values, dtype=torch.float32)
    y = torch.tensor([_parse_label_to_int(v) for v in df["label"].values], dtype=torch.int64)

    model = DeepDNN(input_dim=320)
    state = torch.load(weight_path, map_location="cpu")
    if isinstance(state, dict) and "state_dict" in state and isinstance(state["state_dict"], dict):
        state = state["state_dict"]
    model.load_state_dict(state, strict=True)
    model.eval()

    logits = model(X).squeeze(1)
    probs = torch.sigmoid(logits)
    pred = (probs >= 0.5).to(torch.int64)
    acc = float((pred == y).float().mean().item())

    src = ",".join([p.name for p in csv_paths])
    return ModelMetric(accuracy=acc, samples=int(len(df)), source=src)


def get_model_metrics() -> dict[str, Any]:
    """
    Compute simple offline metrics for weights that can be evaluated from FV CSVs.

    Currently supports:
    - fl_global_dnn.pth -> fl-dnn-v1
    - client_{N}_round_5_dnn.pth (evaluated on FL/client_{N}_data.csv) -> client-N-dnn

    ResNet / MetaFusion require the image dataset, which is not present here.
    """
    weights_dir = _default_weights_dir()
    csv_dir = _default_client_csv_dir()
    sample_csv = csv_dir / "sample_data.csv"

    out: dict[str, Any] = {
        "available": True,
        "note": "DNN accuracies computed from FL/sample_data.csv. ResNet/Meta require image dataset.",
        "models": {},
    }

    if not weights_dir.exists():
        return {"available": False, "message": f"weights dir not found: {weights_dir}"}

    if not sample_csv.exists():
        return {
            "available": False,
            "message": f"sample CSV not found: {sample_csv}",
        }

    # Global DNN
    global_w = weights_dir / "fl_global_dnn.pth"
    if global_w.exists():
        m = _eval_dnn_weight(global_w, sample_csv)
        out["models"]["fl-dnn-v1"] = {
            "accuracy": round(m.accuracy * 100, 2),
            "samples": m.samples,
            "source": m.source,
        }

    # Client DNNs
    for w in sorted(weights_dir.glob("client_*_round_*_dnn.pth")):
        name = w.name
        parts = name.split("_")
        if len(parts) < 2:
            continue
        try:
            cid = int(parts[1])
        except Exception:
            continue
        metric = _eval_dnn_weight(w, sample_csv)
        out["models"][f"client-{cid}-dnn"] = {
            "accuracy": round(metric.accuracy * 100, 2),
            "samples": metric.samples,
            "source": metric.source,
        }

    if not out["models"]:
        out["available"] = False
        out["message"] = "No evaluatable DNN weights found in FL/weights."

    return out

