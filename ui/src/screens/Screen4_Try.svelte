<script>
  // Screen 4 — Try it!
  // Record into the mic, send it to the trained model, and show what it heard.
  // Then: Save, "Use on my computer" (export), or "Make it better" (go back).
  // jargon-free.
  import { createEventDispatcher, onDestroy } from 'svelte';
  import { transcribe, exportModel } from '../lib/api.js';
  import { currentRun, grownUpMode } from '../lib/store.js';
  import { t } from '../lib/i18n.js';
  import { focusOnMount } from '../lib/a11y.js';
  import Mascot from '../components/Mascot.svelte';

  const dispatch = createEventDispatcher();

  let recording = false;
  let mediaRecorder = null;
  let chunks = [];
  let heardText = '';
  let busy = false;
  let micError = '';
  let exportNote = '';
  let saved = false;

  onDestroy(() => {
    if (mediaRecorder && recording) mediaRecorder.stop();
  });

  async function startRecording() {
    micError = '';
    heardText = '';
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      chunks = [];
      mediaRecorder = new MediaRecorder(stream);
      mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) chunks.push(e.data);
      };
      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunks, { type: 'audio/webm' });
        await sendForText(blob);
      };
      mediaRecorder.start();
      recording = true;
    } catch {
      micError = "I couldn't use the microphone. Please allow microphone access.";
    }
  }

  function stopRecording() {
    if (mediaRecorder && recording) {
      mediaRecorder.stop();
      recording = false;
    }
  }

  function toggleRecording() {
    recording ? stopRecording() : startRecording();
  }

  async function sendForText(blob) {
    busy = true;
    try {
      const res = await transcribe(blob);
      heardText = res.text || '';
    } catch (e) {
      micError = e.message || "I couldn't understand that one.";
    } finally {
      busy = false;
    }
  }

  function save() {
    // "Try it" results are shown live and on purpose are not stored anywhere —
    // there's no server-side persistence for them, so this is a local-only
    // acknowledgement that the child saw the result.
    saved = true;
  }

  async function useOnMyComputer() {
    exportNote = '';
    const run = $currentRun;
    if (!run?.run_id) {
      exportNote = $t('try.teach_first');
      return;
    }
    busy = true;
    try {
      // CTranslate2 int8 is the offline desktop default (project/docs/DECISIONS.md D-006).
      const res = await exportModel(run.run_id, 'ctranslate2');
      exportNote = res.notes ? res.notes : `Saved as ${res.format} at ${res.path}`;
    } catch (e) {
      exportNote = e.message || "I couldn't get it ready for your computer.";
    } finally {
      busy = false;
    }
  }
</script>

<section class="screen">
  <Mascot mood="cheer" size={100} />
  <h1 tabindex="-1" use:focusOnMount>{$t('try.title')}</h1>
  <p>{$t('try.subtitle')}</p>

  <div class="stack">
    <button
      class="mic"
      class:recording
      on:click={toggleRecording}
      aria-pressed={recording}
      aria-label={recording ? $t('record.stop_recording') : $t('record.start_recording')}
    >
      {recording ? '⏹' : '🎤'}
    </button>
    <span aria-live="polite">{recording ? $t('record.listening') : $t('record.press_to_talk')}</span
    >
  </div>

  {#if busy}
    <p aria-live="polite">{$t('try.thinking')}</p>
  {/if}

  {#if heardText}
    <div class="card heard">
      <h2>{$t('try.heard')}</h2>
      <p class="big-text" aria-live="polite">{heardText}</p>
    </div>
  {/if}

  {#if micError}
    <p class="error">{micError}</p>
  {/if}

  <div class="row">
    <button class="secondary" on:click={save}>
      {saved ? $t('common.saved') : $t('try.save')}
    </button>
    <button on:click={useOnMyComputer} disabled={busy}> {$t('try.use')} </button>
    <button class="ghost" on:click={() => dispatch('again')}> {$t('try.make_better')} </button>
  </div>

  {#if exportNote}
    <p class="note">{exportNote}</p>
  {/if}

  {#if $grownUpMode}
    <div class="grownup">
      <h3>Advanced</h3>
      run: {JSON.stringify($currentRun)}
      {'\n'}heard: {heardText}
    </div>
  {/if}
</section>

<style>
  .big-text {
    font-size: 1.8rem;
    font-weight: 700;
    color: var(--tt-ink);
  }

  .note {
    color: var(--tt-accent-dark);
    font-weight: 700;
  }

  .error {
    color: var(--tt-oops);
    font-weight: 700;
  }
</style>
