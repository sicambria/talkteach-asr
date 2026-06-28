"""Language probe — pick the base checkpoint + tokenizer automatically.

Whisper covers ~99 languages well; for languages outside that set (or when the
user has lots of data for a hard language) the policy may prefer a self-supervised
multilingual base (XLS-R / wav2vec2) which fine-tunes better from scratch.
"""

from __future__ import annotations

from .types import LanguageProfile

# Whisper's supported languages: ISO-639-1 code → English display name.
# Source: the Whisper tokenizer's `LANGUAGES` table. This dict is the single
# source of truth — `WHISPER_LANGS` (membership, gates base-model choice) and the
# `/api/languages` endpoint that populates the UI picker both derive from it.
WHISPER_LANG_NAMES: dict[str, str] = {
    "en": "English",
    "zh": "Chinese",
    "de": "German",
    "es": "Spanish",
    "ru": "Russian",
    "ko": "Korean",
    "fr": "French",
    "ja": "Japanese",
    "pt": "Portuguese",
    "tr": "Turkish",
    "pl": "Polish",
    "ca": "Catalan",
    "nl": "Dutch",
    "ar": "Arabic",
    "sv": "Swedish",
    "it": "Italian",
    "id": "Indonesian",
    "hi": "Hindi",
    "fi": "Finnish",
    "vi": "Vietnamese",
    "he": "Hebrew",
    "uk": "Ukrainian",
    "el": "Greek",
    "ms": "Malay",
    "cs": "Czech",
    "ro": "Romanian",
    "da": "Danish",
    "hu": "Hungarian",
    "ta": "Tamil",
    "no": "Norwegian",
    "th": "Thai",
    "ur": "Urdu",
    "hr": "Croatian",
    "bg": "Bulgarian",
    "lt": "Lithuanian",
    "la": "Latin",
    "mi": "Maori",
    "ml": "Malayalam",
    "cy": "Welsh",
    "sk": "Slovak",
    "te": "Telugu",
    "fa": "Persian",
    "lv": "Latvian",
    "bn": "Bengali",
    "sr": "Serbian",
    "az": "Azerbaijani",
    "sl": "Slovenian",
    "kn": "Kannada",
    "et": "Estonian",
    "mk": "Macedonian",
    "br": "Breton",
    "eu": "Basque",
    "is": "Icelandic",
    "hy": "Armenian",
    "ne": "Nepali",
    "mn": "Mongolian",
    "bs": "Bosnian",
    "kk": "Kazakh",
    "sq": "Albanian",
    "sw": "Swahili",
    "gl": "Galician",
    "mr": "Marathi",
    "pa": "Punjabi",
    "si": "Sinhala",
    "km": "Khmer",
    "sn": "Shona",
    "yo": "Yoruba",
    "so": "Somali",
    "af": "Afrikaans",
    "oc": "Occitan",
    "ka": "Georgian",
    "be": "Belarusian",
    "tg": "Tajik",
    "sd": "Sindhi",
    "gu": "Gujarati",
    "am": "Amharic",
    "yi": "Yiddish",
    "lo": "Lao",
    "uz": "Uzbek",
    "fo": "Faroese",
    "ht": "Haitian Creole",
    "ps": "Pashto",
    "tk": "Turkmen",
    "nn": "Nynorsk",
    "mt": "Maltese",
    "sa": "Sanskrit",
    "lb": "Luxembourgish",
    "my": "Myanmar",
    "bo": "Tibetan",
    "tl": "Tagalog",
    "mg": "Malagasy",
    "as": "Assamese",
    "tt": "Tatar",
    "haw": "Hawaiian",
    "ln": "Lingala",
    "ha": "Hausa",
    "ba": "Bashkir",
    "jw": "Javanese",
    "su": "Sundanese",
}

# Membership set (gates base-model choice); derived so there is one source of truth.
WHISPER_LANGS: frozenset[str] = frozenset(WHISPER_LANG_NAMES)


def supported_languages() -> list[dict[str, str]]:
    """All Whisper-supported languages as ``{"code", "name"}``, sorted by name.

    Feeds the New-Project language picker via ``GET /api/languages``. Languages
    outside this set are still trainable — the director switches the base model
    to wav2vec2/XLS-R (see policy.py) — and ``code=None`` auto-detects.
    """
    return [
        {"code": code, "name": name}
        for code, name in sorted(WHISPER_LANG_NAMES.items(), key=lambda kv: kv[1])
    ]


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
