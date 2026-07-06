// Small accessibility helpers for the TalkTeach UI (#37).

/**
 * Svelte action: move keyboard focus to this element when it mounts.
 *
 * Used on each screen's `<h1 tabindex="-1">` so that when the wizard swaps
 * screens, keyboard and screen-reader users land at the top of the new screen
 * instead of losing focus to `<body>`. Deferred one frame so the node is in the
 * DOM. `:focus-visible` heuristics mean mouse users won't see an outline from
 * this programmatic focus; keyboard users will, which is the intent.
 */
export function focusOnMount(node) {
  const id = requestAnimationFrame(() => node.focus?.());
  return {
    destroy() {
      cancelAnimationFrame(id);
    },
  };
}
