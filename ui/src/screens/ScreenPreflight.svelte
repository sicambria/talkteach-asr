<script>
  // Pre-flight screen (#18) — "Is everything ready?"
  // Runs BEFORE recording. Calls GET /api/preflight (already shipped + tested)
  // and shows each check (disk / memory / speed / microphone) with a friendly
  // ok / warn / fail icon, a plain-language detail, and how to fix it. The
  // checks are non-fatal by design, so "Continue" is always allowed — a missing
  // mic just means "drag in existing recordings instead". jargon-free.
  import { createEventDispatcher, onMount } from 'svelte';
  import { preflight } from '../lib/api.js';
  import { advancedMode } from '../lib/store.js';
  import { t } from '../lib/i18n.js';
  import { focusOnMount } from '../lib/a11y.js';
  import Mascot from '../components/Mascot.svelte';

  const dispatch = createEventDispatcher();

  let report = null; // { results:[{name,status,detail,remedy}], ok, can_train, summary }
  let loading = true;
  let errorMsg = '';

  // Friendly icon per check status (ok | warn | fail).
  const ICON = { ok: '✅', warn: '⚠️', fail: '⛔' };

  async function load() {
    loading = true;
    errorMsg = '';
    try {
      report = await preflight();
    } catch (e) {
      report = null;
      errorMsg = e.message || $t('preflight.error');
    } finally {
      loading = false;
    }
  }

  onMount(load);

  $: allGood = report?.ok === true;
</script>

<section class="screen">
  <Mascot mood={allGood ? 'cheer' : 'think'} size={90} />
  <h1 tabindex="-1" use:focusOnMount>{$t('preflight.title')}</h1>
  <p>{$t('preflight.subtitle')}</p>

  {#if loading}
    <p aria-live="polite">{$t('preflight.checking')}</p>
  {:else if errorMsg}
    <div class="card">
      <span class="thumb down">😕</span>
      <p class="error">{errorMsg}</p>
      <p class="hint">{$t('preflight.error_hint')}</p>
    </div>
  {:else if report}
    <!-- Headline: ready vs fix-this-first. -->
    <div class="card headline" class:good={allGood}>
      <span class="big-emoji">{allGood ? '🎉' : '🔧'}</span>
      <h2>{allGood ? $t('preflight.ready') : $t('preflight.fix')}</h2>
      <p>{report.summary}</p>
    </div>

    <!-- One row per check. -->
    <ul class="checks">
      {#each report.results as check}
        <li
          class="check card"
          class:warn={check.status === 'warn'}
          class:fail={check.status === 'fail'}
        >
          <span class="icon" aria-hidden="true">{ICON[check.status] ?? '•'}</span>
          <div class="body">
            <strong>{check.name}</strong>
            <p>{check.detail}</p>
            {#if check.remedy && check.status !== 'ok'}
              <p class="hint">{check.remedy}</p>
            {/if}
          </div>
        </li>
      {/each}
    </ul>
  {/if}

  <div class="row">
    <button class="ghost" on:click={() => dispatch('back')}>{$t('common.back')}</button>
    <button class="secondary" disabled={loading} on:click={load}>{$t('preflight.recheck')}</button>
    <button class="big" class:secondary={!allGood} on:click={() => dispatch('ready')}>
      {allGood ? $t('preflight.go') : $t('preflight.continue')}
    </button>
  </div>

  {#if $advancedMode}
    <div class="advanced">
      <h3>Advanced</h3>
      GET /api/preflight {report ? JSON.stringify(report) : '(no report)'}
    </div>
  {/if}
</section>

<style>
  .headline {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
  }

  .headline.good {
    background: #eafaf3;
  }

  .big-emoji {
    font-size: 3rem;
  }

  .checks {
    list-style: none;
    padding: 0;
    margin: 0;
  }

  .check {
    display: flex;
    align-items: flex-start;
    gap: 16px;
    text-align: left;
  }

  .check.warn {
    border-left: 6px solid var(--tt-sun);
  }

  .check.fail {
    border-left: 6px solid var(--tt-oops);
  }

  .check .icon {
    font-size: 1.8rem;
    line-height: 1.2;
  }

  .check .body {
    flex: 1;
  }

  .check .body p {
    margin: 4px 0 0;
  }

  .hint {
    color: var(--tt-ink-soft);
    font-size: 1rem;
  }

  .error {
    color: var(--tt-oops);
    font-weight: 700;
  }
</style>
