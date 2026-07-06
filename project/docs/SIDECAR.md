# Tauri sidecar — the backend "just runs" (roadmap #15)

The desktop app must never make the user start a server. The Tauri shell
spawns the Python FastAPI backend as a **sidecar** subprocess on launch and
kills it on close.

## How it works

- `src-tauri/src/lib.rs` — on `setup()`, calls `app.shell().sidecar("talkteach-backend").spawn()`,
  stores the `CommandChild` in managed state, and drains its stdout/stderr. On
  `WindowEvent::Destroyed` and `RunEvent::Exit` it `kill()`s the subprocess so no
  orphaned server lingers. If the backend can't start, the window still opens and
  the UI shows a friendly "couldn't start" card (easy-to-use contract).
- `src-tauri/Cargo.toml` — adds `tauri-plugin-shell`.
- `src-tauri/tauri.conf.json` — `bundle.externalBin: ["binaries/talkteach-backend"]`
  tells the bundler to include the per-target binary.
- `scripts/build_sidecar.py` + `scripts/_sidecar_entry.py` — freeze the backend
  into `src-tauri/binaries/talkteach-backend-<target-triple>` with PyInstaller.

## Build it (provisioned machine)

```bash
uv pip install -e 'backend[ml,export]' pyinstaller
python scripts/build_sidecar.py              # → src-tauri/binaries/talkteach-backend-<triple>
npm run tauri build                          # bundles it into the installer
```

## Status

**Verified end-to-end** (2026-06-28, on a Linux/Wayland host with WebKit/GTK
present): `npm run tauri dev` compiles the shell, the window launches, `setup()`
spawns the Python backend as a sidecar, and the UI drives it over the live API
(`GET /api/health` → `200`). The CI `rust` job (`.github/workflows/ci.yml`) runs
`cargo fmt/clippy/check`; the release matrix (`RELEASING.md`) produces the per-OS
**frozen** PyInstaller sidecars + installers (still the release-pipeline step,
since the freeze must run on each target OS).

## Backend bind + CSP

The backend binds `127.0.0.1:8756` (configurable via `TALKTEACH_PORT`). The Tauri
CSP (`tauri.conf.json`, DECISIONS.md D-005) allows `connect-src` only to that
local origin (+ `ws:` for the live training-progress stream). A future remote
feature (cloud fallback #27) must widen the CSP explicitly.
</content>
