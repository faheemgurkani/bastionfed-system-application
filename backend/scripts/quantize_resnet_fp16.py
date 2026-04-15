#!/usr/bin/env python3
"""
Convert ``fl_global_resnet.pth`` (float32 state_dict) to FP16 for ~50% smaller on-disk size.

Uses the same architecture as ``hunain_implementation.app.ml.models.build_resnet`` so keys match.

Default paths (only under ``backend/data/models``):

  - Input:  ``data/models/pytorch/global/fl_global_resnet.pth``
  - Output: ``data/models/pytorch/global/fl_global_resnet_fp16.pth``

``torch.load(..., weights_only=False)`` matches training-era checkpoints that may include non-weight metadata.

Usage::

  cd backend
  .venv/bin/python scripts/quantize_resnet_fp16.py
  .venv/bin/python scripts/quantize_resnet_fp16.py --in-place   # backs up .pth to .pth.fp32.bak then replaces
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
HUNAIN_ROOT = BACKEND_ROOT / "hunain_implementation"
MODELS_GLOBAL = BACKEND_ROOT / "data" / "models" / "pytorch" / "global"
DEFAULT_SRC = MODELS_GLOBAL / "fl_global_resnet.pth"
DEFAULT_DST = MODELS_GLOBAL / "fl_global_resnet_fp16.pth"


def main() -> int:
    if str(HUNAIN_ROOT) not in sys.path:
        sys.path.insert(0, str(HUNAIN_ROOT))

    import torch
    from app.ml.models import build_resnet

    p = argparse.ArgumentParser(description="FP16 quantize ResNet FL global checkpoint")
    p.add_argument("--src", type=Path, default=DEFAULT_SRC, help="Input .pth (state_dict)")
    p.add_argument("--dst", type=Path, default=DEFAULT_DST, help="Output .pth path")
    p.add_argument(
        "--in-place",
        action="store_true",
        help=f"Write FP16 to {DEFAULT_SRC.name}; backs up original to .fp32.bak beside it",
    )
    args = p.parse_args()

    src = args.src.resolve()
    if args.in_place:
        dst = src
        bak = src.with_suffix(src.suffix + ".fp32.bak")
    else:
        dst = args.dst.resolve()
        bak = None

    try:
        rel_src = src.relative_to(BACKEND_ROOT)
        rel_dst = dst.relative_to(BACKEND_ROOT)
    except ValueError:
        print("Paths must stay under backend/data/models (repo policy).", file=sys.stderr)
        return 1

    if not str(rel_src).replace("\\", "/").startswith("data/models/") or not str(rel_dst).replace("\\", "/").startswith(
        "data/models/"
    ):
        print("Refusing to read/write outside backend/data/models.", file=sys.stderr)
        return 1

    if not src.is_file():
        print(f"Missing input: {src}", file=sys.stderr)
        return 1

    raw = torch.load(src, map_location="cpu", weights_only=False)
    if isinstance(raw, torch.nn.Module):
        state = raw.state_dict()
    elif isinstance(raw, dict):
        state = raw
    else:
        print(f"Unexpected checkpoint type: {type(raw)}", file=sys.stderr)
        return 1

    model = build_resnet()
    model.load_state_dict(state, strict=True)
    model.half()
    sd_fp16 = model.state_dict()

    old_sz = src.stat().st_size
    if bak is not None:
        shutil.copy2(src, bak)
        print(f"Backup: {bak} ({bak.stat().st_size} bytes)")

    torch.save(sd_fp16, dst)
    new_sz = dst.stat().st_size
    print(f"Wrote {dst} ({new_sz} bytes, was {old_sz} bytes, ratio {new_sz / old_sz:.2%})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
