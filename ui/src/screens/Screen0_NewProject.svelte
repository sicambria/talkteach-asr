<script>
  // Screen 0 — "What should we teach?"
  // Name the project, pick a language (or let the computer figure it out),
  // then start. jargon-free everywhere.
  import { createEventDispatcher, onMount } from 'svelte';
  import { createProject, getLanguages } from '../lib/api.js';
  import { project, advancedMode } from '../lib/store.js';
  import { t } from '../lib/i18n.js';
  import { focusOnMount } from '../lib/a11y.js';
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

  // The full ~99-language set (Whisper) loaded from the backend, so the picker
  // isn't limited to the friendly quick-list above. Languages outside this set
  // are still trainable (the director switches to wav2vec2/XLS-R).
  let allLanguages = []; // [{ code, name }]
  let langQuery = ''; // text typed into the search box

  onMount(async () => {
    try {
      const res = await getLanguages();
      allLanguages = res.languages || [];
    } catch {
      /* offline / browser preview: the quick-picks below still work */
    }
  });

  // Friendly name for the currently-selected code (falls back to the code).
  $: selectedName =
    allLanguages.find((l) => l.code === languageCode)?.name ||
    LANGUAGES.find((l) => l.code === languageCode)?.label ||
    languageCode;

  // Resolve a typed "Name (code)" / name / code from the search box into a code.
  function applyQuery() {
    const q = langQuery.trim().toLowerCase();
    if (!q) return;
    const m = allLanguages.find(
      (l) =>
        `${l.name} (${l.code})`.toLowerCase() === q ||
        l.name.toLowerCase() === q ||
        l.code.toLowerCase() === q
    );
    if (m) languageCode = m.code;
  }

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
      errorMsg = e.message || $t('newproject.error');
    } finally {
      busy = false;
    }
  }
</script>

<section class="screen">
  <Mascot mood="wave" size={110} />
  <h1 tabindex="-1" use:focusOnMount>{$t('newproject.title')}</h1>
  <p>{$t('newproject.subtitle')}</p>

  <div class="card stack">
    <input
      type="text"
      placeholder={$t('newproject.name_placeholder')}
      bind:value={name}
      on:keydown={(e) => e.key === 'Enter' && canStart && start()}
      aria-label={$t('newproject.name_label')}
    />

    <label class="figure-out">
      <input type="checkbox" bind:checked={letItFigureOut} />
      {$t('newproject.figure_out')}
    </label>

    {#if !letItFigureOut}
      <div class="row langs" role="group" aria-label={$t('newproject.pick_language')}>
        {#each LANGUAGES as lang}
          <button
            class="lang"
            class:picked={languageCode === lang.code}
            on:click={() => {
              languageCode = lang.code;
              langQuery = '';
            }}
            type="button"
          >
            <span class="flag">{lang.flag}</span>
            <span>{lang.label}</span>
          </button>
        {/each}
      </div>

      {#if allLanguages.length}
        <label class="more-langs">
          <span>{$t('newproject.search_more')}</span>
          <input
            list="all-languages"
            bind:value={langQuery}
            on:change={applyQuery}
            on:input={applyQuery}
            placeholder={$t('newproject.search_placeholder')}
            aria-label={$t('newproject.search_label')}
          />
          <datalist id="all-languages">
            {#each allLanguages as l}
              <option value={`${l.name} (${l.code})`}></option>
            {/each}
          </datalist>
        </label>
        <p class="chosen">{$t('newproject.teaching_in')} <strong>{selectedName}</strong></p>
      {/if}
    {/if}
  </div>

  {#if errorMsg}
    <p class="error">{errorMsg}</p>
  {/if}

  <button class="big" disabled={!canStart} on:click={start}>
    {busy ? $t('newproject.starting') : $t('newproject.go')}
  </button>

  {#if $advancedMode}
    <div class="advanced">
      <h3>Advanced</h3>
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

  .more-langs {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-top: 10px;
    font-size: 1rem;
    color: var(--tt-ink-soft);
  }

  .chosen {
    margin-top: 4px;
    font-size: 1.05rem;
    color: var(--tt-ink-soft);
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
