# Dependency hygiene (roadmap #42)

How we keep the dependency surface current, and the standing assessment of known
advisories.

## Automation

- **Dependabot** (`.github/dependabot.yml`) opens weekly PRs for pip (`/backend`),
  npm (`/ui` + root), cargo (`/src-tauri`), and GitHub Actions.
- **CI** (`.github/workflows/ci.yml`) runs the lint/type/test gates on every PR so
  a bump that breaks something is caught immediately.
- **pinned + lockfiles**: `ui/package-lock.json`, `src-tauri/Cargo.lock` (on
  build), and pinned wheels in the bundled runtime (`docs/BUNDLING.md`).

## `npm audit` assessment (as of 2026-06-28)

- **Root** (`@tauri-apps/cli`): **0 vulnerabilities**.
- **UI** (`/ui`): 7 advisories, all in **Svelte 4** and all **SSR-only** XSS
  classes (`bind:innerText`/`bind:textContent` during SSR, DOM-clobbering of
  framework state, spread-attribute SSR). **Not exploitable here**: TalkTeach is
  a **client-only** Tauri/Vite SPA — there is no server-side rendering, and the
  Tauri CSP (D-005) blocks remote content. The `npm audit fix --force` remedy is
  a **breaking** upgrade to Svelte 5 (runes — a real migration).

  **Decision**: documented as not-applicable for the current SSR-free SPA; the
  Svelte 5 migration is tracked as a follow-up (it pairs naturally with the
  svelte-check TypeScript migration noted in DECISIONS.md D-011), not an
  emergency. Re-evaluate if the UI ever gains SSR.

## Starlette TestClient / httpx warning

The fast suite emitted `StarletteDeprecationWarning: Using httpx with
starlette.testclient is deprecated`. It's a test-only transport detail we don't
control. Silenced via `filterwarnings` in `backend/pyproject.toml` so a *real*
warning stands out; revisit when Starlette/FastAPI settle the httpx transport.

## Python pins

The base backend stays light (fastapi/uvicorn/pydantic/numpy/python-multipart);
heavy ML lives in optional extras (`[ml]`, `[export]`, `[vad]`, `[denoise]`) so a
plain install has a tiny, easily-audited surface.
</content>
