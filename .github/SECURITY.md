# Security Policy

TalkTeach is a **easy-to-use, offline-first** desktop app that records and trains
on **children's voice recordings**. That makes security and data privacy the same
concern here, and we take both seriously. This document explains what's in scope,
how to report a problem privately, and what to expect back.

> **The privacy promise, in one line:** recordings, transcripts, projects, and
> trained models **never leave the device by default**, and there is **no
> telemetry without explicit opt-in** (see `docs/architecture/DECISIONS.md` D-008). A bug that
> breaks this promise is a security bug, not a feature request.

## Supported versions

TalkTeach is pre-1.0. We support **only the latest `0.x` release** with security
fixes; older `0.x` builds are not patched. Once we reach `1.0`, this table will
be updated to list supported lines.

| Version | Supported |
|---|---|
| latest `0.x` | ✅ |
| older `0.x` | ❌ (please upgrade) |

## Reporting a vulnerability

**Please do not open a public GitHub issue for a security or privacy problem.**

Report it privately by email to the maintainer:

**Gaspar Incze — <inczegaspar@gmail.com>**

(If GitHub private vulnerability reporting is enabled on the repository, the
"Report a vulnerability" button is also fine.)

Helpful things to include — only what you can share safely, and **never attach a
real child's recording**:

- What you were doing (which screen — Record / Check / Teach / Try — or which API
  endpoint).
- Your OS, whether the `[ml]` extra was installed, and whether you were offline.
- A minimal reproduction and the impact you believe it has.
- Whether any data left the device, or could have.

## What to expect

This is a small, maintainer-led project, so timelines are best-effort but
honest:

- **Acknowledgement:** within ~3 business days.
- **Initial assessment** (in scope? severity? reproducible?): within ~7 days.
- **Fix or mitigation plan:** communicated as soon as we've triaged; critical
  data-privacy issues are prioritized above feature work.
- **Disclosure:** coordinated with you. We'll credit you in `CHANGELOG.md` unless
  you'd rather stay anonymous, and we ask that you hold public details until a
  fix ships.

## Scope

The backend is a **local** FastAPI server. The threat model is mostly "untrusted
input on a trusted machine" plus "don't let local data escape." In scope:

- **Path traversal / arbitrary file write.** Uploads and project paths must stay
  inside the project directory. Crafted filenames (e.g. `../../…`) must not
  escape it. We sanitize uploads to a server-generated name with an extension
  allow-list (`docs/architecture/DECISIONS.md` D-004); regressions in that boundary are in scope.
- **The local backend binding.** The server binds to **`127.0.0.1:8756`** and
  must not be exposed on a routable interface. Anything that would bind it more
  broadly, or that lets a remote/cross-origin page reach it, is in scope.
- **The Tauri Content-Security-Policy.** The shipped CSP is locked to `'self'`
  plus the local backend origin (`http://127.0.0.1:8756` and `ws:` for live
  progress) — see `docs/architecture/DECISIONS.md` D-005. Any way to bypass or weaken it, or to
  load remote/active content into the webview, is in scope.
- **Data privacy of children's recordings.** Anything that causes recordings,
  transcripts, projects, or models to leave the device without explicit user
  action — silent network calls, telemetry that isn't opt-in, logs that leak raw
  audio or PII, an export that phones home — is **in scope and taken seriously.**
- **Upload validation.** Size limits and the codec/extension allow-list that
  guard the analyze/upload endpoints (roadmap #9; see `docs/architecture/DECISIONS.md` D-004).
- **Dependency vulnerabilities** that are actually reachable in the app
  (Python `[ml]`/runtime deps, npm UI deps, Rust crates).

Generally **out of scope** (still report if you're unsure):

- Issues that require an already-compromised machine or physical/root access to
  the user's device.
- Denial of service achieved purely by feeding the *local, single user's own*
  backend pathological input on their own machine (we still want robustness
  bugs, but they're triaged as reliability, not as remote vulnerabilities).
- Vulnerabilities only present when a user has deliberately opted into a future
  network feature (e.g. cloud fallback), reported against a build where that
  feature doesn't exist yet.

Thank you for helping keep TalkTeach safe for the kids who use it.
