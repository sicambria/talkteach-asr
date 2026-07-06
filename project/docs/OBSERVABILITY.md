# Observability (roadmap #41)

TalkTeach is offline and built for users, so observability is **local-first and
private by default** (DECISIONS.md D-008). There is no telemetry; nothing is sent
anywhere unless the user deliberately exports and shares it.

## Structured logging

`talkteach/obs/logging.py` configures the `talkteach` logger with a **rotating
JSON-lines** file handler (`~/.talkteach/default/logs/talkteach.jsonl`, 1 MB ×3)
plus a console handler. JSON lines are greppable and machine-readable without a
logging framework. `configure_logging()` runs once on server startup (in the
FastAPI lifespan) and is idempotent. Use `get_logger("area")` for a scoped logger.

## Help bundle ("Export a help bundle")

`GET /api/help-bundle` returns a zip containing:

- `report.json` — Python/platform versions, whether torch/faster-whisper/ffmpeg
  are present, and the `TALKTEACH_*` environment **with secret-looking vars
  redacted** (anything matching TOKEN/KEY/SECRET/PASSWORD/AUTH/HF_TOKEN).
- `logs/talkteach.jsonl*` — the rotating logs.

Nothing leaves the machine — the user downloads the zip and shares it
intentionally with support. `export_help_bundle()` writes the same bundle to a
file. A regression test (`tests/test_durability.py`) asserts secrets are redacted
and non-secret env is kept.

## Telemetry

Off, by design. If a future opt-in telemetry feature is added it MUST be
explicit, documented here, and widen the Tauri CSP (D-005) — never on by default.
</content>
