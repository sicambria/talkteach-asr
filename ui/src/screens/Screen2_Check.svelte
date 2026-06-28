<script>
  // Screen 2 — Check the words.
  // For each clip we ask the computer to write down what it heard (a draft),
  // then the child can tap any word to fix it and save. jargon-free.
  import { createEventDispatcher, onMount } from 'svelte';
  import { listClips, transcribeDraft, saveCorrection } from '../lib/api.js';
  import { grownUpMode } from '../lib/store.js';
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
        label: `Recording ${i + 1}`,
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
  <h1>Check the words</h1>
  <p>Did the computer hear you right? Tap a box to fix any words.</p>

  {#if loadingList}
    <p>Finding your recordings…</p>
  {:else if clips.length === 0}
    <div class="card">
      <p>No recordings yet — go back and record some!</p>
      <button class="big" on:click={() => dispatch('back')}>◀ Back to recording</button>
    </div>
  {/if}

  {#each clips as clip (clip.id)}
    <div class="card clip">
      <div class="clip-head">
        <strong>{clip.label}</strong>
        {#if clip.saved}<span class="chip">Saved ✓</span>{/if}
      </div>

      {#if clip.loading}
        <p>Listening and writing it down…</p>
      {:else}
        <input
          type="text"
          value={clip.text}
          placeholder="(no words yet)"
          on:input={(e) => onEdit(clip, e)}
          aria-label="Words for {clip.label}"
        />
        <div class="row">
          <button class="secondary" disabled={clip.saving} on:click={() => save(clip)}>
            {clip.saving ? 'Saving…' : 'Save fix'}
          </button>
          <button class="ghost" on:click={() => loadDraft(clip)}>Try again</button>
        </div>
      {/if}
    </div>
  {/each}

  {#if errorMsg}
    <p class="error">{errorMsg}</p>
  {/if}

  <div class="row">
    <button class="ghost" on:click={() => dispatch('back')}>◀ Back</button>
    <button class="big" on:click={() => dispatch('next')}> Next: Teach it! ▶ </button>
  </div>

  {#if $grownUpMode}
    <div class="grownup">
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
