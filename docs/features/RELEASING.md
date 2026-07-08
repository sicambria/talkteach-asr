# Releasing — signed installers for Win/macOS/Linux (#24)

The user should be able to download one installer and run it — no
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
(`scripts/build_sidecar.py`, see `SIDECAR.md`), install the OS toolchain
(Linux gets the WebKit/GTK dev libs), then `npm run tauri build` to bundle the
app + sidecar into an installer, and upload the artifact.

## Secrets needed for real signing

**Golden rule: signing material lives *only* in GitHub Actions encrypted secrets —
never in the repo.** Two guards enforce this: `.gitignore` blocks key/cert
extensions (`*.p12`, `*.pfx`, `*.pem`, `*.key`, …) and the `detect-private-key`
pre-commit hook refuses any commit containing a private key. Set every secret with
`gh secret set` reading from a file **outside** the repo (or piped via stdin);
GitHub stores it encrypted and never prints it in logs.

| Secret | Purpose | Status |
| --- | --- | --- |
| `TAURI_SIGNING_PRIVATE_KEY` + `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` | Sign the auto-update bundle | **✅ configured** |
| `APPLE_CERTIFICATE` (base64 .p12) + `APPLE_CERTIFICATE_PASSWORD`, `APPLE_ID`, `APPLE_PASSWORD` (app-specific), `APPLE_TEAM_ID` | macOS sign `.app`/`.dmg` + `notarytool` staple | ⬜ needs your Apple Developer cert |
| `WINDOWS_CERTIFICATE` (base64 PFX) + `WINDOWS_CERTIFICATE_PASSWORD` | Authenticode on `.msi`/`.exe` | ⬜ needs your code-signing cert |

### Tauri updater key (done)

Generated with `npm run tauri signer generate` (private key never written into the
repo); the private key + password are in the secrets above. The **public** key is
safe to publish and goes into `tauri.conf.json` → `plugins.updater.pubkey` when the
auto-update feed is wired:

```
dW50cnVzdGVkIGNvbW1lbnQ6IG1pbmlzaWduIHB1YmxpYyBrZXk6IDVBMTExRkUyRDY2OEE0REUKUldUZXBHalc0aDhSV2srOTgxRFo5alJxZzk4RXBYVU5wc3p0M0pmTkg0QUdCQ21NZ3gxL1ZUcVMK
```

### Setting the macOS / Windows secrets safely

Run these on your machine with the cert files kept **outside** any git repo:

```bash
# macOS: export your Developer ID cert as a .p12, then base64 it from /tmp (not the repo)
base64 -i ~/secure/developerID.p12 | gh secret set APPLE_CERTIFICATE -R sicambria/talkteach-asr
gh secret set APPLE_CERTIFICATE_PASSWORD -R sicambria/talkteach-asr   # prompts / reads stdin
gh secret set APPLE_ID -R sicambria/talkteach-asr
gh secret set APPLE_PASSWORD -R sicambria/talkteach-asr               # app-specific password
gh secret set APPLE_TEAM_ID -R sicambria/talkteach-asr

# Windows: base64 your code-signing PFX (kept outside the repo)
base64 -i ~/secure/codesign.pfx | gh secret set WINDOWS_CERTIFICATE -R sicambria/talkteach-asr
gh secret set WINDOWS_CERTIFICATE_PASSWORD -R sicambria/talkteach-asr
```

`release.yml` already references all of these via `${{ secrets.* }}`; unset ones
are empty, so the build stays green (just unsigned) until you add the cert.

## How sidecar + bundled runtime fit

The installer must be self-contained (Report B.7): no "install Python first". The
sidecar build freezes the FastAPI backend + pinned wheels into a per-target binary
(`SIDECAR.md`); the no-install runtime story (ffmpeg, CPU/CUDA libs via `uv`)
is `BUNDLING.md`. The release job runs the sidecar build *before*
`tauri build` so the binary is present for `bundle.externalBin`.

## Versioning & changelog

- **Semver** on the tag (`vMAJOR.MINOR.PATCH`); keep `package.json`,
  `src-tauri/tauri.conf.json`, and `backend/pyproject.toml` versions in lockstep.
- **CHANGELOG.md** is updated in the release PR (Keep-a-Changelog style); the tag
  message references the section. The release job can attach those notes to the
  GitHub Release.
- Pre-1.0: minor bumps may carry breaking changes; call them out explicitly.

## Status

**Tier C** (#24). The matrix workflow builds per-OS artifacts on tag. The Tauri
updater signing secret is **configured**; macOS/Windows code-signing await the
maintainer's certs (recipes above). Until then the build produces working but
**unsigned** installers. The companion CI (`.github/workflows/ci.yml`, #38)
already gates every PR.
