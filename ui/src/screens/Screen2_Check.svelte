<script>
  // Screen 2 — Check the words.
  // For each clip we ask the computer to write down what it heard (a draft),
  // then the user can tap any word to fix it and save. jargon-free.
  import { createEventDispatcher, onMount } from 'svelte';
  import { listClips, transcribeDraft, saveCorrection } from '../lib/api.js';
  import { advancedMode } from '../lib/store.js';
  import { t } from '../lib/i18n.js';
  import { focusOnMount } from '../lib/a11y.js';
  import Mascot from '../components/Mascot.svelte';

  const dispatch = createEventDispatcher();

  // The recordings come from the backend. Each gets a few client-only helper
  // fields (label, loading, saving, saved) so the UI can show its state.
  let clips = [];
  let loadingList = true;
  let errorMsg = '';

  async function loadDraft(clip) {
    clip.loading = true;
    clips = clips; // poke Svelte reactivity
    try {
      const res = await transcribeDraft(clip.id);
      clip.text = res.text || '';
    } catch (e) {
      errorMsg = e.message || "I couldn't write the words for that clip.";
    } finally {
      clip.loading = false;
      clips = clips;
    }
  }

  async function loadClips() {
    loadingList = true;
    errorMsg = '';
    try {
      const res = await listClips();
      clips = (res.clips || []).map((c, i) => ({
        id: c.id,
        label: `${$t('check.recording')} ${i + 1}`,
        text: c.transcript || '',
        loading: false,
        saving: false,
        // A clip that already had words saved counts as "saved".
        saved: Boolean(c.transcript),
      }));
      // Only ask the computer to write words for clips that don't have any yet.
      clips.filter((c) => !c.text).forEach(loadDraft);
    } catch (e) {
      errorMsg = e.message || "I couldn't find your recordings.";
    } finally {
      loadingList = false;
    }
  }

  onMount(loadClips);

  function onEdit(clip, e) {
    clip.text = e.target.value;
    clip.saved = false;
    clips = clips;
  }

  async function save(clip) {
    clip.saving = true;
    clips = clips;
    try {
      await saveCorrection(clip.id, clip.text);
      clip.saved = true;
    } catch (e) {
      errorMsg = e.message || "I couldn't save your fix.";
    } finally {
      clip.saving = false;
      clips = clips;
    }
  }
</script>

<section class="screen">
  <Mascot mood="think" size={90} />
  <h1 tabindex="-1" use:focusOnMount>{$t('check.title')}</h1>
  <p>{$t('check.subtitle')}</p>

  {#if loadingList}
    <p>{$t('check.finding')}</p>
  {:else if clips.length === 0}
    <div class="card">
      <p>{$t('check.none')}</p>
      <button class="big" on:click={() => dispatch('back')}>{$t('check.back_record')}</button>
    </div>
  {/if}

  {#each clips as clip (clip.id)}
    <div class="card clip">
      <div class="clip-head">
        <strong>{clip.label}</strong>
        {#if clip.saved}<span class="chip" aria-live="polite">{$t('common.saved')}</span>{/if}
      </div>

      {#if clip.loading}
        <p>{$t('check.writing')}</p>
      {:else}
        <input
          type="text"
          value={clip.text}
          placeholder={$t('check.no_words')}
          on:input={(e) => onEdit(clip, e)}
          aria-label="{$t('check.words_for')} {clip.label}"
        />
        <div class="row">
          <button class="secondary" disabled={clip.saving} on:click={() => save(clip)}>
            {clip.saving ? $t('check.saving') : $t('check.save_fix')}
          </button>
          <button class="ghost" on:click={() => loadDraft(clip)}>{$t('check.try_again')}</button>
        </div>
      {/if}
    </div>
  {/each}

  {#if errorMsg}
    <p class="error">{errorMsg}</p>
  {/if}

  <div class="row">
    <button class="ghost" on:click={() => dispatch('back')}>{$t('common.back')}</button>
    <button class="big" on:click={() => dispatch('next')}> {$t('check.next')} </button>
  </div>

  {#if $advancedMode}
    <div class="advanced">
      <h3>Advanced</h3>
      clips: {JSON.stringify(clips)}
    </div>
  {/if}
</section>

<style>
  .clip-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
  }

  .error {
    color: var(--tt-oops);
    font-weight: 700;
  }
</style>
