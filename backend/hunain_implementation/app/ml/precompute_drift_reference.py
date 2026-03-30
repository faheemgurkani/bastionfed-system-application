"""
One-time script — run once to generate drift_reference.npz.

Computes data-driven drift thresholds (τ) from the actual MaleX training distribution
instead of using fixed/guessed values.

Method (FARM framework / max-distance approach, 2024-2026):
  FV tau:  τ_fv  = max(mean |z-score|) across all 94k training feature vectors
  Img tau: τ_img = max(cosine distance to centroid) across all 94k training embeddings

3-state classification at runtime:
  STABLE:          score  ≤  0.9 × τ
  MONITORING:      0.9×τ  <  score  ≤  τ
  DRIFT_DETECTED:  score  >  τ

Usage:
    cd backend/hunain_implementation
    source .venv/bin/activate
    python -m app.ml.precompute_drift_reference
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms
from tqdm import tqdm

from app.ml.data import FEATURE_COLS, _DEFAULT_CSV, load_dataset
from app.ml.models import build_resnet

MALWARE_DIR = Path("/Users/hunain/SEM 7/FYP/fusion/weights and ipynb/Malware Clean")
BENIGN_DIR  = Path("/Users/hunain/SEM 7/FYP/fusion/weights and ipynb/Benign Clean")
OUTPUT_PATH = Path(__file__).parent / "weights" / "drift_reference.npz"
BATCH_SIZE  = 64

DEVICE = torch.device("mps" if torch.backends.mps.is_available() else
                       "cuda" if torch.cuda.is_available() else "cpu")

TRANSFORM = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])


class ImageFolderFlat(Dataset):
    def __init__(self, *dirs: Path):
        self.paths = []
        for d in dirs:
            if d.exists():
                self.paths.extend(sorted(d.glob("*.png")))

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, idx):
        img = Image.open(self.paths[idx]).convert("RGB")
        return TRANSFORM(img)


class ResNetEmbedder(nn.Module):
    """ResNet50 up to avgpool — outputs 2048-dim embedding per image."""
    def __init__(self, resnet: nn.Module):
        super().__init__()
        self.backbone = nn.Sequential(*list(resnet.children())[:-1])

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.backbone(x).squeeze(-1).squeeze(-1)


def welford_update(count, mean, M2, new_val):
    """Online mean + variance via Welford's algorithm."""
    count += 1
    delta = new_val - mean
    mean += delta / count
    delta2 = new_val - mean
    M2 += delta * delta2
    return count, mean, M2


def main():
    print(f"Device: {DEVICE}")

    # ── 1. FV reference + tau from CSV ────────────────────────────────────────
    print("\n[1/3] Loading CSV for FV reference + tau computation...")
    import pandas as pd
    from sklearn.preprocessing import StandardScaler
    t0 = time.time()
    df = pd.read_csv(_DEFAULT_CSV, usecols=FEATURE_COLS,
                     dtype={c: "float32" for c in FEATURE_COLS})
    X = df.values.astype(np.float32)
    scaler = StandardScaler().fit(X)
    fv_mean = scaler.mean_.astype(np.float32)
    fv_std  = scaler.scale_.astype(np.float32)

    # Data-driven FV tau: max(mean |z-score|) across all training samples
    X_scaled   = scaler.transform(X)
    N          = len(X_scaled)
    fv_scores  = np.zeros(N, dtype=np.float32)
    for i in tqdm(range(N), desc="FV tau", unit="sample", ncols=90):
        fv_scores[i] = float(np.mean(np.abs(X_scaled[i])))
    fv_tau     = float(np.max(fv_scores))
    fv_tau_p95 = float(np.percentile(fv_scores, 95))
    print(f"   FV done in {time.time()-t0:.1f}s  shape={fv_mean.shape}")
    print(f"   FV score stats — mean: {fv_scores.mean():.4f}  max(τ): {fv_tau:.4f}  p95: {fv_tau_p95:.4f}")

    # ── 2. Image embeddings — Pass 1: compute centroid ────────────────────────
    print("\n[2/3] Pass 1 — extracting ResNet50 embeddings to compute centroid...")
    resnet = build_resnet().to(DEVICE)
    weights_path = Path(__file__).parent / "weights" / "fl_global_resnet.pth"
    resnet.load_state_dict(torch.load(weights_path, map_location=DEVICE, weights_only=False))
    embedder = ResNetEmbedder(resnet).to(DEVICE)
    embedder.eval()

    dataset = ImageFolderFlat(MALWARE_DIR, BENIGN_DIR)
    loader  = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=False,
                         num_workers=0, pin_memory=False)
    print(f"   Total images: {len(dataset)}")

    count = 0
    mean  = np.zeros(2048, dtype=np.float64)
    M2    = np.zeros(2048, dtype=np.float64)

    t0 = time.time()
    with torch.no_grad():
        for imgs in tqdm(loader, desc="Pass 1 — centroid", unit="batch", ncols=90):
            imgs = imgs.to(DEVICE)
            embs = embedder(imgs).cpu().numpy().astype(np.float64)
            for emb in embs:
                count, mean, M2 = welford_update(count, mean, M2, emb)

    img_emb_mean = mean.astype(np.float32)
    img_emb_std  = np.sqrt(M2 / count).astype(np.float32)
    print(f"   Pass 1 done in {time.time()-t0:.1f}s  centroid shape={img_emb_mean.shape}")

    # ── 3. Image tau — Pass 2: compute cosine distances from centroid ──────────
    print("\n[3/3] Pass 2 — computing cosine distances from centroid to get τ_img...")
    ref_norm  = img_emb_mean / (np.linalg.norm(img_emb_mean) + 1e-8)
    img_tau   = 0.0
    all_img_scores = []

    t0 = time.time()
    with torch.no_grad():
        for imgs in tqdm(loader, desc="Pass 2 — img tau ", unit="batch", ncols=90):
            imgs = imgs.to(DEVICE)
            embs = embedder(imgs).cpu().numpy().astype(np.float32)
            for emb in embs:
                emb_norm  = emb / (np.linalg.norm(emb) + 1e-8)
                cos_dist  = float(1.0 - np.dot(ref_norm, emb_norm))
                cos_dist  = max(0.0, min(1.0, cos_dist))
                all_img_scores.append(cos_dist)
                if cos_dist > img_tau:
                    img_tau = cos_dist

    img_scores_arr = np.array(all_img_scores, dtype=np.float32)
    img_tau_p95    = float(np.percentile(img_scores_arr, 95))
    print(f"   Pass 2 done in {time.time()-t0:.1f}s")
    print(f"   Img score stats — mean: {img_scores_arr.mean():.4f}  max(τ): {img_tau:.4f}  p95: {img_tau_p95:.4f}")

    # ── Save ──────────────────────────────────────────────────────────────────
    np.savez_compressed(
        OUTPUT_PATH,
        fv_mean=fv_mean,
        fv_std=fv_std,
        img_emb_mean=img_emb_mean,
        img_emb_std=img_emb_std,
        n_images=np.array(count),
        fv_tau=np.array(fv_tau, dtype=np.float32),
        img_tau=np.array(img_tau, dtype=np.float32),
    )
    print(f"\nSaved to {OUTPUT_PATH}  ({OUTPUT_PATH.stat().st_size / 1024:.1f} KB)")
    print(f"\nThresholds that will be used at runtime:")
    print(f"  FV  — STABLE ≤ {0.9*fv_tau:.4f} | MONITORING ≤ {fv_tau:.4f} | DRIFT > {fv_tau:.4f}")
    print(f"  Img — STABLE ≤ {0.9*img_tau:.4f} | MONITORING ≤ {img_tau:.4f} | DRIFT > {img_tau:.4f}")


if __name__ == "__main__":
    main()
