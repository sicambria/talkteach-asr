<script>
  // Screen 0 — "What should we teach?"
  // Name the project, pick a language (or let the computer figure it out),
  // then start. jargon-free everywhere.
  import { createEventDispatcher } from 'svelte';
  import { createProject } from '../lib/api.js';
  import { project, grownUpMode } from '../lib/store.js';
  import Mascot from '../components/Mascot.svelte';

  const dispatch = createEventDispatcher();

  // A short, friendly list of common languages with flags.
  const LANGUAGES = [
    { code: 'en', flag: '🇬🇧', label: 'English' },
    { code: 'es', flag: '🇪🇸', label: 'Spanish' },
    { code: 'fr', flag: '🇫🇷', label: 'French' },
    { code: 'de', flag: '🇩🇪', label: 'German' },
    { code: 'hu', flag: '🇭🇺', label: 'Hungarian' },
    { code: 'it', flag: '🇮🇹', label: 'Italian' },
    { code: 'ro', flag: '🇷🇴', label: 'Romanian' },
  ];

  let name = '';
  let languageCode = 'en';
  let letItFigureOut = false; // when true we send null
  let busy = false;
  let errorMsg = '';

  $: canStart = name.trim().length > 0 && !busy;

  async function start() {
    errorMsg = '';
    busy = true;
    try {
      const code = letItFigureOut ? null : languageCode;
      const res = await createProject(name.trim(), code);
      project.set({
        project_id: res.project_id,
        name: name.trim(),
        language_code: code,
      });
      dispatch('done');
    } catch (e) {
      errorMsg = e.message || "Something went wrong. Let's try again.";
    } finally {
      busy = false;
    }
  }
</script>

<section class="screen">
  <Mascot mood="wave" size={110} />
  <h1>What should we teach?</h1>
  <p>Give your project a fun name. You can change it later.</p>

  <div class="card stack">
    <input
      type="text"
      placeholder="Like: My Robot Friend"
      bind:value={name}
      on:keydown={(e) => e.key === 'Enter' && canStart && start()}
      aria-label="Project name"
    />

    <label class="figure-out">
      <input type="checkbox" bind:checked={letItFigureOut} />
      Let it figure out the language by itself
    </label>

    {#if !letItFigureOut}
      <div class="row langs" role="group" aria-label="Pick a language">
        {#each LANGUAGES as lang}
          <button
            class="lang"
            class:picked={languageCode === lang.code}
            on:click={() => (languageCode = lang.code)}
            type="button"
          >
            <span class="flag">{lang.flag}</span>
            <span>{lang.label}</span>
          </button>
        {/each}
      </div>
    {/if}
  </div>

  {#if errorMsg}
    <p class="error">{errorMsg}</p>
  {/if}

  <button class="big" disabled={!canStart} on:click={start}>
    {busy ? 'Starting…' : "Let's go! ▶"}
  </button>

  {#if $grownUpMode}
    <div class="grownup">
      <h3>Grown-up mode</h3>
      POST /api/project {JSON.stringify({
        name: name.trim(),
        language_code: letItFigureOut ? null : languageCode,
      })}
    </div>
  {/if}
</section>

<style>
  .figure-out {
    font-size: 1.1rem;
    display: flex;
    align-items: center;
    gap: 10px;
    color: var(--tt-ink-soft);
  }

  .figure-out input {
    width: 26px;
    height: 26px;
  }

  .langs {
    margin-top: 8px;
  }

  .lang {
    background: #f1f2f6;
    color: var(--tt-ink);
    box-shadow: none;
    border: 3px solid transparent;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    font-size: 1rem;
    padding: 12px 16px;
    min-height: 80px;
  }

  .lang .flag {
    font-size: 2rem;
  }

  .lang.picked {
    border-color: var(--tt-primary);
    background: var(--tt-sun);
  }

  .error {
    color: var(--tt-oops);
    font-weight: 700;
  }
</style>
