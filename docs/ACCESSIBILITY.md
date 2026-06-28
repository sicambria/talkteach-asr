# Accessibility (#37)

"So easily a 10-year-old can" has to include the 10-year-old who uses a screen
reader, can't use a mouse, or reads more easily with a dyslexia-friendly font.
Accessibility isn't a polish pass here — it's part of the child-proof promise.
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

## Pending

- **Full keyboard nav**: tab order verified end-to-end across all five screens,
  Enter/Space activation everywhere, no keyboard traps, focus moved sensibly on
  screen change.
- **Screen-reader pass**: test with NVDA/VoiceOver/Orca; ensure live regions
  announce dynamic changes (the live meter, the "getting smarter" progress, "Saved
  ✓") via `aria-live` rather than silent DOM updates.
- **High-contrast mode**: honour `prefers-contrast` and offer an explicit toggle;
  audit colour contrast to WCAG AA (the quiet/good/loud meter must not rely on
  colour alone — pair it with text/shape).
- **Dyslexia-friendly font option**: a toggle to switch the UI font (e.g. a
  legible/OpenDyslexic-style face) and adjustable text size; the `font-size`
  values already in the styles make this a CSS-variable change.
- **Reduced motion**: honour `prefers-reduced-motion` — the mascot's bob animation
  (`docs/MASCOT.md`) and transitions should calm down for users who need it.
- **i18n interplay**: labels read by AT must come from the catalog
  (`docs/I18N.md`), so accessibility and translation land together.

## How to verify

Manual AT testing on each OS, plus an automated audit (axe / Lighthouse) wired
into the UI build once the screens stabilise. `svelte-check` already flags
template-level a11y issues (D-011).

## Status

**Tier B** (#37). Core ARIA labelling, focus styling, and large targets are in the
components today; the keyboard-nav sweep, screen-reader live regions,
high-contrast + dyslexia-font toggles, and reduced-motion support are pending and
need real assistive-tech testing on each platform.
