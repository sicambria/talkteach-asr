<script>
  // The winners' podium: top three engines by ELO, shown silver–gold–bronze so
  // gold stands tallest in the middle. Ties share a medal (the backend decides).
  export let board = [];

  const EMOJI = { gold: '🥇', silver: '🥈', bronze: '🥉' };

  // Visual order: silver (left), gold (centre, tallest), bronze (right).
  $: top = board.filter((r) => r.medal);
  $: gold = top.find((r) => r.medal === 'gold') || null;
  // Two engines can tie for gold; only then show them both (with "tied") on the
  // top step — a single winner gets the plain "{elo} ELO" scalar branch.
  $: golds = top.filter((r) => r.medal === 'gold');
  $: silver = top.find((r) => r.medal === 'silver') || null;
  $: bronze = top.find((r) => r.medal === 'bronze') || null;
  $: ordered = [silver, golds.length > 1 ? golds : gold, bronze];
</script>

<div class="podium" aria-label="Winners' podium">
  {#each ordered as slot, i}
    {#if slot}
      <div class="step step-{i}" class:tall={i === 1}>
        <div class="medal">{EMOJI[(Array.isArray(slot) ? slot[0] : slot).medal]}</div>
        <div class="who">
          {#if Array.isArray(slot)}
            {#each slot as r}
              <div class="engine">{r.engine}</div>
            {/each}
            <div class="elo">tied · {slot[0].elo} ELO</div>
          {:else}
            <div class="engine">{slot.engine}</div>
            <div class="elo">{slot.elo} ELO</div>
          {/if}
        </div>
        <div class="block"></div>
      </div>
    {/if}
  {/each}
</div>

<style>
  .podium {
    display: flex;
    align-items: flex-end;
    justify-content: center;
    gap: 14px;
    margin: 10px 0 24px;
    min-height: 200px;
  }

  .step {
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 150px;
  }

  .medal {
    font-size: 2.4rem;
    line-height: 1;
  }

  .who {
    margin: 6px 0 8px;
    text-align: center;
  }

  .engine {
    font-weight: 800;
    color: var(--tt-ink);
    font-size: 1.1rem;
  }

  .elo {
    color: var(--tt-ink-soft);
    font-size: 0.9rem;
  }

  .block {
    width: 100%;
    border-radius: var(--tt-radius) var(--tt-radius) 0 0;
    background: var(--tt-accent);
    box-shadow: 0 6px 16px rgba(29, 36, 51, 0.12);
  }

  /* silver, gold, bronze step heights */
  .step-0 .block {
    height: 86px;
    background: #c9d2dc;
  }
  .step-1 .block {
    height: 130px;
    background: var(--tt-sun);
  }
  .step-2 .block {
    height: 64px;
    background: #e6b07a;
  }

  .tall .engine {
    font-size: 1.25rem;
  }
</style>
