<script>
  // Screen 2 — Check the words.
  // For each clip we ask the computer to write down what it heard (a draft),
  // then the child can tap any word to fix it and save. jargon-free.
  import { createEventDispatcher, onMount } from 'svelte';
  import { transcribeDraft } from '../lib/api.js';
  import { grownUpMode } from '../lib/store.js';
  import Mascot from '../components/Mascot.svelte';

  const dispatch = createEventDispatcher();

  // The clip list will eventually come from the backend. For now we keep a
  // small placeholder list so the screen flow is real and testable.
  // TODO(backend): replace with GET of the project's recorded clips.
  let clips = [
    { id: 'clip-1', label: 'Recording 1', text: '', loading: false, saved: false },
    { id: 'clip-2', label: 'Recording 2', text: '', loading: false, saved: false },
  ];

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

  onMount(() => {
    clips.forEach(loadDraft);
  });

  function onEdit(clip, e) {
    clip.text = e.target.value;
    clip.saved = false;
    clips = clips;
  }

  function save(clip) {
    // TODO(backend): persist corrected transcript for this clip.
    clip.saved = true;
    clips = clips;
  }
</script>

<section class="screen">
  <Mascot mood="think" size={90} />
  <h1>Check the words</h1>
  <p>Did the computer hear you right? Tap a box to fix any words.</p>

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
          <button class="secondary" on:click={() => save(clip)}>Save fix</button>
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
      <h3>Grown-up mode</h3>
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
