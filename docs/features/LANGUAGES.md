# Languages

TalkTeach separates two ideas people often conflate:

- **Speech language** — the language the *model learns to recognise*. This is what
  you pick on the New-Project screen. Covered below.
- **Interface language** — the language the *app's buttons and text* are shown in.
  Today the UI is **English only**; the translation scaffold and plan live in
  [`I18N.md`](I18N.md).

## Speech languages you can train

Two tiers, chosen automatically by the director (`backend/talkteach/director/`):

1. **The ~99 Whisper languages (first-class).** When you pick one of these, the
   director fine-tunes a Whisper base for it. The full list is below, and it is
   served live to the app's searchable picker via `GET /api/languages` (single
   source of truth: `director/language.py::WHISPER_LANG_NAMES`).
2. **Any other language (via XLS-R).** If your language isn't in Whisper's set,
   the director switches the base model to **wav2vec2 / XLS-R** — a multilingual
   self-supervised model that fine-tunes well from scratch — so low-resource and
   even unwritten languages are trainable given enough audio
   (`director/policy.py`).
3. **"Let it figure out."** Leave the language unset and Whisper detects it at
   draft-transcription time (`probe_language(None)` → `auto_detect`).

### Where you choose it

On the **New Project** screen: seven friendly quick-picks (English, Spanish,
French, German, Hungarian, Italian, Romanian) with flags, a **search box for all
99 Whisper languages**, and a "Let it figure out the language by itself" toggle.

### The 99 first-class (Whisper) languages

Afrikaans (af), Albanian (sq), Amharic (am), Arabic (ar), Armenian (hy),
Assamese (as), Azerbaijani (az), Bashkir (ba), Basque (eu), Belarusian (be),
Bengali (bn), Bosnian (bs), Breton (br), Bulgarian (bg), Catalan (ca),
Chinese (zh), Croatian (hr), Czech (cs), Danish (da), Dutch (nl), English (en),
Estonian (et), Faroese (fo), Finnish (fi), French (fr), Galician (gl),
Georgian (ka), German (de), Greek (el), Gujarati (gu), Haitian Creole (ht),
Hausa (ha), Hawaiian (haw), Hebrew (he), Hindi (hi), Hungarian (hu),
Icelandic (is), Indonesian (id), Italian (it), Japanese (ja), Javanese (jw),
Kannada (kn), Kazakh (kk), Khmer (km), Korean (ko), Lao (lo), Latin (la),
Latvian (lv), Lingala (ln), Lithuanian (lt), Luxembourgish (lb),
Macedonian (mk), Malagasy (mg), Malay (ms), Malayalam (ml), Maltese (mt),
Maori (mi), Marathi (mr), Mongolian (mn), Myanmar (my), Nepali (ne),
Norwegian (no), Nynorsk (nn), Occitan (oc), Pashto (ps), Persian (fa),
Polish (pl), Portuguese (pt), Punjabi (pa), Romanian (ro), Russian (ru),
Sanskrit (sa), Serbian (sr), Shona (sn), Sindhi (sd), Sinhala (si),
Slovak (sk), Slovenian (sl), Somali (so), Spanish (es), Sundanese (su),
Swahili (sw), Swedish (sv), Tagalog (tl), Tajik (tg), Tamil (ta), Tatar (tt),
Telugu (te), Thai (th), Tibetan (bo), Turkish (tr), Turkmen (tk),
Ukrainian (uk), Urdu (ur), Uzbek (uz), Vietnamese (vi), Welsh (cy),
Yiddish (yi), Yoruba (yo).

> This table is generated from `WHISPER_LANG_NAMES`; if that map changes, the
> picker, the `/api/languages` response, and this list all change together.
