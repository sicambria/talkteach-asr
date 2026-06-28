#!/usr/bin/env python3
"""Build a shareable model pack (roadmap #34) — Tier C scaffold.

A "model pack" is a single zip a family can share or publish: the portable export
(CTranslate2/ONNX) + a metadata card (engine, base model, languages, measured
WER, license) so the recipient knows exactly what they're running. Publishing to
Hugging Face is a separate, consented step (see project/docs/MODEL_PACKS.md).

    python scripts/pack_model.py <export_dir> <out.zip> [--name ...] [--wer 0.12]
"""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path


def make_pack(export_dir: str, out_zip: str, *, name: str, wer: float | None) -> str:
    src = Path(export_dir)
    if not src.is_dir():
        raise SystemExit(f"export dir not found: {export_dir}")
    card = {
        "name": name,
        "engine": "whisper_lora",
        "format": "ctranslate2",
        "measured_wer": wer,
        "license": "GPL-3.0-or-later (app); model weights per base-model license",
        "note": "Built with TalkTeach. Offline-capable.",
    }
    out = Path(out_zip)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("model_card.json", json.dumps(card, indent=2))
        for f in src.rglob("*"):
            if f.is_file():
                zf.write(f, arcname=f"model/{f.relative_to(src)}")
    return str(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("export_dir")
    ap.add_argument("out_zip")
    ap.add_argument("--name", default="My voice model")
    ap.add_argument("--wer", type=float, default=None)
    args = ap.parse_args()
    path = make_pack(args.export_dir, args.out_zip, name=args.name, wer=args.wer)
    print(f"Wrote model pack → {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
