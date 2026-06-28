<script>
  // The full ELO leaderboard table. WER/CER are the ground truth; ELO is the
  // headline. Δ vs base shows how much fine-tuning improved on the raw model.
  export let board = [];

  const EMOJI = { gold: '🥇', silver: '🥈', bronze: '🥉' };
  const pct = (x) => (x == null ? '—' : `${Math.round(x * 100)}%`);
  const f3 = (x) => (x == null ? '—' : x.toFixed(3));
  const f1 = (x) => (x == null ? '—' : x.toFixed(1));
  const signed = (x) => (x == null ? '—' : `${x >= 0 ? '+' : ''}${x.toFixed(3)}`);
</script>

<table class="board">
  <thead>
    <tr>
      <th>#</th>
      <th aria-label="medal"></th>
      <th>Engine</th>
      <th>ELO</th>
      <th>W-L-T</th>
      <th>Win%</th>
      <th>WER</th>
      <th>CER</th>
      <th>Δ vs base</th>
      <th>Train(s)</th>
      <th>Conds</th>
    </tr>
  </thead>
  <tbody>
    {#each board as r, i}
      <tr class:top={r.medal === 'gold'}>
        <td>{i + 1}</td>
        <td class="medal">{EMOJI[r.medal] || ''}</td>
        <td class="engine">{r.engine}</td>
        <td class="elo">{r.elo}</td>
        <td>{r.wins}-{r.losses}-{r.ties}</td>
        <td>{pct(r.win_rate)}</td>
        <td>{f3(r.mean_wer)}</td>
        <td>{f3(r.mean_cer)}</td>
        <td class:good={r.mean_delta_wer > 0}>{signed(r.mean_delta_wer)}</td>
        <td>{f1(r.mean_train_seconds)}</td>
        <td>{r.cells}</td>
      </tr>
    {/each}
    {#if !board.length}
      <tr><td colspan="11" class="empty">No finished engines yet…</td></tr>
    {/if}
  </tbody>
</table>

<style>
  .board {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.95rem;
  }

  th,
  td {
    padding: 8px 10px;
    text-align: right;
    white-space: nowrap;
  }

  th:nth-child(3),
  td.engine {
    text-align: left;
  }

  thead th {
    color: var(--tt-ink-soft);
    font-weight: 700;
    border-bottom: 2px solid #eceef3;
  }

  tbody tr {
    border-bottom: 1px solid #f1f2f6;
  }

  tr.top {
    background: rgba(255, 209, 102, 0.18);
  }

  .engine {
    font-weight: 800;
    color: var(--tt-ink);
  }

  .elo {
    font-weight: 800;
    color: var(--tt-primary-dark);
  }

  .medal {
    font-size: 1.2rem;
    text-align: center;
  }

  td.good {
    color: var(--tt-happy);
    font-weight: 700;
  }

  .empty {
    text-align: center;
    color: var(--tt-ink-soft);
    padding: 18px;
  }
</style>
