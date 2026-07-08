# Mascot, sound & gamification (#31)

An easy-mode app needs a *character* — a friendly face that reacts, celebrates,
and softens mistakes — far more than it needs another progress bar. Today
`ui/src/components/Mascot.svelte` is an honest **emoji placeholder** (🤖 / 👋 / 🤔
/ 🎉 / 😅 that bobs gently). This note is the plan to replace it with real art,
sound, and light gamification. It explicitly **needs an artist** — that's why it's
Tier C, not just unbuilt code.

## States (already modelled, just placeholder art)

The component takes a `mood` prop and already enumerates the reaction states the
flow drives:

| State (`mood`) | When | Placeholder |
|---|---|---|
| `happy` (idle) | resting / between actions | 🤖 |
| `wave` | greeting on a new screen | 👋 |
| `think` | model is working ("Teach!", transcribing) | 🤔 |
| `cheer` | success — good clip, gate reached, run finished | 🎉 |
| `oops` | a gentle failure (too quiet, couldn't decode) | 😅 |

Keeping the state machine now means swapping art later changes assets, not logic.

## Asset pipeline (the artist's deliverable)

- One mascot, the five states above, as **SVG** (crisp at any size, tiny, themeable)
  or a small sprite/Lottie animation per state. SVG/Lottie keeps the bundle small
  and offline.
- A short **sound** per celebratory state (success chime, gentle "oops"), kept
  optional and respectful of reduced-motion / quiet settings
  (`ACCESSIBILITY.md`).
- Assets live under `ui/src/assets/mascot/`; `Mascot.svelte` maps `mood → asset`
  exactly as it maps `mood → emoji` today.
- Licensing: commissioned or CC0/permissive art, recorded in
  `THIRD_PARTY.md`; the project is GPL-3.0-or-later.

## Gamification (light, never coercive)

Tie reactions to real milestones the director already knows: first good clip,
sufficiency gate reached, smartness crossing a threshold, run complete. Optional
stickers/streaks — encouragement, never dark patterns, and never a reason to keep
the user recording past "enough".

## Status

**Tier C** (#31). The `Mascot.svelte` component and its five-state contract exist
with emoji placeholders that already animate and carry an `aria-label`; real art,
sound, and the milestone-driven gamification are pending and require an artist —
outside what can be produced in this environment.
