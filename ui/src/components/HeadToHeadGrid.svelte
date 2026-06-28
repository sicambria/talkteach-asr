<script>
  // Head-to-head: how many shared clips the row engine transcribed better than
  // the column engine. The diagonal is a dash (an engine doesn't play itself).
  export let grid = {};

  $: engines = Object.keys(grid).sort();
  // Shade a cell by how dominant the win count is, relative to the grid's max.
  $: max = Math.max(
    1,
    ...engines.flatMap((a) => engines.filter((b) => b !== a).map((b) => grid[a]?.[b] ?? 0))
  );
</script>

{#if engines.length >= 2}
  <table class="grid">
    <thead>
      <tr>
        <th></th>
        {#each engines as b}<th>{b}</th>{/each}
      </tr>
    </thead>
    <tbody>
      {#each engines as a}
        <tr>
          <th class="row-label">{a}</th>
          {#each engines as b}
            {#if a === b}
              <td class="self">·</td>
            {:else}
              <td style="background: rgba(76,201,176,{((grid[a]?.[b] ?? 0) / max) * 0.55})">
                {grid[a]?.[b] ?? 0}
              </td>
            {/if}
          {/each}
        </tr>
      {/each}
    </tbody>
  </table>
  <p class="hint">Row beat column on this many shared clips.</p>
{:else}
  <p class="hint">Run at least two engines to see head-to-heads.</p>
{/if}

<style>
  .grid {
    border-collapse: collapse;
    font-size: 0.95rem;
  }

  th,
  td {
    padding: 8px 12px;
    text-align: center;
    border: 1px solid #eceef3;
    min-width: 56px;
  }

  thead th,
  .row-label {
    color: var(--tt-ink-soft);
    font-weight: 700;
    background: #f7f8fb;
  }

  .row-label {
    text-align: right;
  }

  td {
    font-weight: 700;
    color: var(--tt-ink);
  }

  .self {
    color: var(--tt-ink-soft);
    background: #fafbfc;
  }

  .hint {
    color: var(--tt-ink-soft);
    font-size: 0.85rem;
    margin-top: 6px;
  }
</style>
