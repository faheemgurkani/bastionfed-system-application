"""
Dataset loader for the BastionFed fusion dataset.
Loads the balanced CSV, fits a StandardScaler, and provides
O(1) sha256 -> scaled feature vector lookup for inference.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

_DEFAULT_CSV = Path(__file__).resolve().parents[3] / "data" / "Final Balanced Dataset.csv"

_scaler: Optional[StandardScaler] = None
_feature_lookup: dict[str, np.ndarray] = {}
_data_loaded = False

FEATURE_COLS = [f"feature_{i}" for i in range(320)]


def load_dataset(csv_path: Path | None = None) -> None:
    global _scaler, _feature_lookup, _data_loaded
    if _data_loaded:
        return

    path = Path(os.environ.get("BASTIONFED_DATASET_CSV", str(csv_path or _DEFAULT_CSV)))

    if not path.exists():
        logger.warning("Dataset CSV not found at %s — DNN branch will use neutral placeholder", path)
        _data_loaded = True
        return

    logger.info("Loading dataset from %s ...", path)
    df = pd.read_csv(path, usecols=["sha256"] + FEATURE_COLS, dtype={c: "float32" for c in FEATURE_COLS})
    df["sha256"] = df["sha256"].str.strip().str.lower()

    X = df[FEATURE_COLS].values.astype(np.float32)

    _scaler = StandardScaler()
    X_scaled = _scaler.fit_transform(X).astype(np.float32)

    _feature_lookup = {sha: X_scaled[i] for i, sha in enumerate(df["sha256"])}

    logger.info("Dataset loaded: %d samples, scaler fitted", len(_feature_lookup))
    _data_loaded = True


def get_feature_vector(sha256: str) -> Optional[list[float]]:
    """Return scaled 320-dim feature vector for a sha256 hash, or None if not found."""
    if not _data_loaded:
        load_dataset()
    vec = _feature_lookup.get(sha256.strip().lower())
    if vec is None:
        return None
    return vec.tolist()


def data_loaded() -> bool:
    return _data_loaded and _scaler is not None
