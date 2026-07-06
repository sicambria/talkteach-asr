# Plan: UI parity sweep — pre-flight screen, live meter, i18n plumbing, a11y quick-wins (#18, #13, #36, #37)

> **Scope honesty.** This is the *Optimal* tier of the four deferred front-end
> parity items — the CPU/sandbox-buildable half (Svelte 4 + WebAudio, no new
> runtime deps). It does **not** clear the whole a11y/i18n board: manual
> screen-reader certification, high-contrast + dyslexia-font toggles, RTL, and
> real second-language *translations* stay deferred (they need a screen reader +
> human, or translators). Those rows stay honestly "pending" in their docs.

## Summary

Close the four front-end gaps that make TalkTeach feel finished, following the
repo's UI conventions (plain-JS Svelte 4, `checkJs:false` per D-011; jargon-free
copy; grown-up-mode for technical detail):

1. **#18 Pre-flight SCREEN** — a Svelte screen that calls the *already-shipped*
   `GET /api/preflight` (`app.py:249`) and shows disk/memory/compute/mic status
   with a clear "you're ready" vs "fix this first" state, wired as an interstitial
   between New-Project and Record.
2. **#13 Live recording meter** — a client-side WebAudio RMS level bar on
   Screen1, tapping the existing `getUserMedia` stream (`Screen1_Record.svelte:89`).
   No backend call.
3. **#36 i18n plumbing** — key the hard-coded strings on the pre-flight screen +
   Screen0–4 through the existing `$t()` store (`ui/src/lib/i18n.js`), extend the
   `en` catalog, and add a minimal language switcher.
4. **#37 a11y quick-wins** — the CPU-verifiable half of `ACCESSIBILITY.md`
   "Pending": end-to-end tab order, Enter/Space activation, no keyboard traps,
   focus moved on screen change, and `aria-live` announcements for the meter +
   training progress. Verified by the repo's own a11y linters (svelte-check +
   eslint-plugin-svelte) plus an axe pass and a documented manual keyboard walk.

## Scope — what gets built

**A. Pre-flight screen (#18) — localized, one new file + wiring**
- New `ui/src/screens/ScreenPreflight.svelte`: on mount calls `preflight()`
  (`api.js:75`, returns `{results:[{name,status,detail,remedy}], ok, can_train,
  summary}`); shows a per-check list (✅/⚠️/⛔ from `status` = `ok|warn|fail`,
  each with `detail` + `remedy`), a headline "You're ready!" (when `ok`/`can_train`)
  vs "Let's fix this first", a **Re-check** button, and a **Continue** button.
  Continue is always allowed (checks are non-fatal by design — `run_preflight`
  docstring: "friendly, non-fatal report"; mic WARN must not block, per the drag-in
  fallback), but is styled secondary when not `ok`.
- Wire into `App.svelte`: add a `preflight` interstitial state shown *after*
  Screen0's `done` and *before* Screen1. Screen0 `on:done` → `preflight=true`
  (step stays 0, so the stepper stays hidden — it's a pre-wizard gate);
  ScreenPreflight `on:ready` → `preflight=false; next()` (→ step 1); `on:back` →
  `preflight=false` (→ Screen0). Guarded so the Arena path is unaffected.

**B. Live recording meter (#13) — localized to Screen1**
- In `startRecording()` (after `getUserMedia`): create one `AudioContext`, a
  `MediaStreamAudioSourceNode` from the stream, and an `AnalyserNode`
  (`fftSize:1024`); sample time-domain data on `requestAnimationFrame`, compute
  RMS → a reactive `level` (0..1, lightly smoothed). Render a level bar that fills
  with `level`. Teardown in `stopRecording`/`onstop`/`onDestroy`: cancel the RAF,
  disconnect nodes, `audioContext.close()`.
- **a11y of the meter (correctness):** the fast-updating bar is
  `aria-hidden="true"` (per-frame numeric updates in a live region are an AT
  anti-pattern). A *separate* `aria-live="polite"` status announces coarse state
  only — "Listening…" on start, "We can hear you" once level first crosses a
  threshold, "Stopped" on stop — so SR users get signal without spam.

**C. i18n plumbing (#36) — sweeps Screen0–4 + pre-flight**
- Extend `CATALOGS.en` in `i18n.js` with namespaced keys for every user-visible
  static string on Screen0–4 and the pre-flight screen (`preflight.*`, `record.*`,
  `check.*`, `teach.*`, `try.*`, `newproject.*`, `common.*`, `meter.*`, `app.*`).
  Reuse the four existing keys; do not rename them.
- Replace those hard-coded strings with `{$t('key')}` / `$t('key')` in the six
  screens. Backend-supplied text (prompts, clip transcripts, remedies, error
  detail) stays as-is — only the app's own chrome is keyed. `import { t } from
  '../lib/i18n.js'` per screen.
- **Language switcher:** a small `<select>` bound to `locale` in the topbar,
  populated from `availableLocales()`. To make the swap *observable* (success
  criterion: "toggling swaps strings via `t()`") without shipping a real
  translation, add one **synthetic QA pseudo-locale** generated
  **programmatically from `en`** — wrap every `en` value (e.g. `Hello` →
  `⟦Ħēĺĺō⟧`) at module load, so the *entire* UI visibly transforms on toggle
  (strong proof), it's unmistakably synthetic (no one reads it as a shipped
  translation), and it's zero-maintenance as `en` keys grow. Labelled
  "Pseudo (QA)" in the switcher. `en` remains the only real catalog; default
  stays `en`. Documented as plumbing proof in `I18N.md`.

**D. a11y quick-wins (#37) — cross-screen pass**
- **Enter/Space + no trap:** the Screen1 drop zone is `role="button" tabindex="0"`
  with no keyboard handler — add a hidden `<input type="file" accept="audio/*">`
  and make the zone activate it on click/Enter/Space (real keyboard path for
  "add existing audio"), or drop the button role if it stays drop-only. All other
  controls are native `<button>`/`<input>` (Enter/Space already native).
- **Focus on screen change:** add a tiny `focusOnMount` Svelte action that moves
  focus to the screen's `<h1>` (`tabindex="-1"`) when a screen mounts, so
  keyboard/SR users land at the top of each new screen (App-level screen swaps +
  the pre-flight interstitial).
- **aria-live:** wrap Screen3's training status/percent in `aria-live="polite"`;
  meter coarse status (B); "Saved ✓" confirmations announced politely.
- **Tab order:** verified logical by DOM order (already largely correct); confirmed
  in the manual walk. No positive `tabindex`.

## Verification (repo-native first, then axe, then manual)

- **Gate 1 — repo UI gate (committed, authoritative):** `make ui-check`
  (`Makefile:45` = `cd ui && npm run build && npm run check && npm run
  format:check`) **plus** `cd ui && npm run lint` (eslint-plugin-svelte, whose
  a11y rules are the repo's template-level a11y linter per `ACCESSIBILITY.md`
  "How to verify" + D-011). Must be clean; establish a green baseline *before*
  editing so any new violation is attributable.
- **Gate 2 — axe evidence (scratchpad, not committed repo infra):** run
  `@axe-core/playwright` against the running Vite dev server using the
  already-cached Playwright chromium (`~/.cache/ms-playwright/chromium-1228`).
  **Scope: the statically-reachable screens only — Screen0 (New project),
  Pre-flight, Screen1 (Record).** Screens past Record (Check/Teach/Try) are
  state-gated (need seeded clips / sufficiency / a trained run) and are not worth
  the harness cost — their template a11y is covered by Gate 1's linters + the
  manual walk. Assert no new serious/critical violations. Bonus evidence, **not**
  the deliverable: if the harness proves unavailable/flaky in-sandbox, fall back
  to Gate 1 + the manual walk and say so honestly in `ACCESSIBILITY.md`. Hold the
  line on time here.
- **Gate 3 — live app + manual keyboard walk (/run + /verify):** launch the
  **backend** (`cd backend && .venv/bin/python -m talkteach.app` → serves
  `http://127.0.0.1:8756`; venv already present) *and* Vite from `ui/` (per project
  memory), so the pre-flight screen renders **live** `/api/preflight` data (not
  just its error branch — this is what verifies #18). Then tab through every
  screen: reach every control in a logical order, Enter/Space activates, focus
  lands on the new `<h1>` on each screen change, no trap, the meter bar moves while
  recording, and the language switcher visibly swaps the keyed strings. Also spot
  the degraded state by killing the backend (pre-flight shows its error branch,
  never dead-ends). Record the result in `ACCESSIBILITY.md`.

## Steps (ordered — localized first, sweeps second)

1. **Baseline:** `make ui-check` + `cd ui && npm run lint` on a clean tree; record
   that it's green (attribution baseline). Read `styles.css` meter/`:focus` classes.
   Confirm the backend runs for live verification: `cd backend && .venv/bin/python
   -m talkteach.app` → `curl http://127.0.0.1:8756/api/preflight` returns a report
   (venv + entrypoint confirmed: `README.md:97`, `app.py:876`).
2. **#18:** write `ScreenPreflight.svelte`; wire the interstitial into
   `App.svelte`; `make ui-check`. (English strings first; keyed in step 4.)
3. **#13:** add the WebAudio meter + teardown + coarse aria-live to
   `Screen1_Record.svelte`; `make ui-check`.
4. **#36:** extend `en` catalog + add `qa` pseudo-locale in `i18n.js`; key
   Screen0–4 + pre-flight; add the `<select>` switcher in `App.svelte`;
   `make ui-check` + `npm run lint`.
5. **#37:** drop-zone keyboard path + hidden file input; `focusOnMount` action
   wired on all screens; `aria-live` on training progress + "Saved ✓"; `make
   ui-check` + `npm run lint`.
6. **Verify:** Gate 2 axe harness run; Gate 3 manual keyboard walk via /run +
   /verify; capture evidence.
7. **Docs + status:** flip `ROADMAP_STATUS.md` rows 13/18/36/37 with honest
   evidence (see below); update `ACCESSIBILITY.md` (move keyboard-nav + live-region
   rows to "present", keep SR/contrast/font/motion/RTL "pending"); update `I18N.md`
   — its "What's pending" section is now stale (it says "most screen strings are
   not yet keyed" + "add at least one non-English catalog"): rewrite to reflect the
   sweep + switcher + pseudo-locale, keeping *real translations + RTL* pending so
   the doc doesn't contradict the #36 ✅; `CHANGELOG.md`; commit direct to `main`
   (per user memory — no lingering diff).

### Status-flip honesty (the two judgement calls)

- **#13 → ✅**, **#18 → ✅** — real, tested, user-visible screens; unambiguous.
- **#36 → ✅ with in-cell scope note** — plumbing + switcher + `en` catalog +
  fallback proven across Screen0–4 + pre-flight. The cell states: real
  second-language *translations* (l10n) ride with the D-011 TS pass; only `en` + a
  QA pseudo-locale ship; and the **grown-up Arena (Screen5) stays hardcoded** (it's
  the technical surface, out of the child-facing i18n scope) so the ✅ isn't
  over-read. ("Internationalize the UI" = the infrastructure, which is done.)
- **#37 → ✅ with in-cell scope note**, *not a bare ✅*. The row is holistic
  ("Accessibility pass"); flipping it clean would overclaim. The cell reads:
  keyboard nav end-to-end + Enter/Space + no traps + focus-on-change + `aria-live`
  regions + axe-clean **delivered**; manual SR certification, high-contrast,
  dyslexia-font, reduced-motion, RTL **tracked pending in `ACCESSIBILITY.md`**.
  This honors the GOAL's "✅ for the keyboard+axe half, manual-SR kept pending"
  while keeping the matrix honest. (Surfaced to the advisor; if a bare ✅ or a
  stay-🟡 is preferred, that's the user's call.)

## Risks / reversibility

- **Blast radius:** one new screen file; additive edits to `App.svelte` (new
  interstitial state — Arena/wizard paths untouched), `Screen1_Record.svelte`
  (meter is additive; teardown guards against leaked `AudioContext`s),
  `i18n.js` (catalog additions only — existing keys unchanged), and string-only
  swaps on Screen0–4 (behaviour-preserving: `$t('k')` returns today's English).
  No API contract, no backend, no runtime dependency changes.
- **Biggest real risk = AudioContext leak / autoplay policy:** teardown on every
  stop path + `onDestroy`; `AudioContext` is created only inside the user-gesture
  `startRecording`, so no autoplay-policy block. Verified in Gate 3 (meter moves,
  no console errors, mic light off after stop).
- **Rollback:** one commit on `main`; `git revert`. New screen is unreferenced by
  the Arena path; the interstitial can be removed by reverting the `App.svelte`
  hunk alone.
- **i18n regression guard:** missing keys fall back to English (never blank); the
  pseudo-locale is opt-in via the switcher (default `en`), so the shipped
  experience is unchanged for every user who doesn't pick "Demo".

## Test plan

- **Automated (repo gate, every step):** `make ui-check` (vite build +
  svelte-check + prettier) + `cd ui && npm run lint` (eslint svelte a11y). Green
  baseline first; must stay green — svelte-check/eslint are the repo's a11y
  linters and will fail on `role` without keyboard handler, missing labels, etc.
- **Automated a11y (axe, scratchpad):** `@axe-core/playwright` over the six
  screens via cached chromium; assert zero new serious/critical violations.
  Honest fallback documented if unrunnable in-sandbox.
- **Manual/behavioural (/verify + /run):** keyboard-only walk of all screens
  (tab reach, Enter/Space, focus-on-change, no trap); meter moves while recording
  and tears down cleanly; language switcher swaps keyed strings live; pre-flight
  screen renders real `/api/preflight` data (backend up) and degrades to its error
  state (backend down) without dead-ending.
- **No new unit tests:** the UI has no JS unit-test runner (repo gate is
  build+svelte-check+eslint+prettier); adding a test framework is out of scope and
  would be inventing infra. Behaviour is covered by the a11y linters + axe + the
  manual walk, matching how the existing screens are verified.

## Standards & Guardrails Evidence

- Pre-flight API + shape to consume: `backend/talkteach/app.py:249` (`GET
  /api/preflight`), `api.js:75` (`preflight()` client), `reliability/preflight.py:233`
  (`run_preflight`, "friendly, non-fatal"), status enum `ok|warn|fail`
  (`preflight.py:29`).
- Screen routing to extend: `ui/src/App.svelte:16-19` (`step`/`arena` state),
  `:90-100` (screen switch); stepper hidden for step 0 (`:49`).
- Record stream to tap for the meter: `ui/src/screens/Screen1_Record.svelte:89`
  (`getUserMedia`), teardown site `:95-99` (`onstop`), `:77-80` (`onDestroy`).
- i18n scaffold: `ui/src/lib/i18n.js:29` (`t` derived store, English fallback),
  `:34` (`availableLocales`), `:26` (`locale` writable). Doc: `project/docs/I18N.md`.
- a11y baseline + what's owed: `project/docs/ACCESSIBILITY.md` "Already present"
  vs "Pending"; existing `:focus-visible` at `ui/src/styles.css:148`; the
  keyboard-gap to fix (`role="button"` drop zone, no handler)
  `Screen1_Record.svelte:218-227`.
- Repo UI verify contract: `Makefile:45` (`ui-check`), `Makefile:56` (`npm run
  lint` in prepush), CI `.github/workflows/ci.yml:55` (`ui` job = build +
  svelte-check). axe is **not** in the repo gate (confirmed) → run as scratchpad
  evidence, not committed infra.
- Cached chromium for the axe harness: `~/.cache/ms-playwright/chromium-1228`
  (present); npm registry reachable (`npm view @axe-core/cli` → 4.12.1).
- Status matrix rows to flip: `project/docs/ROADMAP_STATUS.md:32` (#13), `:37`
  (#18), `:55` (#36), `:56` (#37).
- Commit target = `main` directly (repo has no worktree contract; per user memory
  "always commit").
</invoke>
