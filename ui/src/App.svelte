<script>
  // The app host. Shows either the Arena (the default landing view — compare
  // speech engines) or the step-by-step wizard (Record → Check → Teach → Try),
  // plus a stepper, a mascot, and an "Advanced" toggle for technical detail.
  import { STEPS } from './lib/constants.js';
  import { advancedMode, project } from './lib/store.js';
  import { t, locale, availableLocales, localeName } from './lib/i18n.js';
  import Mascot from './components/Mascot.svelte';

  import Screen0_NewProject from './screens/Screen0_NewProject.svelte';
  import ScreenPreflight from './screens/ScreenPreflight.svelte';
  import Screen1_Record from './screens/Screen1_Record.svelte';
  import Screen2_Check from './screens/Screen2_Check.svelte';
  import Screen3_Teach from './screens/Screen3_Teach.svelte';
  import Screen4_Try from './screens/Screen4_Try.svelte';
  import Screen5_Benchmark from './screens/Screen5_Benchmark.svelte';

  // 0 = New project (before the stepper). 1..4 = Record/Check/Teach/Try.
  let step = 0;
  // The Arena is the default landing view; the wizard is the other destination.
  let arena = true;
  // Pre-flight interstitial (#18): shown after New project, before Record, so a
  // so the user sees mic/disk/dependency status before recording starts.
  // step stays 0 while it's up, so the stepper stays hidden — it's a pre-wizard gate.
  let preflight = false;

  function goTo(n) {
    step = Math.max(0, Math.min(4, n));
  }

  function next() {
    goTo(step + 1);
  }

  // New project done → show the pre-flight gate (not straight to Record).
  function afterNewProject() {
    preflight = true;
  }

  // Pre-flight cleared → into the wizard at Record.
  function afterPreflight() {
    preflight = false;
    goTo(1);
  }

  function toggleAdvanced() {
    advancedMode.update((v) => !v);
  }

  function openArena() {
    arena = true;
  }

  function closeArena() {
    arena = false;
  }
</script>

<header class="topbar">
  <div class="brand">
    <Mascot mood="wave" size={48} />
    <span class="title">TalkTeach</span>
  </div>

  <!-- The friendly stepper. Step 0 (New project) is intentionally hidden. -->
  {#if step >= 1}
    <nav class="stepper" aria-label="Where we are">
      {#each STEPS as label, i}
        {@const n = i + 1}
        <button
          class="step"
          class:done={step > n}
          class:active={step === n}
          disabled={n > step}
          on:click={() => goTo(n)}
          aria-current={step === n ? 'step' : undefined}
        >
          <span class="dot">{step > n ? '✓' : n}</span>
          <span class="step-label">{label}</span>
        </button>
      {/each}
    </nav>
  {/if}

  <nav class="dest" aria-label="Sections">
    <!-- The Arena (compare engines) and the step-by-step wizard. -->
    <button class="dest-btn" class:on={arena} on:click={openArena}> {$t('app.arena')} </button>
    <button class="dest-btn" class:on={!arena} on:click={closeArena}> {$t('app.wizard')} </button>
  </nav>

  <!-- Language switcher (#36). Only English ships for real; "Pseudo (QA)" is a
       synthetic locale that proves the plumbing swaps every string via t(). -->
  <label class="lang-switch">
    <span class="sr-only">{$t('app.language')}</span>
    <select bind:value={$locale} aria-label={$t('app.language')}>
      {#each availableLocales() as code}
        <option value={code}>{localeName(code)}</option>
      {/each}
    </select>
  </label>

  <!-- "Advanced": a toggle that reveals technical detail panels. -->
  <button
    class="gear"
    class:on={$advancedMode}
    on:click={toggleAdvanced}
    title={$t('app.advanced_details')}
    aria-pressed={$advancedMode}
    aria-label={$t('app.advanced_details')}
  >
    ⚙
  </button>
</header>

<main>
  {#if arena}
    <Screen5_Benchmark on:back={closeArena} />
  {:else if preflight}
    <ScreenPreflight on:ready={afterPreflight} on:back={() => (preflight = false)} />
  {:else if step === 0}
    <Screen0_NewProject on:done={afterNewProject} />
  {:else if step === 1}
    <Screen1_Record on:next={next} />
  {:else if step === 2}
    <Screen2_Check on:next={next} on:back={() => goTo(1)} />
  {:else if step === 3}
    <Screen3_Teach on:next={next} on:back={() => goTo(2)} />
  {:else if step === 4}
    <Screen4_Try on:again={() => goTo(1)} />
  {/if}
</main>

{#if $advancedMode && !arena}
  <div class="advanced" style="max-width:820px;margin:0 auto 40px;">
    <h3>{$t('app.advanced')}</h3>
    Step: {step} ({step >= 1 ? STEPS[step - 1] : 'New project'})
    {'\n'}Project: {$project ? JSON.stringify($project) : '(none yet)'}
  </div>
{/if}

<style>
  .topbar {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 14px 22px;
    background: var(--tt-surface);
    box-shadow: 0 2px 10px rgba(29, 36, 51, 0.06);
  }

  .brand {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .title {
    font-size: 1.6rem;
    font-weight: 800;
    color: var(--tt-primary-dark);
  }

  .stepper {
    display: flex;
    gap: 10px;
    margin: 0 auto;
    flex-wrap: wrap;
  }

  .step {
    display: flex;
    align-items: center;
    gap: 8px;
    background: #f1f2f6;
    color: var(--tt-ink-soft);
    box-shadow: none;
    border-radius: 999px;
    padding: 8px 18px;
    min-height: 48px;
    font-size: 1.05rem;
  }

  .step.active {
    background: var(--tt-sun);
    color: var(--tt-ink);
  }

  .step.done {
    background: var(--tt-happy);
    color: white;
  }

  .step:disabled {
    opacity: 0.55;
    box-shadow: none;
  }

  .dot {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: rgba(0, 0, 0, 0.12);
    font-weight: 800;
  }

  .dest {
    display: flex;
    gap: 8px;
  }

  .dest-btn {
    background: #f1f2f6;
    color: var(--tt-ink-soft);
    box-shadow: none;
    font-size: 1rem;
    font-weight: 800;
    border-radius: 999px;
    padding: 8px 16px;
    min-height: 48px;
  }

  .dest-btn.on {
    background: var(--tt-accent);
    color: white;
  }

  .lang-switch select {
    width: auto;
    max-width: 180px;
    min-height: 48px;
    font-size: 1rem;
    padding: 8px 12px;
  }

  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
    white-space: nowrap;
    border: 0;
  }

  .gear {
    background: transparent;
    color: var(--tt-ink-soft);
    box-shadow: none;
    font-size: 1.6rem;
    padding: 8px 12px;
    min-height: 48px;
    min-width: 48px;
    opacity: 0.55;
  }

  .gear.on {
    opacity: 1;
    color: var(--tt-primary-dark);
  }
</style>
