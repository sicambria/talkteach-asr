#!/usr/bin/env bash
#
# TalkTeach setup — installs every dependency layer.
#
#   System libs (sudo)  →  Rust  →  Node (Tauri CLI + Svelte UI)  →  Python backend
#
# Usage:
#   ./setup.sh                 # full install (system + rust + node + python light)
#   ./setup.sh --with-ml       # also install the heavy ML stack (torch, transformers, …)
#   ./setup.sh --with-sota     # install ML stack + download SOTA benchmark datasets (~2.1 GB)
#   ./setup.sh --backend-only  # only the Python backend (no system/rust/node)
#   ./setup.sh --skip-system   # skip the sudo apt/dnf/pacman/brew step
#   ./setup.sh --skip-rust     # skip rustup + the root Tauri CLI (desktop build)
#   ./setup.sh --help
#
# Idempotent: safe to re-run. Light backend + UI need NO sudo, NO GPU, NO ML deps.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

# --- options -----------------------------------------------------------------
WITH_ML=0
WITH_SOTA=0
SKIP_SYSTEM=0
SKIP_RUST=0
BACKEND_ONLY=0

for arg in "$@"; do
  case "$arg" in
    --with-ml)      WITH_ML=1 ;;
    --with-sota)    WITH_ML=1; WITH_SOTA=1 ;;
    --skip-system)  SKIP_SYSTEM=1 ;;
    --skip-rust)    SKIP_RUST=1 ;;
    --backend-only) BACKEND_ONLY=1; SKIP_SYSTEM=1; SKIP_RUST=1 ;;
    --help|-h)
      awk 'NR==1{next} /^#/{sub(/^# ?/,""); print; next} {exit}' "${BASH_SOURCE[0]}"
      exit 0 ;;
    *) echo "Unknown option: $arg (try --help)" >&2; exit 2 ;;
  esac
done

log()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }
VENV_PY="$REPO_ROOT/backend/.venv/bin/python"

# --- 1. system packages (sudo) ----------------------------------------------
install_system() {
  log "Installing system dependencies (Tauri WebKit/GTK + ffmpeg + espeak-ng TTS)"
  # espeak-ng is the system TTS binary the benchmark's espeak provider shells out to
  # (project/docs/TTS.md). Tiny; installed here so the benchmark fast-path works.
  if have apt-get; then
    sudo apt-get update
    sudo apt-get install -y \
      build-essential curl wget file pkg-config \
      libwebkit2gtk-4.1-dev libgtk-3-dev libayatana-appindicator3-dev \
      librsvg2-dev libssl-dev libxdo-dev libsoup-3.0-dev ffmpeg espeak-ng
  elif have dnf; then
    sudo dnf install -y webkit2gtk4.1-devel gtk3-devel libappindicator-gtk3-devel \
      librsvg2-devel openssl-devel libxdo-devel libsoup3-devel \
      @development-tools curl wget file ffmpeg espeak-ng
  elif have pacman; then
    sudo pacman -S --needed --noconfirm webkit2gtk-4.1 gtk3 libappindicator-gtk3 \
      librsvg openssl base-devel curl wget file ffmpeg espeak-ng
  elif have brew; then
    xcode-select --install 2>/dev/null || true
    brew install ffmpeg espeak-ng
  else
    warn "No known package manager (apt/dnf/pacman/brew). Install the Tauri prereqs manually:"
    warn "  https://tauri.app/start/prerequisites/  — then re-run with --skip-system"
    return 1
  fi
}

# --- 2. rust -----------------------------------------------------------------
install_rust() {
  if have rustc && have cargo; then
    log "Rust already installed ($(rustc --version))"
    return 0
  fi
  log "Installing Rust toolchain (rustup)"
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
  # shellcheck disable=SC1091
  source "$HOME/.cargo/env"
}

# --- 3. node (root Tauri CLI + Svelte UI) ------------------------------------
install_node() {
  if ! have npm; then
    warn "npm not found — install Node.js ≥ 18 (https://nodejs.org). Skipping node deps."
    return 1
  fi
  if [ "$SKIP_RUST" -eq 0 ]; then
    log "Installing root Node deps (Tauri CLI)"
    npm install
  else
    log "Skipping root Tauri CLI (--skip-rust); installing UI deps only"
  fi
  log "Installing Svelte UI deps"
  ( cd ui && npm install )
  # This environment's npm blocks install scripts; esbuild needs its postinstall.
  # Standard npm runs scripts automatically, so this is best-effort.
  ( cd ui && npm approve-scripts esbuild >/dev/null 2>&1 ) || true
}

# --- 4. python backend -------------------------------------------------------
install_python() {
  log "Setting up Python backend (uv)"
  if ! have uv; then
    warn "uv not found — install it: https://github.com/astral-sh/uv  (or use pip+venv manually)"
    return 1
  fi
  cd "$REPO_ROOT/backend"
  [ -d .venv ] || uv venv .venv
  if [ "$WITH_ML" -eq 1 ]; then
    log "Installing backend with ML + export + tts + dev extras (large download)"
    # tts = piper neural voice for the benchmark; export now also pulls optimum
    # (ONNX export for wav2vec2/Whisper). espeak-ng comes from the system step.
    uv pip install --python .venv -e '.[ml,export,tts,dev]'
  else
    log "Installing backend (light: dev extras only — no GPU/ML framework)"
    uv pip install --python .venv -e '.[dev]'
  fi
  cd "$REPO_ROOT"
}

# --- run ---------------------------------------------------------------------
[ "$SKIP_SYSTEM" -eq 0 ] && { install_system || warn "system deps step failed/partial"; }
[ "$SKIP_RUST"   -eq 0 ] && { install_rust   || warn "rust step failed"; }
if [ "$BACKEND_ONLY" -eq 0 ]; then
  install_node || warn "node deps step failed/partial"
fi
install_python || warn "python step failed"

# --- SOTA datasets (optional, needs --with-sota) ------------------------------
if [ "$WITH_SOTA" -eq 1 ]; then
  log "Downloading SOTA benchmark datasets (~2.1 GB)"
  if [ -x "$VENV_PY" ]; then
    bash scripts/sota/download_data.sh || warn "SOTA data download failed/partial"
  else
    warn "Python venv not found — skip SOTA data download"
  fi
fi

# --- verify ------------------------------------------------------------------
log "Verifying"
if [ -x "$VENV_PY" ]; then
  ( cd "$REPO_ROOT/backend" && "$VENV_PY" -m pytest -q ) && echo "  backend tests: OK"
fi
if [ "$BACKEND_ONLY" -eq 0 ] && have npm; then
  ( cd ui && npm run build >/dev/null 2>&1 ) && echo "  UI build: OK (ui/dist)"
fi

log "Done."
cat <<'EOF'

Next:
  Backend server : cd backend && source .venv/bin/activate && python -m talkteach.app
  UI (web)       : cd ui && npm run dev
  Desktop app    : npm run tauri dev          (needs system deps + Rust)
  Real training  : re-run with --with-ml
  Benchmark      : python scripts/benchmark.py --config benchmarks/quick.yaml  (needs --with-ml)
  SOTA benchmark : bash scripts/sota/run_all.sh --baseline  (needs --with-sota)
EOF
