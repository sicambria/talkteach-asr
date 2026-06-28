# Multi-speaker / diarization (#33)

Today TalkTeach assumes one voice: `audio/quality.py::aggregate` hard-codes
`distinct_speakers=1` in the `DataProfile`. That's the right Phase-0 simplification
(a child teaching their own voice), but it breaks down the moment two kids share a
session or a parent demonstrates a sentence. Diarization — "who spoke when" —
lets TalkTeach split a mixed recording by speaker and either train per-speaker or
warn that the data is mixed.

## Backends

| Backend | License | Notes |
|---|---|---|
| **pyannote.audio** | MIT (code) | the de-facto OSS diarizer; **pretrained weights are gated** on Hugging Face and need an accepted user agreement — a real friction point for an offline, child-proof app |
| **NeMo diarization** | Apache-2.0 | ties into the Phase-2 NeMo stack (#25); no gated-weights step |

The gated-weights caveat matters: anything requiring an online agreement
acceptance conflicts with the offline promise, so NeMo or a permissively-licensed
pretrained model is preferable for a bundled build. pyannote is not yet listed in
`docs/THIRD_PARTY.md` — add it (with the gated-weights note) when a backend is
chosen.

## How it would feed the director

1. Run diarization on each multi-speaker take → speaker-labelled segments
   (`speaker_id`, `start_s`, `end_s`).
2. Cut **per-speaker clips** (reuse the `Segment` machinery shared with VAD #11 /
   alignment #12).
3. Count distinct labels and set `DataProfile.distinct_speakers` for real, instead
   of the hard-coded `1`. The director / sufficiency messaging can then say "we
   heard 2 different voices — teach them separately?" in plain language.

Per-speaker clips also enable per-speaker projects (#29): one diarized session can
seed multiple projects.

## Why Tier C, not now

Diarization is heavy (a second neural model), introduces the gated-weights snag,
and the core promise (one child, one voice) doesn't need it. It's a delight/scale
feature, not a correctness gap — so it stays a design until a permissively-bundled
backend and the per-speaker UX are worth building.

## Status

**Tier C** (#33). Design only. `distinct_speakers` is hard-coded to `1` in
`aggregate`; wiring a diarizer to set it for real, the per-speaker clip cutting,
and the backend choice (favouring non-gated weights) are all pending.
