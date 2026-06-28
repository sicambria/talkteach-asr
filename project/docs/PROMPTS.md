# Karaoke prompt sets (roadmap #21)

Reading a known sentence aloud is the fastest way to collect clean, *labelled*
audio: the prompt **is** the transcript, so Screen 2 has ground truth to check
against (and Screen 1 can pre-fill the correction).

- `backend/talkteach/prompts/` ships a small, **CC0** (public-domain) starter set
  of short, kid-friendly, phonetically varied sentences per language (en/es/de),
  with English fallback so the flow never blocks on an unsupported language.
- `GET /api/prompts?lang=en&n=8` returns sentences + the available languages.
- The UI shows one sentence at a time with an "another sentence" button; after a
  clip is recorded for a prompt, the prompt text becomes that clip's transcript.

## Expanding the set

The full product seeds these from the **Common Voice CC0 sentence corpus**
(CC0-licensed, so freely redistributable). To add a language, drop a list into
`PROMPT_SETS` keyed by ISO 639-1 code, or load Common Voice's
`sentences.tsv` for that locale and filter to short, simple sentences. Keep them
CC0 / public-domain to stay redistributable (see `THIRD_PARTY.md`).
</content>
