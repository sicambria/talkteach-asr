# Cloud fallback — one-tap remote training (#27)

On a GPU-less laptop the director picks `whisper-tiny` int8 on CPU: it works, but
a real fine-tune is slow. Cloud fallback lets a grown-up tap once to run the
*same* training job on a borrowed GPU (a Colab notebook or a remote worker) and
watch the same "getting smarter" meter advance — then pull the trained model back.

This feature is **off by default** and gated behind explicit consent, because it
is the one path where a child's voice recordings leave the device.

## Architecture

```
device                                   remote GPU (Colab / worker)
  manifest [{path,text}] + clips  ──►  same TrainingPlan, same engine adapter
  poll / stream progress         ◄──  TrainProgress heartbeats
  download trained model         ◄──  PEFT adapter / merged CT2 export
```

The remote runs the **identical** `ASREngine.train(plan, manifest, workdir)` — the
director still decides the plan locally, so behaviour matches the on-device path
exactly. Only the execution host changes. Progress streams back over the same
`TrainProgress` shape the UI already renders; the result returns as the same
exportable model (`EXPORT.md`).

## Privacy — the hard part (D-008)

Children's voice data leaving the device is a serious step, so:

- **Explicit, informed opt-in per run.** A plain-language consent card names *what*
  is uploaded (the clips + transcripts), *where*, and that it can be deleted.
  Never silent, never a default, never remembered without asking.
- **Minimise & clean up.** Upload only the clips needed; delete remote copies when
  the run finishes or is cancelled.
- **No telemetry rides along.** Cloud training is a user-initiated transfer, not a
  phone-home; it stays separate from the off-by-default telemetry posture (D-008).

## CSP implications (D-005)

The Tauri CSP is locked to the local backend origin (`127.0.0.1:8756` + `ws:`).
A remote endpoint is a *new network target*, so enabling cloud fallback **must
explicitly widen `connect-src`** to that endpoint — and only that endpoint. This
is the precedent set in `SIDECAR.md` ("a future remote feature must widen the
CSP explicitly"); the widening ships with the feature, scoped as narrowly as
possible, and is documented in its own decision entry.

## Why off by default

It contradicts the headline promise — offline, private, child-safe — unless the
user deliberately chooses it. So it is an *escape hatch* for the GPU-less case,
surfaced as "this could be faster on a borrowed GPU — ask a grown-up", never the
default route.

## Status

**Tier C** (#27). Design only — no remote endpoint, consent UI, or CSP widening is
built yet. It depends on the real training loop (done, Tier B) and a chosen remote
runtime (Colab template or a small worker), both pending a GPU host.
