"""
Compares ResNet inference accuracy between fp32 and fp16 weights.
Uses bigram DCT PNG images from Benign Clean / Malware Clean folders.

Usage:
    python compare_fp16_fp32.py
"""
import random
import sys
from pathlib import Path

import torch
import torch.nn.functional as F
from PIL import Image
from torchvision import transforms, models
import torch.nn as nn

# ── config ────────────────────────────────────────────────────────────────────
FP32_WEIGHTS  = Path(__file__).parent / "app/ml/weights/fl_global_resnet.pth"
FP16_WEIGHTS  = Path("/Users/hunain/Downloads/weights 3/fl_global_resnet.pth")
BENIGN_DIR    = Path("/Users/hunain/Downloads/Benign Clean")
MALWARE_DIR   = Path("/Users/hunain/Downloads/Malware Clean")
N_SAMPLES     = 100   # images per class (200 total)
SEED          = 42
# ──────────────────────────────────────────────────────────────────────────────

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


def build_resnet():
    m = models.resnet50(weights=None)
    m.fc = nn.Linear(m.fc.in_features, 2)
    return m


def load_model(weights_path: Path, use_fp16: bool) -> nn.Module:
    m = build_resnet().to(DEVICE)
    state = torch.load(weights_path, map_location=DEVICE, weights_only=False)
    m.load_state_dict(state)
    if use_fp16:
        m = m.half()
    m.eval()
    return m


def predict(model: nn.Module, img_path: Path, use_fp16: bool) -> int:
    img = Image.open(img_path).convert("RGB")
    tensor = TRANSFORM(img).unsqueeze(0).to(DEVICE)
    if use_fp16:
        tensor = tensor.half()
    with torch.no_grad():
        prob = F.softmax(model(tensor), dim=1)[0, 1].item()
    return 1 if prob >= 0.5 else 0


def evaluate(model: nn.Module, use_fp16: bool, samples: list) -> dict:
    correct = 0
    for img_path, label in samples:
        pred = predict(model, img_path, use_fp16)
        if pred == label:
            correct += 1
    return {
        "accuracy": round(correct / len(samples) * 100, 2),
        "correct": correct,
        "total": len(samples),
    }


def main():
    # Validate paths
    for p, name in [(FP32_WEIGHTS, "FP32 weights"), (FP16_WEIGHTS, "FP16 weights"),
                    (BENIGN_DIR, "Benign dir"), (MALWARE_DIR, "Malware dir")]:
        if not p.exists():
            print(f"ERROR: {name} not found: {p}")
            sys.exit(1)

    # Sample images
    random.seed(SEED)
    benign_imgs  = random.sample(list(BENIGN_DIR.glob("*.png")), N_SAMPLES)
    malware_imgs = random.sample(list(MALWARE_DIR.glob("*.png")), N_SAMPLES)
    samples = [(p, 0) for p in benign_imgs] + [(p, 1) for p in malware_imgs]
    random.shuffle(samples)

    print(f"Device: {DEVICE}")
    print(f"Samples: {len(samples)} ({N_SAMPLES} benign + {N_SAMPLES} malware)\n")

    # FP32
    print("Loading FP32 model...")
    model_fp32 = load_model(FP32_WEIGHTS, use_fp16=False)
    res_fp32 = evaluate(model_fp32, use_fp16=False, samples=samples)
    print(f"FP32 → Accuracy: {res_fp32['accuracy']}%  ({res_fp32['correct']}/{res_fp32['total']})")
    del model_fp32

    # FP16
    print("\nLoading FP16 model (converting fp32 weights to half)...")
    model_fp16 = load_model(FP16_WEIGHTS, use_fp16=True)
    res_fp16 = evaluate(model_fp16, use_fp16=True, samples=samples)
    print(f"FP16 → Accuracy: {res_fp16['accuracy']}%  ({res_fp16['correct']}/{res_fp16['total']})")
    del model_fp16

    # Summary
    diff = round(res_fp32['accuracy'] - res_fp16['accuracy'], 2)
    print(f"\n{'='*40}")
    print(f"Accuracy drop (fp32 → fp16): {diff}%")
    if abs(diff) <= 0.5:
        print("Verdict: negligible difference — fp16 is safe to use")
    else:
        print("Verdict: noticeable difference — consider keeping fp32")


if __name__ == "__main__":
    main()
