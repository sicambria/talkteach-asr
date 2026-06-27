"""Language probe — pick the base checkpoint + tokenizer automatically.

Whisper covers ~99 languages well; for languages outside that set (or when the
user has lots of data for a hard language) the policy may prefer a self-supervised
multilingual base (XLS-R / wav2vec2) which fine-tunes better from scratch.
"""

from __future__ import annotations

from .types import LanguageProfile

# Whisper's supported language codes (ISO 639-1). Source: Whisper tokenizer.
# Trimmed to the commonly-used set; membership only gates base-model choice.
WHISPER_LANGS: frozenset[str] = frozenset(
    """en zh de es ru ko fr ja pt tr pl ca nl ar sv it id hi fi vi he uk el ms cs
    ro da hu ta no th ur hr bg lt la mi ml cy sk te fa lv bn sr az sl kn et mk br
    eu is hy ne mn bs kk sq sw gl mr pa si km sn yo so af oc ka be tg sd gu am yi
    lo uz fo ht ps tk nn mt sa lb my bo tl mg as tt haw ln ha ba jw su""".split()
)


def probe_language(code: str | None) -> LanguageProfile:
    """Normalize a user language choice into a LanguageProfile.

    `code=None` means the user chose "Let it figure out" → auto language ID at
    draft-transcription time (Whisper detects it), so we treat it as Whisper-
    supported and flag auto_detect.
    """
    if code is None:
        return LanguageProfile(code=None, is_whisper_supported=True, auto_detect=True)
    norm = code.strip().lower()
    return LanguageProfile(
        code=norm,
        is_whisper_supported=norm in WHISPER_LANGS,
        auto_detect=False,
    )
