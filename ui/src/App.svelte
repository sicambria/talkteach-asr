<script>
  // The wizard host. Holds the current step (0..4) and shows one screen at a
  // time, plus a friendly stepper, a mascot, and a hidden "Grown-up mode" gear.
  // jargon-free: every visible word here is plain language.
  import { STEPS } from "./lib/constants.js";
  import { grownUpMode, project } from "./lib/store.js";
  import Mascot from "./components/Mascot.svelte";

  import Screen0_NewProject from "./screens/Screen0_NewProject.svelte";
  import Screen1_Record from "./screens/Screen1_Record.svelte";
  import Screen2_Check from "./screens/Screen2_Check.svelte";
  import Screen3_Teach from "./screens/Screen3_Teach.svelte";
  import Screen4_Try from "./screens/Screen4_Try.svelte";

  // 0 = New project (before the stepper). 1..4 = Record/Check/Teach/Try.
  let step = 0;

  function goTo(n) {
    step = Math.max(0, Math.min(4, n));
  }

  function next() {
    goTo(step + 1);
  }

  function toggleGrownUp() {
    grownUpMode.update((v) => !v);
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
          aria-current={step === n ? "step" : undefined}
        >
          <span class="dot">{step > n ? "✓" : n}</span>
          <span class="step-label">{label}</span>
        </button>
      {/each}
    </nav>
  {/if}

  <!-- Hidden "Grown-up mode": a small gear that reveals technical panels. -->
  <button
    class="gear"
    class:on={$grownUpMode}
    on:click={toggleGrownUp}
    title="Grown-up mode"
    aria-pressed={$grownUpMode}
    aria-label="Grown-up mode"
  >
    ⚙
  </button>
</header>

<main>
  {#if step === 0}
    <Screen0_NewProject on:done={next} />
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

{#if $grownUpMode}
  <div class="grownup" style="max-width:820px;margin:0 auto 40px;">
    <h3>Grown-up mode</h3>
    Step: {step} ({step >= 1 ? STEPS[step - 1] : "New project"})
    {"\n"}Project: {$project ? JSON.stringify($project) : "(none yet)"}
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
