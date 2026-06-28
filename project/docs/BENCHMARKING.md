# Benchmarking — comparing ASR engines for real

`scripts/benchmark.py` (over `talkteach.benchmark`) generates real synthetic speech
with one or more TTS engines, trains each ASR engine on it, and reports **WER / CER /
train-time** on a **shared, held-out** eval set. This is how OSS ASR engines get
compared on the same footing instead of by reputation.

```bash
make setup-ml                               # backend[ml,export,tts,dev] + (system) espeak-ng
make report                                  # full run → ELO scoreboard → records benchmarks/REPORT.md
# or drive the CLI directly:
python scripts/benchmark.py --config benchmarks/quick.yaml            # prints matrix + scoreboard
python scripts/benchmark.py --config benchmarks/quick.yaml --report benchmarks/REPORT.md
python scripts/benchmark.py --config benchmarks/quick.yaml --train-clips 4 --eval-clips 3
```

`make report` (→ `scripts/full_report.sh`) runs fully automatically: it generates the
speech, fine-tunes every engine, scores them, prints the scoreboard, and writes
`benchmarks/REPORT.md` (committable) plus raw `results.json` under a temp workdir.

## The scoreboard (ELO + medals)

The run prints — and records — a leaderboard ranked by **ELO**, with the raw metrics
alongside and 🥇🥈🥉 on the top engines:

```
#     Engine    ELO   W-L-T    Win%  MeanWER  MeanCER  Train(s)  Conds
1  🥇  whisper   1043  9-2-1    82%   0.036    0.008    9.3       2
2  🥈  wav2vec2   957  2-9-1    18%   0.179    0.039    4.8       2
```

**Medals** are awarded by *competition ranking* (`benchmark.assign_medals`): engines
tied on ELO share a medal and the next distinct ELO takes the one below, so two engines
tied for first both get gold and silver is skipped. A two-engine matrix never reaches
bronze; widen it (e.g. `benchmarks/full.yaml` adds the GPU NeMo cell) for a full podium.
Control how many medals are handed out with the `medals:` config key or `--medals N`.

### Detail views

Beyond the headline table, the Markdown report and the in-app Arena also surface:

- **Easiest & hardest clip** per engine — the lowest- and highest-WER eval sentence it
  hit, so you can see exactly where a model shines or struggles.
- **Head-to-head grid** — how many shared clips each engine won against each other
  (the same per-(TTS, clip) outcomes that feed ELO).
- **Per-voice breakdown** — each engine's WER/CER/train-time split by TTS voice.
- **Δ vs base** — the WER drop from the *untrained* base checkpoint to the fine-tune
  (positive = training helped). Skipped (`—`) when the base can't be scored (e.g. NeMo)
  or under `TALKTEACH_FORCE_SIMULATION=1`.

### Multiple languages

The matrix has a **language axis**: pass `languages: [en, hu, …]` (config or the Arena's
language picker) and every (language × TTS × engine) cell runs, each spoken and scored in
**that language's own sentences** (`talkteach.prompts`, written per language — never an
English stand-in). espeak speaks any language by its code; piper runs only where a voice
is known (`benchmark._PIPER_VOICES`), others self-skip. ELO head-to-heads are grouped per
`(language, TTS)` so clips from different languages are never wrongly compared. Single
`language:` still works as the one-language default.

### In the app: the Arena

The same benchmark is exposed over HTTP and as the **Arena** screen (the app's default
landing view; 🏆 Arena / Wizard toggle in the header). Pick the languages, TTS voices, and
ASR engines to compare, press **Run**, and watch cells stream in to a medal podium with all
the detail views above. The top three engines always get 🥇🥈🥉 (ties share a medal). The
API (mirrors the training-job pattern; in-memory, transient):

```
GET  /api/benchmark/options      # providers, engines, languages — each with an `available`/code
POST /api/benchmark              # {languages, tts, engines, train_clips, eval_clips}
GET  /api/benchmark/{id}         # status + live scoreboard payload (partial as cells finish)
POST /api/benchmark/{id}/cancel
```

The JSON the API returns is `benchmark.scoreboard_payload(report)` — the single source the
CLI report and the Arena both render, so their numbers never diverge.

**WER/CER on the shared eval set are the ground truth; ELO is a presentation layer
on top.** LLM arenas use ELO because they have *no* objective metric — only pairwise
human preference. ASR has WER, so ELO here is a convenience, not a necessity. It still
earns its place: each engine plays one **match per (TTS, clip)** — it wins the clips it
transcribes with lower WER — so ELO aggregates across voices and clip difficulty into a
single familiar number, without a few brutal clips dominating a mean. Ratings come from
iterating those head-to-heads over shuffled passes (fixed seed, so it's reproducible).
With few eval clips ELO is *indicative*; widen the matrix (more voices, more clips) for a
stronger signal. Implementation: `talkteach.benchmark.compute_elo` / `scoreboard`.

## Methodology (why each piece matters)

- **Real speech, known transcript.** Prompts are spoken by a TTS provider; the prompt
  *is* the ground truth. WER measures recognition, not (as with sine tones) noise.
- **Disjoint, shared eval set.** Train and eval prompts never overlap, and *every*
  engine is scored on the *same* eval clips — not each engine's own internal split,
  which varies per run and makes cells incomparable.
- **Quality gate.** Generated clips pass through `audio.quality.analyze_file` (the same
  gate real recordings face); the good-fraction is reported so a bad voice can't
  silently poison the comparison.
- **Pinned hyperparameters.** Each cell's plan comes from
  `director.plan_config.plan_from_config`, *not* the director's hardware heuristics, so
  a comparison holds everything fixed except the engine.
- **WER/CER/train-time are the comparable axes.** Export formats differ per engine
  (Whisper→CTranslate2, wav2vec2→ONNX, NeMo→`.nemo`), so a single portable artifact is
  not the comparison — see [ENGINES.md](ENGINES.md).

## Config schema (`benchmarks/*.yaml`)

```yaml
name: quick
language: en            # single-language default…
languages: [en, hu]    # …or cover several; each read in its own sentences (optional)
train_clips: 6          # distinct karaoke prompts spoken for training
eval_clips: 4           # disjoint prompts; the SAME eval set for every engine
sample_rate: 16000
medals: 3               # how many top engines get 🥇🥈🥉 (ties share a medal)
tts:
  - provider: espeak    # any registered TTS provider
    voice: en
  - provider: piper
    voice: en_US-lessac-low
engines:
  - name: whisper       # label shown in the report
    plan:               # forwarded verbatim to plan_from_config (any TrainingPlan field)
      engine: whisper_lora
      base_checkpoint: openai/whisper-tiny
      epochs: 1
      lora_rank: 4
```

`--train-clips` / `--eval-clips` override the config. Unknown `plan` keys fail loudly
(typo protection). Providers/engines whose deps are missing are reported as
`skipped`, never crashing the matrix.

Optional top-level key `keep_artifacts: true` retains each cell's trained model on
disk (default `false`).

## Disk footprint

Each cell trains and **saves a full fine-tuned model** — small for a Whisper LoRA
adapter, but ~2.4 GB for `wav2vec2-base`. By default the benchmark **deletes a
cell's checkpoint as soon as it's scored**, so an N-cell matrix needs disk for *one*
model at a time, not N. Set `keep_artifacts: true` to keep them. `scripts/full_report.sh`
puts all generated audio/models under one temp workdir, does a pre-flight free-space
check, and prints the workdir size at the end.

> Why this matters: an earlier run that kept every checkpoint filled a per-user disk
> **quota**, which presents as a totally unresponsive shell (every command fails to
> write temp files) rather than an obvious "disk full". See the RCA in
> `LEARNINGS.md`. If a run dies oddly or the shell wedges, check `df` and free space
> (e.g. `rm -rf ~/.cache/huggingface`, delete old workdirs).

## Engine tiering (what "all real" actually means)

| Engine | Real training | CPU / CI-runnable | Notes |
|---|---|---|---|
| **whisper_lora** | ✅ | ✅ (whisper-tiny) | PEFT/LoRA `Seq2SeqTrainer`; default engine |
| **wav2vec2_ctc** | ✅ | ✅ (wav2vec2-base) | `Wav2Vec2ForCTC` + CTC loss |
| **nemo_rnnt** | ✅ (real path) | ❌ GPU/opt-in only | needs `[nemo]` + CUDA; self-skips otherwise — never gates CI |

## CI

The default `pytest -q` job stays dependency-light (no ML) and is unchanged. A separate
`benchmark-smoke` CI job installs `backend[ml,tts]` + `espeak-ng` and runs the
**measurement-is-real** test (`pytest -m espeak`): base whisper-tiny transcribes clean
espeak speech with low WER, and tones with high WER — proving the gap discriminates,
without depending on a tiny fine-tune lowering WER (which is too noisy to assert).
Training-improvement checks are opt-in (`TALKTEACH_RUN_INTEGRATION=1`) with loose bounds.

See [TTS.md](TTS.md) for the speech generators and [ENGINES.md](ENGINES.md) for the
engine adapters.
