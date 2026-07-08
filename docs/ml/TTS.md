# Synthetic speech (TTS) for testing & benchmarking

The product trains on **real recorded speech**. For automated end-to-end tests and
the engine benchmark we need audio with a *known* transcript and real phonetic
content, so word-error-rate means something. The old fixtures used sine **tones**
(`selftest.make_toy_dataset`): they exercise the plumbing, but a tone has no words,
so WER measured on them is noise. The `talkteach.tts` package fixes that by turning
karaoke prompts into intelligible speech whose ground truth is the prompt itself.

## Which TTS should I use?

| Provider | Install | Voice quality | Speed | Voice cloning | Best for |
|---|---|---|---|---|---|
| `espeak` | `apt-get install espeak-ng` | :star: Robotic / formant (phonetically correct) | Fastest (binary) | No | CI tests, quick sanity checks |
| `piper`  | `uv pip install -e 'backend[tts]'` | :star::star::star: Natural, neural | Fast (ONNX CPU) | No | Benchmark fidelity, everyday use |
| `pocket-tts` | `uv pip install -e 'backend[pocket-tts]'` | :star::star::star::star: Natural + voice cloning | ~6× real-time (CPU) | **Yes** — clone any voice from 20 s of audio | Synthetic training data, personalized voices, multi-speaker datasets |

**Quick guide:**
- **Only need a working TTS for tests?** → `espeak` (no pip install needed, just a system package)
- **Want natural-sounding speech for benchmarks?** → `piper` (good quality, small download)
- **Need to generate ASR training data or clone voices?** → `pocket-tts` (best quality, voice cloning, multi-lingual)

## Providers

All providers implement `talkteach.tts.base.TTSProvider` and emit **16 kHz mono PCM
WAV** (the format Whisper, the CTC engines, and `audio.quality` expect). Pick one by
name:

```python
from talkteach.tts import get_tts_provider
from talkteach.tts.dataset import synthesize_dataset

provider = get_tts_provider("piper")              # or "espeak" / "pocket-tts"
manifest = synthesize_dataset(provider, "out/", language="en", n=6)
# -> [{"path": "...wav", "text": "The cat sat...", "duration_s": 1.58}, ...]
```

### espeak-ng (system binary)

The robotic-but-reliable workhorse. Every phoneme is there — it just sounds like a
robot. Perfect for CI and fast feedback, terrible for natural-sounding demos.

```bash
sudo apt-get install espeak-ng      # Debian/Ubuntu
brew install espeak-ng              # macOS
```

`is_available()` checks `PATH` (`espeak-ng`, falling back to `espeak`); when absent,
tests/benchmarks skip cleanly. `voice` is an espeak language code (`en`, `en-us`,
`es`, `de`). espeak emits ~22 kHz; the provider resamples to 16 kHz mono.

### piper (neural)

Natural neural speech — sounds like a real person reading aloud. Uses an ONNX voice
model (~few MB) downloaded on first use. Good balance of quality and speed.

```bash
uv pip install -e 'backend[tts]'    # installs piper-tts
```

`voice` is a piper voice name; it is **downloaded on first use** into a cache dir
(`$TALKTEACH_DATA/piper_voices` by default, overridable via `download_dir=`). The
default `en_US-lessac-low` is 16 kHz native and small. `*-medium`/`*-high` voices are
22 kHz and are resampled. piper bundles its own espeak-ng phonemizer, so it needs no
system binary.

### pocket-tts (neural + voice cloning)

The most capable TTS in the toolbox. Based on Kyutai's 100M-parameter **Continuous
Audio Language Model**, it runs entirely on CPU (no GPU needed) and generates speech
~6× faster than real-time on a modern laptop.

**Voice cloning** is the killer feature. Instead of picking from a fixed set of voices,
you can give Pocket TTS any WAV file (as little as 20 seconds of speech) and it will
generate new audio that sounds like the same person.

```bash
uv pip install -e 'backend[pocket-tts]'    # installs pocket-tts + torch (CPU)
```

**Voices** can be:
- **Catalog names** — predefined voices like `"alba"`, `"estelle"`, `"juergen"`.
  English voices: `alba`, `anna`, `azelma`, `bill_boerst`, `caro_davy`, `charles`,
  `cosette`, `eponine`, `eve`, `fantine`, `george`, `jane`, `jean`, `javert`,
  `marius`, `mary`, `michael`, `paul`, `peter_yearsley`, `stuart_bell`, `vera`.
  Other languages: `giovanni` (it), `lola` (es), `rafael` (pt), `estelle` (fr),
  `juergen` (de).
- **WAV file paths** — any recorded speech for voice cloning.
- **Safetensors paths** — previously exported voice states for near-instant loading.

**Supported languages:** English, French, German, Portuguese, Italian, Spanish.
Select with the `language` parameter: `get_tts_provider("pocket-tts", language="french_24l")`.

**Quantization:** Pass `quantize=True` to enable int8 quantization. Reduces memory
~48 % and improves speed ~27 % with no measurable quality loss (WER unchanged).
Requires `torchao` (install with `pip install pocket-tts[quantize]`).

**Note:** The first call is slow because model weights (~100M) are downloaded from
Hugging Face and loaded. Subsequent calls reuse the cached model and voice states.

### Voice cloning example

```python
from talkteach.tts import get_tts_provider
from talkteach.tts.dataset import synthesize_dataset

# Clone a voice from a recording
provider = get_tts_provider("pocket-tts")
# Use a WAV file path as the voice
manifest = synthesize_dataset(
    provider, "output/", language="en", n=5,
    voices=["/path/to/my_recording.wav"]   # ← voice cloning!
)
# The generated WAVs will sound like the speaker in that recording
```

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
