# Plan: reposition "child / grown-up" → "easy / advanced" across the repo

> **Scope honesty.** The user asked to change *all* "child", "grown-up", and
> similar references repo-wide, renaming the two product tiers to **easy**
> (wizard with great defaults, few meaningful options) and **advanced** (full
> detailed config in the UI). This is a **product repositioning** — from a
> "kids' app" persona to a general-audience tool with an Easy default flow and an
> Advanced surface — not a blind find-replace. One code identifier changes;
> everything else is prose, copy, and user-facing message strings.

## Summary

Two distinct usage classes were found (grep, ~250 occurrences, ~78 files):

1. **Mode/tier labels** → rename to Easy / Advanced.
   - Code identifier: `grownUpMode` (store.js export + 6 screen imports + App.svelte).
   - CSS class `.grownup` → `.advanced`.
   - Prose: "Grown-up mode", "grown-up Arena", "Kids never see it / the kid view".
2. **Domain persona prose** ("the child records", "so a child sees…", "ask a
   grown-up to install") → reposition to **second person ("you")** for the
   easy-mode user and plain phrasing; drop the child/adult dichotomy.

**Critical blast-radius finding:** the *only* code identifier is `grownUpMode`.
No DB columns (`schema.sql` only mentions "child" in a comment), no function/class
names, no API request/response fields, no i18n **keys** (`app.advanced` already
exists and already renders "Advanced"). So the rename is safe: one JS identifier +
one CSS class + tone-aware text edits.

## Mapping (canonical — applied consistently everywhere)

| Found | Becomes | Notes |
|---|---|---|
| `grownUpMode` (identifier) | `advancedMode` | store.js `export const` + 6 imports + `$grownUpMode` refs + `.update` |
| CSS class `.grownup` | `.advanced` | App.svelte + 5 screens |
| "Grown-up mode" / "Grown-up" (label) | "Advanced mode" / "Advanced" | toggle already labeled "Advanced" |
| "grown-up **Arena**" | "Advanced **Arena**" | README table |
| "Kids never see it" / "the kid view" | "Easy mode hides it" / "the easy view" | mode contrast |
| "so a/the child …" / "the kid …" (the user) | "so you …" / "you …" | second person |
| "a non-English-speaking child can use it" | "anyone can use it, in any language" | audience |
| "ask a grown-up to install X" (message) | "install X with `<hint>`" | drop persona; keep the install hint already in the string |
| "Stopped by the grown-up." (message) | "Stopped. Progress was saved." | actor is just the user |
| "a kids' app handling voice" | "a local app handling voice" | |
| "child speech" / "kid dataset" (technical) | "speech" / "small dataset" | domain-neutral |

**Guardrail A — audience of the *text* picks the person (advisor #2):**
user-visible copy (svelte strings, `EngineUnavailableError` messages) → **"you"**
("you record one long take", grammatical, never "you records"); developer-facing
**comments/docstrings** → **"the user" / "easy mode"** ("so the user never sees a
hyperparameter", not "so you never see"). ~25 backend files are the latter.

**Guardrail B — `nth-child` is a substring false-positive (advisor #1):** the CSS
selector `th:nth-child(3)` (`ui/src/components/Scoreboard.svelte:65`, the **only**
hit) must NOT be touched. No `replace_all` on the bare token "child" in any file
with CSS. The step-6 straggler grep excludes it explicitly:
`rg -i -e 'grown-?up' -e '\bkid' -e 'child' -g'!*lock*' | rg -v 'nth-child'`.

**Guardrail C — never rename the spec:** this file
(`plans/terminology-easy-advanced.md`) keeps "child/grown-up" in its "Found"
column — it is the mapping, not a product surface.

## File groups (execution order)

- **G1 — Structural (do first, verify build):** `ui/src/lib/store.js` (rename export
  + its comment), `ui/src/App.svelte`, `Screen0–4`, `ScreenPreflight` imports/refs,
  CSS `.grownup`→`.advanced` (App.svelte + `styles.css` if defined there). Then
  `make ui-check` to prove the identifier rename compiles before touching copy.
- **G2 — UI copy + i18n:** svelte visible text, `i18n.js` values + comment, screen
  comments. `make ui-check`.
- **G3 — Backend message strings (user-facing):** the `EngineUnavailableError`
  messages + "Stopped by the grown-up" in `engines/base.py`, `whisper_lora.py`,
  `_train_common.py`, `_wav2vec2_train.py`, `_whisper_train.py`, `audio/decode.py`.
  These are shown to users → reposition carefully.
- **G4 — Backend comments/docstrings:** the remaining ~25 backend files (comments
  only; no behavior change).
- **G5 — Living docs:** `README.md`, `ui/README.md`, `project/docs/*` (ROADMAP,
  ROADMAP_STATUS, DECISIONS, all design docs), `CHANGELOG.md` (add an entry).
- **G6 — Historical artifacts (advisor #3: lean inclusive — "entire repo"):**
  completed plans (`plans/ui-parity-sweep.md`, 3 hits) and design docs describe the
  *current* product → **include them**. The dated external snapshots
  (`reports/*_2026-06-27.md` 7 hits, `docs/product/PRODUCT_ASSESSMENT_2026-07-06.md`
  2 hits) → **update terminology only, never scores/substance** (they're records of
  a point-in-time finding). Note the inclusive choice in the commit. **Do NOT touch
  `plans/terminology-easy-advanced.md`** (the spec, per Guardrail C).

## Steps

1. G1 structural rename; `make ui-check` green (proves `advancedMode` compiles).
2. G2 UI copy; `make ui-check`.
3. G3 backend message strings; `make -C backend check` (or `make check`).
4. G4 backend comments; G5 living docs.
5. `make check` (backend lint+test) + `make ui-check` both green.
6. Straggler sweep: `rg -i 'grown-?up|\bgrownUp'` returns **0** in living surfaces;
   `rg -i '\bchild|\bkid'` remaining hits are only in G6 historical (or intentional
   domain-neutral survivors), each accounted for.
7. Commit direct to `main` (per memory). Then return to the UI-surfacing decisions
   with recommendations (the second half of the session).

## Risks / reversibility

- **Blast radius:** one JS identifier (`grownUpMode`), one CSS class, ~250 text
  edits. No API, DB, function-name, or i18n-key changes → no contract break. UI and
  backend behavior are byte-identical except for the strings users read.
- **Biggest risk = ungrammatical "you" substitutions** in prose → mitigated by
  in-context edits, not sed, and by `make ui-check`/`make check` (won't catch
  grammar, but catches broken code) + a manual re-read of each changed message.
- **Second risk = over-reach into historical records** (G6) → default to leaving
  dated artifacts intact; surface the call rather than silently rewriting history.
- **Rollback:** one commit on `main`; `git revert`. No data migration.

## Test plan

- `make ui-check` after G1 and G2 (vite build + svelte-check + prettier + eslint) —
  proves the `advancedMode`/`.advanced` rename compiles and lints clean.
- `make check` (backend: ruff + mypy + pytest) after G3/G4 — proves message-string
  edits didn't break any test that asserts on message text
  (`test_director.py:101`, `test_api.py:232` assert on "grown-up mode"/"grown-up" —
  **these tests must be updated in lockstep** or they fail; that's the shift-left
  signal the rename is complete).
- Final straggler grep (step 6) is the completeness gate.

## Standards & Guardrails Evidence

- Only code identifier: `ui/src/lib/store.js:18` (`export const grownUpMode`).
- No DB/schema impact: `backend/talkteach/data/schema.sql:3` (term is in a comment).
- i18n keys already Easy/Advanced-agnostic: `ui/src/lib/i18n.js:15` (`app.advanced`).
- Tests that assert on the term (must update in lockstep): `backend/tests/test_director.py:101`,
  `backend/tests/test_api.py:232`.
- User-facing message strings to reposition: `backend/talkteach/engines/base.py:40`,
  `whisper_lora.py:216,373`, `_train_common.py:198`, `_wav2vec2_train.py:276`,
  `_whisper_train.py:365`, `audio/decode.py:67`.
- Verify contract: `Makefile` `check: lint test`; UI `make ui-check`.
- Commit target = `main` directly (repo has no worktree contract; per user memory).
