<script>
  // Screen 4 — Try it!
  // Record into the mic, send it to the trained model, and show what it heard.
  // Then: Save, "Use on my computer" (export), or "Make it better" (go back).
  // jargon-free.
  import { createEventDispatcher, onDestroy, onMount } from 'svelte';
  import { transcribe, exportModel, exportFormats } from '../lib/api.js';
  import { currentRun, advancedMode } from '../lib/store.js';
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

  // Captions (#48): the transcribe response carries ready-to-save SRT/VTT strings
  // and per-utterance segments; .txt is the plain text. Easy mode gets one "Save
  // captions" (.srt) button; Advanced gets a format picker.
  let captions = { srt: '', vtt: '', txt: '' };
  let capFmt = 'srt';
  let capSaved = false;

  // Export format picker (#57). Easy keeps the one-tap ctranslate2 default; Advanced
  // shows every target with a real-vs-scaffold hint.
  let formats = [];
  let exportFmt = 'ctranslate2';

  onMount(async () => {
    try {
      const res = await exportFormats();
      formats = res.formats || [];
      exportFmt = res.default || 'ctranslate2';
    } catch {
      // Picker just falls back to the single default button if this fails.
    }
  });

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
    capSaved = false;
    try {
      const res = await transcribe(blob);
      heardText = res.text || '';
      captions = { srt: res.srt || '', vtt: res.vtt || '', txt: res.text || '' };
    } catch (e) {
      micError = e.message || "I couldn't understand that one.";
    } finally {
      busy = false;
    }
  }

  function downloadCaptions() {
    const body = captions[capFmt] || '';
    if (!body) return;
    const mime = capFmt === 'vtt' ? 'text/vtt' : 'text/plain';
    const blob = new Blob([body], { type: `${mime};charset=utf-8` });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `captions.${capFmt}`;
    a.click();
    URL.revokeObjectURL(a.href);
    capSaved = true;
  }

  function save() {
    // "Try it" results are shown live and on purpose are not stored anywhere —
    // there's no server-side persistence for them, so this is a local-only
    // acknowledgement that the user saw the result.
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
      // Easy mode uses the CTranslate2 int8 offline default (DECISIONS.md D-006);
      // Advanced mode can pick another target via the format select.
      const fmt = $advancedMode ? exportFmt : 'ctranslate2';
      const res = await exportModel(run.run_id, fmt);
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
      {#if captions.srt}
        <button class="ghost caps" on:click={downloadCaptions}>
          {capSaved ? $t('try.captions_saved') : $t('try.save_captions')}
        </button>
      {/if}
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

  {#if $advancedMode}
    <div class="advanced">
      <h3>Advanced</h3>

      <label class="adv-field">
        <span>Export format</span>
        <select bind:value={exportFmt}>
          {#each formats as f}
            <option value={f.fmt}>{f.label}{f.scaffold ? ' — scaffold' : ''}</option>
          {/each}
        </select>
      </label>
      {#if formats.find((f) => f.fmt === exportFmt && f.scaffold)}
        <p class="adv-hint">
          This target is a documented dry-run scaffold, not a runnable export yet.
        </p>
      {/if}

      {#if captions.srt}
        <label class="adv-field">
          <span>Caption format</span>
          <select bind:value={capFmt}>
            <option value="srt">SubRip (.srt)</option>
            <option value="vtt">WebVTT (.vtt)</option>
            <option value="txt">Plain text (.txt)</option>
          </select>
        </label>
      {/if}

      <p class="adv-meta">run: {JSON.stringify($currentRun)}</p>
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

  .caps {
    margin-top: 10px;
    font-size: 0.95rem;
  }

  .adv-field {
    display: flex;
    align-items: center;
    gap: 10px;
    justify-content: space-between;
    margin: 8px 0;
  }

  .adv-field span {
    font-weight: 700;
  }

  .adv-field select {
    flex: 1;
    max-width: 60%;
  }

  .adv-hint {
    font-size: 0.85rem;
    color: var(--tt-ink-soft);
    margin: 0 0 8px;
  }

  .adv-meta {
    font-size: 0.8rem;
    color: var(--tt-ink-soft);
    word-break: break-all;
  }
</style>
