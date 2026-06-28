# Landscape currency — keeping the headline claim true (#45)

TalkTeach's reason to exist is one claim (Report Part C): *there is no end-to-end,
open-source, "next-next-finish" GUI that actually trains state-of-the-art ASR
models.* That claim was adversarially verified once (48 claims, 3-vote-checked) —
but it is the single most **perishable** thing in the whole project. A competitor
could ship next quarter and quietly invalidate the premise. This note is the
checklist and cadence to keep it honest, so the README and the report never drift
into a false boast.

## What to re-check

The claim has parts; a counter-example must satisfy *all* of them to falsify it:

1. **End-to-end** — record/import → train → use, in one tool (not a notebook, not
   a CLI pipeline).
2. **GUI / "next-next-finish"** — a non-expert, child-usable interface; no
   hyperparameters, no YAML.
3. **Open source** — a real OSS license, not "source-available" or a free tier of
   a hosted product.
4. **Trains** (not just runs/fine-tunes-via-API) — produces a model from the
   user's own data, locally.
5. **State-of-the-art ASR** — Whisper / Parakeet / wav2vec2-class, not a toy.

If a tool meets 1–5, the headline must change. If it meets some, record it as
adjacent prior art (and cite it fairly).

## Where to look

- GitHub topics/search: `speech-recognition`, `asr`, `whisper fine-tune gui`,
  `train asr`, trending repos.
- Hugging Face Spaces & community tools; NVIDIA NeMo / Riva announcements.
- Tauri/Electron desktop-ML apps; "no-code speech" launches on HN / Reddit
  r/MachineLearning / r/LocalLLaMA.
- The upstream stacks we build on (faster-whisper, sherpa-onnx, WhisperX) for a
  new official GUI.

## Cadence & recording the result

- **Quarterly** (and before any tagged release, `docs/RELEASING.md`).
- Re-run the relevant slice of the companion report's verification, then append a
  dated row below: date, who checked, sources scanned, verdict
  (**holds / weakened / falsified**), and any adjacent tools found.
- If **weakened/falsified**: open an issue, soften the README/report wording in
  the same PR, and (if falsified) reframe the project's differentiator (the
  director + reliability engineering, Report Part C) rather than the "only one"
  framing.

| Date | Checked by | Sources | Verdict | Notes |
|---|---|---|---|---|
| 2026-06-27 | report Part A | deep-research, 48 claims 3-vote-checked | holds | original verification |

## Status

**Tier A** (#45). This is a complete, ready-to-run process: the checklist, the
sources, the cadence, and the log table exist now. It carries no code dependency —
the only "pending" is the recurring discipline of running it each quarter and
appending a row.
