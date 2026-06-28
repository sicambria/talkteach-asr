<script>
  // Screen 3 — Teach it!
  // One big button starts teaching. We then ask the backend "how's it going?"
  // every ~1.5s and show a progress bar and a "How smart is it?" meter.
  // jargon-free: no "training", "epochs as numbers only", no "WER".
  import { createEventDispatcher, onDestroy, onMount } from 'svelte';
  import { startTraining, trainProgress, getPlan } from '../lib/api.js';
  import { sufficiency, currentRun, grownUpMode } from '../lib/store.js';
  import { TRAIN_POLL_MS } from '../lib/constants.js';
  import Mascot from '../components/Mascot.svelte';

  const dispatch = createEventDispatcher();

  let runId = null;
  let progress = null; // TrainProgress
  let polling = false;
  let paused = false;
  let errorMsg = '';
  let pollTimer = null;

  // The director's plan + detected hardware, for Grown-up mode. We fetch this
  // up front so a grown-up can see *why* before pressing Teach. Kids never see
  // it — the kid view is just the smartness meter and progress.
  let plan = null;
  let hardware = null;

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
          errorMsg = "Teaching stopped early. Let's try again.";
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
      ? "All done! It's ready to try."
      : failed
        ? "Oops, that didn't work."
        : fractionPct > 66
          ? 'Almost there…'
          : fractionPct > 33
            ? 'Getting smarter!'
            : polling
              ? 'Warming up the brain…'
              : '');
</script>

<section class="screen">
  <Mascot mood={done ? 'cheer' : failed ? 'oops' : polling ? 'think' : 'happy'} size={100} />
  <h1>Teach it!</h1>

  {#if !polling && !done}
    <p>When you press the button, the computer will learn from your recordings.</p>
    <button class="big" disabled={!readyToTeach} on:click={teach}>
      {readyToTeach ? 'Teach it! ✨' : 'Record more first…'}
    </button>
    {#if paused}
      <button class="secondary" on:click={resume}>Keep watching ▶</button>
    {/if}
  {/if}

  {#if progress || polling}
    <div class="card">
      <h2>How far along?</h2>
      <div class="meter"><div class="fill" style="width:{fractionPct}%"></div></div>
      <p>{fractionPct}%</p>

      <h2>How smart is it?</h2>
      <div class="meter smart"><div class="fill" style="width:{smartPct}%"></div></div>
      <p>{smartPct}% smart</p>

      <p class="status">{friendlyStatus}</p>
    </div>

    {#if polling && !done}
      <div class="row">
        <button class="ghost" on:click={pause}>⏸ Pause</button>
        <button class="ghost" on:click={closeForNow}>Close and continue later</button>
      </div>
    {/if}
  {/if}

  {#if errorMsg}
    <p class="error">{errorMsg}</p>
    <button class="secondary" on:click={teach}>Try again</button>
  {/if}

  {#if done}
    <button class="big" on:click={() => dispatch('next')}>Next: Try it! ▶</button>
  {/if}

  {#if $grownUpMode}
    <div class="grownup">
      <h3>Grown-up mode</h3>
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
      run_id: {runId}
      {'\n'}progress: {JSON.stringify(progress)}
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
</style>
