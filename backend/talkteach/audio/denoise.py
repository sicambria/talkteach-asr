"""Optional denoise for noisy uploads (roadmap #30) — Tier C scaffold.

A noisy recording can be cleaned with DeepFilterNet (MIT/Apache) or Demucs (MIT)
before quality analysis. This is **opt-in and never destructive**: we write a
cleaned copy and keep the original, so the user's recording is never lost or
silently altered. Heavy deps are guarded; without them this is a no-op that
returns the input path unchanged.
"""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path


def denoise_available() -> bool:
    return (
        importlib.util.find_spec("df") is not None or importlib.util.find_spec("demucs") is not None
    )


def denoise_file(src_path: str, out_path: str | None = None) -> str:
    """Write a denoised copy of ``src_path``; return its path.

    Falls back to copying the file unchanged when no denoise backend is installed
    (so callers can always use the returned path). The original is never modified.
    """
    dst = out_path or str(Path(src_path).with_suffix(".denoised.wav"))
    if importlib.util.find_spec("df") is not None:
        # DeepFilterNet path (scaffold): enhance() the loaded audio and write dst.
        from df.enhance import enhance, init_df, load_audio, save_audio  # type: ignore

        model, df_state, _ = init_df()
        audio, _ = load_audio(src_path, sr=df_state.sr())
        save_audio(dst, enhance(model, df_state, audio), df_state.sr())
        return dst
    # No backend → non-destructive passthrough (copy, keep original).
    shutil.copyfile(src_path, dst)
    return dst
