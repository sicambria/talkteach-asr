# Shareable model packs & "Publish to Hugging Face" (#34)

A user who taught a great model should be able to *share* it — give it to
someone else, hand it to a teacher, or (deliberately) publish it. A **model pack** is
the unit of sharing: one self-describing zip the recipient can run offline.

## What a pack contains (`scripts/pack_model.py`)

```
pack.zip
├── model_card.json     # name, engine, format, measured WER, license, "built with TalkTeach"
└── model/…             # the portable export (CTranslate2 by default; ONNX optional)
```

`pack_model.py` zips an existing export dir (`EXPORT.md`) plus a
`model_card.json`. The card records the **measured WER** (so a recipient knows how
good it is), the engine/format, and licensing: the app is GPL-3.0-or-later, but
the model *weights* inherit the base model's license — the card states both, so
sharing never misrepresents what's being handed over.

```bash
python scripts/pack_model.py exports/1 my_voice_model.zip --name "Mia's voice" --wer 0.12
```

## Publish to Hugging Face — a separate, consented step

Sharing a file is local; publishing puts the user's voice model on the public
internet. So HF upload is its own button with its own gate:

- **Explicit consent (D-008).** A plain-language card: *this uploads your model to
  a public website where anyone can download it.* Never silent, never default.
  Especially important because the model encodes the user's voice characteristics.
- **CSP widening (D-005).** The Tauri CSP is locked to the local backend
  (`SIDECAR.md`). Talking to `huggingface.co` is a new network target, so the
  publish feature **must explicitly widen `connect-src`** to the HF API origin —
  and only that — shipped with the feature and scoped narrowly.
- **Flow.** `huggingface_hub` login token (entered by the user, stored
  locally) → create/select a repo → upload the pack contents + the model card as
  the README → return the URL.

Publishing the *pack* (not raw weights) means the license and provenance card
travel with it.

## Status

**Tier C** (#34). `scripts/pack_model.py` builds a real pack zip with a model card
today. The HF publish flow (consent UI, token handling, CSP widening, upload) is
pending — it depends on a real export to package and a deliberate choice to add a
network feature to an otherwise-offline app.
