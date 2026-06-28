# Releasing — signed installers for Win/macOS/Linux (#24)

A 10-year-old's grown-up should be able to download one installer and run it — no
"unidentified developer" scares, no SmartScreen blocks. That means **signed,
notarized installers** for all three desktop OSes, built reproducibly from a
version tag. This note describes the pipeline; the workflow lives at
`.github/workflows/release.yml`.

## Trigger & matrix

`release.yml` runs on a `v*` tag push (or manual dispatch) across a three-OS
matrix:

| Runner | Target triple |
|---|---|
| `ubuntu-latest` | `x86_64-unknown-linux-gnu` |
| `macos-latest` | `aarch64-apple-darwin` |
| `windows-latest` | `x86_64-pc-windows-msvc` |

Each job: build the **backend sidecar** with PyInstaller per target
(`scripts/build_sidecar.py`, see `docs/SIDECAR.md`), install the OS toolchain
(Linux gets the WebKit/GTK dev libs), then `npm run tauri build` to bundle the
app + sidecar into an installer, and upload the artifact.

## Secrets needed for real signing

The matrix builds today produce **unsigned** artifacts. Signing is wired by
adding these repo secrets (referenced as comments in the workflow):

- **macOS notarization** — `APPLE_CERTIFICATE` (base64 .p12) +
  `APPLE_CERTIFICATE_PASSWORD`, `APPLE_ID`, `APPLE_PASSWORD` (app-specific) /
  `APPLE_TEAM_ID`. Tauri signs the `.app`/`.dmg`, then `notarytool` staples.
- **Windows code-signing** — `WINDOWS_CERTIFICATE` (base64 PFX) +
  `WINDOWS_CERTIFICATE_PASSWORD` for Authenticode on the `.msi`/`.exe`.
- **Tauri updater** — `TAURI_SIGNING_PRIVATE_KEY` (already referenced) signs the
  update bundle if/when auto-update is enabled.

These cannot live in the sandbox; a maintainer adds them once, in repo settings.

## How sidecar + bundled runtime fit

The installer must be self-contained (Report B.7): no "install Python first". The
sidecar build freezes the FastAPI backend + pinned wheels into a per-target binary
(`docs/SIDECAR.md`); the no-install runtime story (ffmpeg, CPU/CUDA libs via `uv`)
is `docs/BUNDLING.md`. The release job runs the sidecar build *before*
`tauri build` so the binary is present for `bundle.externalBin`.

## Versioning & changelog

- **Semver** on the tag (`vMAJOR.MINOR.PATCH`); keep `package.json`,
  `src-tauri/tauri.conf.json`, and `backend/pyproject.toml` versions in lockstep.
- **CHANGELOG.md** is updated in the release PR (Keep-a-Changelog style); the tag
  message references the section. The release job can attach those notes to the
  GitHub Release.
- Pre-1.0: minor bumps may carry breaking changes; call them out explicitly.

## Status

**Tier C** (#24). The matrix workflow is a real scaffold that builds (unsigned)
artifacts on tag; signing/notarization is pending the secrets above and three
build hosts, which can't be exercised in this environment. The companion CI
(`.github/workflows/ci.yml`, #38) already gates every PR.
