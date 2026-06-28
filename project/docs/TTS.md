# Synthetic speech (TTS) for testing & benchmarking

The product trains on **real recorded speech**. For automated end-to-end tests and
the engine benchmark we need audio with a *known* transcript and real phonetic
content, so word-error-rate means something. The old fixtures used sine **tones**
(`selftest.make_toy_dataset`): they exercise the plumbing, but a tone has no words,
so WER measured on them is noise. The `talkteach.tts` package fixes that by turning
karaoke prompts into intelligible speech whose ground truth is the prompt itself.

## Providers

All providers implement `talkteach.tts.base.TTSProvider` and emit **16 kHz mono PCM
WAV** (the format Whisper, the CTC engines, and `audio.quality` expect). Pick one by
name:

```python
from talkteach.tts import get_tts_provider
from talkteach.tts.dataset import synthesize_dataset

provider = get_tts_provider("piper")              # or "espeak"
manifest = synthesize_dataset(provider, "out/", language="en", n=6)
# -> [{"path": "...wav", "text": "The cat sat...", "duration_s": 1.58}, ...]
```

| Provider | Dependency | Voice | Realism | Best for |
|---|---|---|---|---|
| `espeak` | **espeak-ng binary** (system) | formant, robotic | low (but phonetically correct) | CI fast-path — no model download |
| `piper`  | `piper-tts` pip pkg (`[tts]`) + ONNX voice | neural, natural | high | fidelity end of the benchmark |

### espeak-ng (system binary)

The one provider that needs a *system binary*, not a pip package:

```bash
sudo apt-get install espeak-ng      # Debian/Ubuntu
brew install espeak-ng              # macOS
```

`is_available()` checks `PATH` (`espeak-ng`, falling back to `espeak`); when absent,
tests/benchmarks skip cleanly. `voice` is an espeak language code (`en`, `en-us`,
`es`, `de`). espeak emits ~22 kHz; the provider resamples to 16 kHz mono.

### piper (neural)

```bash
uv pip install -e 'backend[tts]'    # installs piper-tts
```

`voice` is a piper voice name; it is **downloaded on first use** into a cache dir
(`$TALKTEACH_DATA/piper_voices` by default, overridable via `download_dir=`). The
default `en_US-lessac-low` is 16 kHz native and small. `*-medium`/`*-high` voices are
22 kHz and are resampled. piper bundles its own espeak-ng phonemizer, so it needs no
system binary.

## Adding a provider

1. Subclass `TTSProvider` (`name`, `is_available`, `synthesize`) — funnel raw output
   through `tts.base.normalize_wav` for the canonical 16 kHz mono format.
2. Register it in `talkteach/tts/__init__.py` `_PROVIDERS`.
3. It's now usable everywhere `get_tts_provider(name)` is — including `benchmarks/*.yaml`.

gtts, Coqui TTS, and others fit this shape.

## Resampling

`tts.base.normalize_wav` converts width/channels/rate to 16-bit mono 16 kHz. It uses
the stdlib `audioop` (clean, dependency-free, present on Python 3.10–3.12) with a
NumPy linear-interpolation fallback for Python 3.13+ where `audioop` is removed.

See [BENCHMARKING.md](BENCHMARKING.md) for how the benchmark consumes these datasets.
