# Accessibility (#37)

"So easily a 10-year-old can" has to include the 10-year-old who uses a screen
reader, can't use a mouse, or reads more easily with a dyslexia-friendly font.
Accessibility isn't a polish pass here — it's part of the easy-to-use promise.
This is the working checklist: what's in place and what's still owed.

## Already present

- **ARIA labels** on icon-only and non-text controls (`aria-label` across the
  screens and the mascot), so a screen reader announces the big buttons.
- **State exposed to AT**: `aria-pressed` on the record/toggle controls,
  `aria-current` on the active wizard step, `role=` on custom widgets.
- **Keyboard reachability**: a `tabindex` where a non-button element must be
  focusable, and a visible `:focus` style in `styles.css`.
- **Large touch targets**: big primary buttons sized for small fingers (the whole
  UX is built around one giant button per screen).
- **Full keyboard nav** *(#37, delivered)*: tab order verified end-to-end across
  every screen, Enter/Space activation everywhere (the drag-and-drop zone now
  doubles as a real keyboard button opening a file picker), no keyboard traps, and
  focus moved to the new screen's `<h1 tabindex="-1">` on every screen change via
  the `focusOnMount` action (`ui/src/lib/a11y.js`). Confirmed in a headless
  Playwright run.
- **Live regions for dynamic changes** *(#37, delivered)*: `aria-live="polite"`
  on the live recording meter's coarse status ("Listening…" → "We can hear you!" —
  the fast-updating bar itself is `aria-hidden`, since per-frame numeric updates
  spam a screen reader), the "getting smarter" training progress, and the "Saved ✓"
  confirmations.

## Pending

- **Screen-reader certification**: test with NVDA/VoiceOver/Orca on each OS. The
  live regions above are wired, but an end-to-end SR pass on real assistive tech is
  still owed (needs a screen reader + a human — deferred).
- **High-contrast mode / WCAG-AA contrast**: honour `prefers-contrast` and offer an
  explicit toggle;
  audit colour contrast to WCAG AA (the quiet/good/loud meter must not rely on
  colour alone — pair it with text/shape).
- **Dyslexia-friendly font option**: a toggle to switch the UI font (e.g. a
  legible/OpenDyslexic-style face) and adjustable text size; the `font-size`
  values already in the styles make this a CSS-variable change.
- **Reduced motion**: honour `prefers-reduced-motion` — the mascot's bob animation
  (`MASCOT.md`) and transitions should calm down for users who need it.
- **i18n interplay**: labels read by AT must come from the catalog
  (`I18N.md`), so accessibility and translation land together.

## How to verify

- **Automated (repo gate):** `svelte-check` + `eslint-plugin-svelte` flag
  template-level a11y issues (missing labels, interactive elements without
  keyboard handlers, etc.) and run in `make ui-check` / `npm run lint` (D-011).
- **Automated (axe):** an `@axe-core/playwright` sweep of the statically-reachable
  screens (New project, Pre-flight, Record) found **no new** serious/critical
  violations vs the pre-change baseline. The one serious finding — `color-contrast`
  on the primary/secondary buttons — is pre-existing (identical on the unchanged
  Arena screen): it comes from the deliberately cheerful kid palette (white on
  orange/teal) and is tracked under *High-contrast mode / WCAG-AA contrast* above,
  not introduced by the #37 sweep.
- **Manual AT testing** on each OS (NVDA/VoiceOver/Orca) is still owed — see
  *Screen-reader certification* under Pending.

## Status

**Tier B → keyboard + axe half delivered** (#37). The end-to-end keyboard-nav
sweep, focus-on-screen-change, and `aria-live` regions are in the components and
verified (axe-clean for the changes, headless keyboard walk passing). Still
pending and needing real assistive-tech / design work: screen-reader
certification, the WCAG-AA colour-contrast fix + high-contrast toggle,
dyslexia-font option, reduced-motion, and RTL.
