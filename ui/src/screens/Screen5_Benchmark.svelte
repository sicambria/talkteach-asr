<script>
  // The Arena: pick the languages, TTS voices, and ASR engines to compare, run the
  // whole matrix, and see them ranked on an ELO leaderboard with 🥇🥈🥉.
  import { createEventDispatcher, onDestroy, onMount } from 'svelte';
  import {
    getBenchmarkOptions,
    startBenchmark,
    benchmarkStatus,
    cancelBenchmark,
  } from '../lib/api.js';
  import { benchmark } from '../lib/store.js';
  import { BENCH_POLL_MS } from '../lib/constants.js';
  import Podium from '../components/Podium.svelte';
  import Scoreboard from '../components/Scoreboard.svelte';
  import HeadToHeadGrid from '../components/HeadToHeadGrid.svelte';

  const dispatch = createEventDispatcher();

  let options = null; // { tts:[], engines:[], languages:[], default_language, defaults }
  let langPick = new Set();
  let ttsPick = new Set();
  let enginePick = new Set();
  let trainClips = 6;
  let evalClips = 6;

  let benchId = null;
  let status = ''; // running | done | cancelled | failed
  let message = '';
  let report = null; // scoreboard payload
  let errorMsg = '';
  let pollTimer = null;

  $: running = status === 'running';
  $: comboCount = langPick.size * ttsPick.size * enginePick.size;
  $: board = report?.scoreboard ?? [];
  $: extremes = report?.clip_extremes ?? {};
  $: perVoice = report?.per_voice ?? {};
  $: matrix = report?.matrix ?? [];
  $: cellsDone = matrix.length;

  onMount(async () => {
    try {
      options = await getBenchmarkOptions();
      // Pre-tick everything available so a first run is one click. Default to just
      // the project's language so the very first contest is quick.
      const def = options.default_language;
      langPick = new Set(
        options.languages.some((l) => l.code === def)
          ? [def]
          : options.languages.slice(0, 1).map((l) => l.code)
      );
      ttsPick = new Set(options.tts.filter((t) => t.available).map((t) => t.provider));
      enginePick = new Set(options.engines.filter((e) => e.available).map((e) => e.name));
      const d = options.defaults || {};
      trainClips = d.train_clips ?? 6;
      evalClips = d.eval_clips ?? 6;
    } catch (e) {
      errorMsg = e.message || "Couldn't load the contest options.";
    }
    // Re-attach to an in-flight run if you navigated away and came back.
    const saved = $benchmark;
    if (saved?.benchmark_id) {
      benchId = saved.benchmark_id;
      report = saved.report ?? null;
      status = saved.status ?? 'running';
      if (status === 'running') startPolling();
    }
  });

  onDestroy(() => stopPolling());

  function toggle(set, key) {
    const next = new Set(set);
    next.has(key) ? next.delete(key) : next.add(key);
    return next;
  }

  function stopPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = null;
  }

  async function tick() {
    if (!benchId) return;
    try {
      const r = await benchmarkStatus(benchId);
      status = r.status;
      message = r.message;
      report = r.report;
      benchmark.set({ benchmark_id: benchId, status, report });
      if (r.done) stopPolling();
    } catch (e) {
      errorMsg = e.message || 'Lost track of the contest.';
      stopPolling();
    }
  }

  function startPolling() {
    stopPolling();
    tick();
    pollTimer = setInterval(tick, BENCH_POLL_MS);
  }

  async function run() {
    errorMsg = '';
    if (!comboCount) {
      errorMsg = 'Pick at least one language, one voice, and one engine.';
      return;
    }
    report = null;
    status = 'running';
    message = 'Getting the contest ready…';
    try {
      const selection = {
        languages: [...langPick],
        tts: options.tts
          .filter((t) => ttsPick.has(t.provider))
          .map((t) => ({ provider: t.provider, voice: t.voice })),
        engines: options.engines
          .filter((e) => enginePick.has(e.name))
          .map((e) => ({ name: e.name, plan: e.plan })),
        train_clips: trainClips,
        eval_clips: evalClips,
      };
      const res = await startBenchmark(selection);
      benchId = res.benchmark_id;
      benchmark.set({ benchmark_id: benchId, status: 'running', report: null });
      startPolling();
    } catch (e) {
      status = 'failed';
      errorMsg = e.message || "Couldn't start the contest.";
    }
  }

  async function stop() {
    try {
      await cancelBenchmark(benchId);
      message = 'Stopping…';
    } catch (e) {
      errorMsg = e.message || "Couldn't stop the contest.";
    }
  }
</script>

<section class="arena">
  <header class="arena-head">
    <button class="ghost" on:click={() => dispatch('back')}>← Back</button>
    <h1>🏆 Arena</h1>
    <p class="sub">
      Compare speech-recognition engines: pick what to test, run them on the same sentences, and see
      them ranked by ELO.
    </p>
  </header>

  {#if errorMsg}<p class="error">{errorMsg}</p>{/if}

  {#if !options}
    <p>Loading the options…</p>
  {:else}
    <!-- Picker -->
    <div class="card picker">
      <div class="pick-col">
        <h3>Languages</h3>
        {#each options.languages as l}
          <label>
            <input
              type="checkbox"
              checked={langPick.has(l.code)}
              disabled={running}
              on:change={() => (langPick = toggle(langPick, l.code))}
            />
            {l.name}
            <span class="why">({l.code})</span>
          </label>
        {/each}
      </div>

      <div class="pick-col">
        <h3>Voices</h3>
        {#each options.tts as t}
          <label class:disabled={!t.available} title={t.available ? '' : t.detail}>
            <input
              type="checkbox"
              checked={ttsPick.has(t.provider)}
              disabled={!t.available || running}
              on:change={() => (ttsPick = toggle(ttsPick, t.provider))}
            />
            {t.provider}
            {#if !t.available}<span class="why">(unavailable)</span>{/if}
          </label>
        {/each}
        <p class="note">Voices speak each language's own sentences.</p>
      </div>

      <div class="pick-col">
        <h3>Engines</h3>
        {#each options.engines as e}
          <label class:disabled={!e.available} title={e.available ? '' : e.detail}>
            <input
              type="checkbox"
              checked={enginePick.has(e.name)}
              disabled={!e.available || running}
              on:change={() => (enginePick = toggle(enginePick, e.name))}
            />
            {e.label || e.name}
            {#if !e.available}<span class="why">(unavailable)</span>{/if}
          </label>
        {/each}
      </div>

      <div class="pick-col">
        <h3>Sentences</h3>
        <label class="num"
          >For training
          <input type="number" min="1" max="50" bind:value={trainClips} disabled={running} />
        </label>
        <label class="num"
          >For scoring
          <input type="number" min="1" max="50" bind:value={evalClips} disabled={running} />
        </label>
      </div>
    </div>

    <div class="run-row">
      {#if running}
        <button class="secondary" on:click={stop}>⏹ Stop</button>
        <span class="status">{message} ({cellsDone}/{comboCount} done)</span>
      {:else}
        <button class="big" on:click={run} disabled={!comboCount}>
          Run ({comboCount}
          {comboCount === 1 ? 'combination' : 'combinations'})
        </button>
        {#if status}<span class="status">{message}</span>{/if}
      {/if}
    </div>
  {/if}

  <!-- Results -->
  {#if report && board.length}
    <Podium {board} />

    <div class="card">
      <h2>Leaderboard</h2>
      <Scoreboard {board} />
    </div>

    <div class="card">
      <h2>Head-to-head</h2>
      <HeadToHeadGrid grid={report.head_to_head} />
    </div>

    {#if Object.keys(extremes).length}
      <div class="card">
        <h2>Easiest & hardest sentence</h2>
        <div class="extremes">
          {#each Object.entries(extremes) as [eng, ex]}
            <div class="ex">
              <div class="ex-eng">{eng}</div>
              <div class="ex-line good">
                🟢 “{ex.best.prompt}” — {ex.best.wer.toFixed(3)}
                <span class="dim">({ex.best.language ?? ex.best.tts})</span>
              </div>
              <div class="ex-line bad">
                🔴 “{ex.worst.prompt}” — {ex.worst.wer.toFixed(3)}
                <span class="dim">({ex.worst.language ?? ex.worst.tts})</span>
              </div>
            </div>
          {/each}
        </div>
      </div>
    {/if}

    {#if Object.keys(perVoice).length}
      <div class="card">
        <h2>Breakdown by language & voice</h2>
        <table class="voice">
          <thead>
            <tr
              ><th>Engine</th><th>Lang</th><th>Voice</th><th>WER</th><th>CER</th><th>Δ vs base</th
              ><th>Train(s)</th></tr
            >
          </thead>
          <tbody>
            {#each Object.entries(perVoice) as [eng, rows]}
              {#each rows as c}
                <tr>
                  <td class="l">{eng}</td>
                  <td class="l">{c.language ?? '—'}</td>
                  <td class="l">{c.voice ?? c.tts}</td>
                  <td>{c.wer == null ? '—' : c.wer.toFixed(3)}</td>
                  <td>{c.cer == null ? '—' : c.cer.toFixed(3)}</td>
                  <td class:good={c.delta_wer > 0}>
                    {c.delta_wer == null
                      ? '—'
                      : (c.delta_wer >= 0 ? '+' : '') + c.delta_wer.toFixed(3)}
                  </td>
                  <td>{c.train_seconds == null ? '—' : c.train_seconds.toFixed(1)}</td>
                </tr>
              {/each}
            {/each}
          </tbody>
        </table>
      </div>
    {/if}

    <p class="ground">
      WER and CER on the shared, held-out sentences are the ground truth; ELO and the medals are a
      leaderboard layer on top.
    </p>
  {:else if status === 'done'}
    <p class="status">No engine finished — check the unavailable items above.</p>
  {/if}
</section>

<style>
  .arena {
    max-width: 900px;
    margin: 0 auto 60px;
    padding: 0 16px;
  }

  .arena-head {
    text-align: center;
    margin: 10px 0 18px;
  }

  .arena-head h1 {
    margin: 6px 0 2px;
  }

  .arena-head .ghost {
    float: left;
  }

  .sub {
    color: var(--tt-ink-soft);
  }

  .picker {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 18px;
    text-align: left;
  }

  @media (max-width: 760px) {
    .picker {
      grid-template-columns: repeat(2, 1fr);
    }
  }

  .pick-col h3 {
    margin: 0 0 8px;
    color: var(--tt-primary-dark);
  }

  .pick-col .note {
    color: var(--tt-ink-soft);
    font-size: 0.8rem;
    margin: 6px 0 0;
  }

  .pick-col label {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 5px 0;
    font-size: 1rem;
  }

  .pick-col label.disabled {
    opacity: 0.5;
  }

  .pick-col .why {
    color: var(--tt-ink-soft);
    font-size: 0.82rem;
  }

  label.num {
    justify-content: space-between;
  }

  label.num input {
    width: 72px;
    padding: 6px 8px;
    border-radius: 10px;
    border: 2px solid #e3e6ee;
    font: inherit;
  }

  .run-row {
    display: flex;
    align-items: center;
    gap: 16px;
    justify-content: center;
    margin: 16px 0 8px;
    flex-wrap: wrap;
  }

  .status {
    color: var(--tt-ink-soft);
    font-weight: 600;
  }

  .error {
    color: var(--tt-oops);
    font-weight: 700;
    text-align: center;
  }

  .extremes {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 12px;
    text-align: left;
  }

  .ex {
    background: #f7f8fb;
    border-radius: 14px;
    padding: 10px 12px;
  }

  .ex-eng {
    font-weight: 800;
    margin-bottom: 4px;
  }

  .ex-line {
    font-size: 0.92rem;
  }

  .dim {
    color: var(--tt-ink-soft);
  }

  table.voice {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.93rem;
  }

  table.voice th,
  table.voice td {
    padding: 7px 9px;
    text-align: right;
    border-bottom: 1px solid #f1f2f6;
  }

  table.voice th {
    color: var(--tt-ink-soft);
  }

  table.voice .l {
    text-align: left;
  }

  td.good {
    color: var(--tt-happy);
    font-weight: 700;
  }

  .ground {
    color: var(--tt-ink-soft);
    font-size: 0.85rem;
    text-align: center;
    margin-top: 18px;
  }
</style>
