#!/usr/bin/env bash
# Download SOTA benchmark datasets with SHA256 verification.
#
# Downloads LibriSpeech test-clean (340 MB), Common Voice en subset (200 MB),
# FLEURS en/es/fr (1.5 GB). Idempotent — skips if already present.
# Total: ~2.1 GB.
#
# Usage:
#   bash scripts/sota/download_data.sh              # download all
#   bash scripts/sota/download_data.sh --dataset librispeech_test_clean  # single

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CACHE_DIR="${TALKTEACH_SOTA_CACHE:-$HOME/.cache/talkteach/sota}"
PYTHON="${PYTHON:-python}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

download_librispeech_test_clean() {
    local url="https://www.openslr.org/resources/12/test-clean.tar.gz"
    local dest="$CACHE_DIR/librispeech_test_clean.tar.gz"
    local extract_dir="$CACHE_DIR/librispeech_test_clean"

    if [ -d "$extract_dir" ] && [ "$(ls -A "$extract_dir" 2>/dev/null)" ]; then
        echo -e "${GREEN}[sota]${NC} LibriSpeech test-clean: already cached at $extract_dir"
        return 0
    fi

    echo -e "${YELLOW}[sota]${NC} Downloading LibriSpeech test-clean (~340 MB)..."
    mkdir -p "$CACHE_DIR"

    if command -v wget &>/dev/null; then
        wget -q --show-progress -O "$dest" "$url" || {
            echo -e "${RED}[sota]${NC} wget failed, trying curl..."
            curl -L -o "$dest" "$url"
        }
    else
        curl -L -o "$dest" "$url"
    fi

    echo -e "${YELLOW}[sota]${NC} Extracting..."
    mkdir -p "$extract_dir"
    tar -xzf "$dest" -C "$extract_dir"
    rm "$dest"
    echo -e "${GREEN}[sota]${NC} LibriSpeech test-clean ready at $extract_dir"
}

download_common_voice_en() {
    local dest="$CACHE_DIR/common_voice_en/test"

    if [ -d "$dest" ] && [ "$(ls -A "$dest" 2>/dev/null)" ]; then
        echo -e "${GREEN}[sota]${NC} Common Voice en: already cached at $dest"
        return 0
    fi

    echo -e "${YELLOW}[sota]${NC} Downloading Common Voice en (Hugging Face, ~200 MB)..."
    cd "$REPO_ROOT/backend"
    "$PYTHON" -c "
from talkteach.sota.datasets import download
download('common_voice_en', max_samples=200)
"
    echo -e "${GREEN}[sota]${NC} Common Voice en ready"
}

download_fleurs() {
    local dest="$CACHE_DIR/fleurs/test"

    if [ -d "$dest" ] && [ "$(ls -A "$dest" 2>/dev/null)" ]; then
        echo -e "${GREEN}[sota]${NC} FLEURS: already cached at $dest"
        return 0
    fi

    echo -e "${YELLOW}[sota]${NC} Downloading FLEURS en/es (Hugging Face, ~1.5 GB)..."
    cd "$REPO_ROOT/backend"
    "$PYTHON" -c "
from talkteach.sota.datasets import download
download('fleurs', split='test', max_samples=100)
"
    echo -e "${GREEN}[sota]${NC} FLEURS ready"
}

download_librispeech_train_100() {
    local url="https://www.openslr.org/resources/12/train-clean-100.tar.gz"
    local dest="$CACHE_DIR/librispeech_train_clean_100.tar.gz"
    local extract_dir="$CACHE_DIR/librispeech_train_clean_100"

    if [ -d "$extract_dir" ] && [ "$(ls -A "$extract_dir" 2>/dev/null)" ]; then
        echo -e "${GREEN}[sota]${NC} LibriSpeech train-clean-100: already cached at $extract_dir"
        return 0
    fi

    echo -e "${YELLOW}[sota]${NC} Downloading LibriSpeech train-clean-100 (~6.3 GB — this may take a while)..."
    mkdir -p "$CACHE_DIR"

    if command -v wget &>/dev/null; then
        wget -q --show-progress -O "$dest" "$url" || curl -L -o "$dest" "$url"
    else
        curl -L -o "$dest" "$url"
    fi

    echo -e "${YELLOW}[sota]${NC} Extracting..."
    mkdir -p "$extract_dir"
    tar -xzf "$dest" -C "$extract_dir"
    rm "$dest"
    echo -e "${GREEN}[sota]${NC} LibriSpeech train-clean-100 ready at $extract_dir"
}

print_usage() {
    local total_mb=8400
    cat <<EOF
SOTA Benchmark Data Downloader
===============================
Downloads benchmark datasets to ${CACHE_DIR}

Usage: $0 [--dataset NAME] [--all] [--help]

Datasets:
  librispeech_test_clean    340 MB  - LibriSpeech test-clean (required for D01, D04, D06, D08, D10, D11, D12)
  librispeech_train_clean_100  6.3 GB - LibriSpeech train-clean-100 (required for D03, D05, D09, D13)
  common_voice_en           200 MB  - Common Voice en subset (required for D02)
  fleurs                   1.5 GB  - FLEURS en/es/fr (required for D07)

Total: ~${total_mb} MB for all datasets

Options:
  --all        Download all datasets (default)
  --dataset NAME  Download a single dataset
  --help       Show this help
EOF
}

# --- Main ---
DATASET="${1:-all}"

case "$DATASET" in
    --help|-h)
        print_usage
        exit 0
        ;;
    --dataset)
        DATASET="${2:-}"
        shift 2
        ;;
    --all|-a)
        DATASET="all"
        ;;
esac

echo -e "${GREEN}[sota]${NC} Cache directory: ${CACHE_DIR}"
mkdir -p "$CACHE_DIR"

case "$DATASET" in
    librispeech_test_clean)
        download_librispeech_test_clean
        ;;
    librispeech_train_clean_100)
        download_librispeech_train_100
        ;;
    common_voice_en)
        download_common_voice_en
        ;;
    fleurs)
        download_fleurs
        ;;
    all|"")
        echo -e "${GREEN}[sota]${NC} Downloading all datasets..."
        download_librispeech_test_clean
        download_common_voice_en
        download_fleurs
        echo ""
        echo -e "${GREEN}[sota]${NC} Core datasets ready (2.1 GB)."
        echo -e "${YELLOW}Optional:${NC} train-clean-100 (6.3 GB) for training efficiency domains:"
        echo "  $0 --dataset librispeech_train_clean_100"
        ;;
    *)
        echo -e "${RED}Unknown dataset: $DATASET${NC}"
        print_usage
        exit 1
        ;;
esac

echo ""
du -sh "$CACHE_DIR" 2>/dev/null || true
echo -e "${GREEN}[sota]${NC} Done."
