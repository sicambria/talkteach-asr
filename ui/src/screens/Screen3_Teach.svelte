<script>
  // Screen 3 — Teach it!
  // One big button starts teaching. We then ask the backend "how's it going?"
  // every ~1.5s and show a progress bar and a "How smart is it?" meter.
  // jargon-free: no "training", "epochs as numbers only", no "WER".
  import { createEventDispatcher, onDestroy, onMount } from 'svelte';
  import { startTraining, trainProgress, getPlan, metrics, evalReport } from '../lib/api.js';
  import { sufficiency, currentRun, advancedMode } from '../lib/store.js';
  import { TRAIN_POLL_MS } from '../lib/constants.js';
  import { t } from '../lib/i18n.js';
  import { focusOnMount } from '../lib/a11y.js';
  import Mascot from '../components/Mascot.svelte';

  const dispatch = createEventDispatcher();

  let runId = null;
  let progress = null; // TrainProgress
  let polling = false;
  let paused = false;
  let errorMsg = '';
  let pollTimer = null;

  // The director's plan + detected hardware, for Advanced mode. We fetch this
  // up front so the user can see *why* before pressing Teach. Easy mode hides
  // it — the easy view is just the smartness meter and progress.
  let plan = null;
  let hardware = null;

  // Advanced-mode training metrics (#53): the real trainer writes a loss/WER curve
  // to metrics.jsonl; we read it once teaching finishes. Simulated runs have none,
  // and curveData.has_curve tells us to say so honestly instead of drawing nothing.
  let curveData = null;

  async function loadMetrics() {
    try {
      curveData = await metrics(runId);
    } catch {
      curveData = null; // panel just omits the curve if the read fails
    }
  }

  // Build an SVG polyline (viewBox 0..100 × 0..30) for one metric, normalised to
  // its own min/max so both loss and WER are visible on the same little chart.
  function sparkPoints(curve, key) {
    const ys = curve.map((p) => p[key]).filter((v) => typeof v === 'number');
    if (ys.length < 2) return '';
    const lo = Math.min(...ys);
    const hi = Math.max(...ys);
    const span = hi - lo || 1;
    return curve
      .map((p, i) => {
        const x = (i / (curve.length - 1)) * 100;
        const y = 30 - ((p[key] - lo) / span) * 28 - 1; // invert: lower = bottom
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(' ');
  }

  $: curve = curveData?.curve || [];
  $: lossPts = curve.length ? sparkPoints(curve, 'loss') : '';
  $: werPts = curve.length ? sparkPoints(curve, 'wer') : '';

  // "Where it still struggles" report (#52) — an active-learning signal, loaded on
  // demand from Advanced mode. Held-out accuracy is best_val_wer (the curve/meter).
  let report = null;
  let reportBusy = false;
  async function loadReport() {
    if (!runId) return;
    reportBusy = true;
    try {
      report = await evalReport(runId);
    } catch (e) {
      report = { available: false, message: e.message || "Couldn't build the report." };
    } finally {
      reportBusy = false;
    }
  }

  onMount(async () => {
    try {
      const res = await getPlan();
      plan = res.plan;
      hardware = res.hardware;
    } catch {
      // The plan panel just stays hidden if the backend isn't up yet.
    }
  });

  $: s = $sufficiency;
  $: readyToTeach = s && s.status === 'ready';

  $: fractionPct = progress ? Math.round((progress.fraction || 0) * 100) : 0;
  $: smartPct = progress ? Math.round((progress.smartness || 0) * 100) : 0;
  $: done = progress?.done === true;
  $: failed = progress?.failed === true;

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
    polling = false;
  }

  onDestroy(stopPolling);

  async function tick() {
    if (!runId) return;
    try {
      progress = await trainProgress(runId);
      currentRun.set({ run_id: runId, ...progress });
      if (progress.done || progress.failed) {
        stopPolling();
        if (progress.failed) {
          errorMsg = $t('teach.stopped_early');
        } else {
          loadMetrics(); // Advanced-mode loss/WER curve (#53)
        }
      }
    } catch (e) {
      errorMsg = e.message || 'I lost track of the teaching.';
      stopPolling();
    }
  }

  function startPolling() {
    stopPolling();
    polling = true;
    paused = false;
    tick(); // immediate first read
    pollTimer = setInterval(tick, TRAIN_POLL_MS);
  }

  async function teach() {
    errorMsg = '';
    progress = null;
    try {
      const res = await startTraining();
      runId = res.run_id;
      if (res.plan) plan = res.plan; // the actual plan being used
      currentRun.set({ run_id: runId });
      startPolling();
    } catch (e) {
      errorMsg = e.message || "I couldn't start teaching.";
    }
  }

  // Phase 0: Pause just stops watching; the run keeps going on the server.
  function pause() {
    stopPolling();
    paused = true;
  }

  function resume() {
    startPolling();
  }

  function closeForNow() {
    // Stop watching and step back; the run continues server-side.
    stopPolling();
    dispatch('back');
  }

  // A few cheerful status lines based on how far along we are.
  $: friendlyStatus =
    progress?.message ||
    (done
      ? $t('teach.done')
      : failed
        ? $t('teach.failed')
        : fractionPct > 66
          ? $t('teach.almost')
          : fractionPct > 33
            ? $t('teach.getting_smarter')
            : polling
              ? $t('teach.warming')
              : '');
</script>

<section class="screen">
  <Mascot mood={done ? 'cheer' : failed ? 'oops' : polling ? 'think' : 'happy'} size={100} />
  <h1 tabindex="-1" use:focusOnMount>{$t('teach.title')}</h1>

  {#if !polling && !done}
    <p>{$t('teach.intro')}</p>
    <button class="big" disabled={!readyToTeach} on:click={teach}>
      {readyToTeach ? $t('teach.teach_btn') : $t('teach.record_more')}
    </button>
    {#if paused}
      <button class="secondary" on:click={resume}>{$t('teach.keep_watching')}</button>
    {/if}
  {/if}

  {#if progress || polling}
    <div class="card">
      <h2>{$t('teach.how_far')}</h2>
      <div class="meter"><div class="fill" style="width:{fractionPct}%"></div></div>
      <p>{fractionPct}%</p>

      <h2>{$t('teach.how_smart')}</h2>
      <div class="meter smart"><div class="fill" style="width:{smartPct}%"></div></div>
      <p>{smartPct}{$t('teach.smart_suffix')}</p>

      <p class="status" aria-live="polite">{friendlyStatus}</p>
    </div>

    {#if polling && !done}
      <div class="row">
        <button class="ghost" on:click={pause}>{$t('teach.pause')}</button>
        <button class="ghost" on:click={closeForNow}>{$t('teach.close_later')}</button>
      </div>
    {/if}
  {/if}

  {#if errorMsg}
    <p class="error">{errorMsg}</p>
    <button class="secondary" on:click={teach}>{$t('teach.try_again')}</button>
  {/if}

  {#if done}
    <button class="big" on:click={() => dispatch('next')}>{$t('teach.next')}</button>
  {/if}

  {#if $advancedMode}
    <div class="advanced">
      <h3>Advanced</h3>
      {#if plan}
        <p>
          <strong>Engine:</strong>
          {plan.engine} &nbsp;·&nbsp;
          <strong>Model:</strong>
          {plan.base_checkpoint}
        </p>
        <p>
          <strong>Precision:</strong>
          {plan.precision} &nbsp;·&nbsp;
          <strong>Epochs:</strong>
          {plan.epochs}
        </p>
        {#if hardware}
          <p>
            <strong>Hardware:</strong>
            {hardware.compute}{hardware.gpu_name ? ` (${hardware.gpu_name})` : ''}
            {#if hardware.vram_gib}· {hardware.vram_gib} GiB VRAM{/if}
            {#if hardware.ram_gib}· {hardware.ram_gib} GiB RAM{/if}
          </p>
        {/if}
        {#if plan.rationale && plan.rationale.length}
          <p><strong>Why this plan:</strong></p>
          <ul class="rationale">
            {#each plan.rationale as reason}
              <li>{reason}</li>
            {/each}
          </ul>
        {/if}
      {:else}
        <p>Working out the plan…</p>
      {/if}

      {#if done}
        <div class="metrics">
          <p><strong>Training curve</strong></p>
          {#if curveData && curveData.has_curve}
            <svg
              class="spark"
              viewBox="0 0 100 30"
              preserveAspectRatio="none"
              role="img"
              aria-label="Loss and word-error-rate over training"
            >
              {#if lossPts}<polyline class="loss" points={lossPts} />{/if}
              {#if werPts}<polyline class="wer" points={werPts} />{/if}
            </svg>
            <p class="legend">
              <span class="k loss">loss</span>
              <span class="k wer">WER</span>
              {#if curveData.best_val_wer != null}
                · best WER {(curveData.best_val_wer * 100).toFixed(1)}%
              {/if}
            </p>
          {:else}
            <p class="muted">
              Detailed metrics are recorded during a real training run (this run had none to show).
            </p>
          {/if}
        </div>

        <div class="report">
          <button class="ghost" on:click={loadReport} disabled={reportBusy}>
            {reportBusy ? 'Checking…' : 'Where does it still struggle?'}
          </button>
          {#if report}
            {#if report.available === false}
              <p class="muted">{report.message || 'Report needs the ML pack installed.'}</p>
            {:else}
              {#if report.best_val_wer != null}
                <p>
                  Held-out accuracy:
                  <strong>{((1 - report.best_val_wer) * 100).toFixed(1)}%</strong>
                  ({(report.best_val_wer * 100).toFixed(1)}% WER on unseen clips)
                </p>
              {/if}
              {#if report.hardest && report.hardest.length}
                <p><strong>Hardest clips to fix or relabel next:</strong></p>
                <ul class="rationale">
                  {#each report.hardest as h}
                    <li>
                      “{h.reference}” → heard “{h.hypothesis}” ({Math.round(h.wer * 100)}% off)
                    </li>
                  {/each}
                </ul>
              {/if}
              {#if report.report?.top_substitutions?.length}
                <p>
                  <strong>Most common confusions:</strong>
                  {#each report.report.top_substitutions.slice(0, 5) as s, i}{i > 0
                      ? ', '
                      : ' '}{s.ref}→{s.hyp} ({s.count}){/each}
                </p>
              {/if}
            {/if}
          {/if}
        </div>
      {/if}

      <p class="adv-meta">run_id: {runId} · progress: {JSON.stringify(progress)}</p>
    </div>
  {/if}
</section>

<style>
  .status {
    font-size: 1.3rem;
    font-weight: 700;
    color: var(--tt-primary-dark);
  }

  .error {
    color: var(--tt-oops);
    font-weight: 700;
  }

  .rationale {
    text-align: left;
    margin: 6px 0;
  }

  .metrics {
    text-align: left;
    margin: 10px 0;
  }

  .spark {
    width: 100%;
    height: 60px;
    background: rgba(0, 0, 0, 0.04);
    border-radius: 8px;
  }

  .spark polyline {
    fill: none;
    stroke-width: 1.2;
    vector-effect: non-scaling-stroke;
  }

  .spark polyline.loss {
    stroke: var(--tt-accent, #e0559b);
  }

  .spark polyline.wer {
    stroke: var(--tt-primary-dark, #2b6cb0);
  }

  .legend {
    font-size: 0.9rem;
    margin: 4px 0 0;
  }

  .legend .k {
    font-weight: 700;
    margin-right: 10px;
  }

  .legend .k.loss {
    color: var(--tt-accent, #e0559b);
  }

  .legend .k.wer {
    color: var(--tt-primary-dark, #2b6cb0);
  }

  .muted {
    color: var(--tt-ink-soft);
  }

  .report {
    text-align: left;
    margin: 10px 0;
  }

  .adv-meta {
    font-size: 0.8rem;
    color: var(--tt-ink-soft);
    word-break: break-all;
  }
</style>
