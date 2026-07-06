<script>
  // Screen 1 — Record.
  // Big mic button (MediaRecorder). When you stop, we send the clip to be
  // checked and show a thumbs up/down. A meter shows "minutes of good audio"
  // from /api/sufficiency. You can also drop in audio files you already have.
  // The "Teach" button only wakes up when there's enough good audio.
  // jargon-free everywhere.
  import { onMount, onDestroy, createEventDispatcher } from 'svelte';
  import {
    analyzeClip,
    sufficiency as fetchSufficiency,
    getPrompts,
    saveCorrection,
    selfTest,
  } from '../lib/api.js';
  import { sufficiency, grownUpMode, project } from '../lib/store.js';
  import { t } from '../lib/i18n.js';
  import { focusOnMount } from '../lib/a11y.js';
  import Mascot from '../components/Mascot.svelte';

  const dispatch = createEventDispatcher();

  // Karaoke lines to read aloud. We fetch real ones from the backend on mount,
  // but keep a few friendly defaults so there's always something to read.
  let prompts = [
    'The big red bus goes fast.',
    'My dog likes to jump and play.',
    'We had pancakes for breakfast.',
    'Look at the bright yellow sun!',
  ];
  let promptIndex = 0;
  $: prompt = prompts[promptIndex % prompts.length];

  function anotherSentence() {
    promptIndex = (promptIndex + 1) % prompts.length;
  }

  let recording = false;
  let mediaRecorder = null;
  let chunks = [];
  // The sentence shown when recording started — becomes that clip's transcript.
  let recordingPrompt = null;
  let lastResult = null; // ClipQuality
  let busy = false;
  let micError = '';
  let dragOver = false;
  let practiceNote = '';

  let pollTimer = null;

  // --- Live "we can hear you" meter (#13) ---------------------------------
  // Client-side WebAudio only: we tap the same getUserMedia stream, read its
  // loudness (RMS) each animation frame, and fill a bar so a child sees they're
  // being heard. No backend call. The fast-moving bar is aria-hidden (per-frame
  // numeric updates spam a screen reader); a separate coarse aria-live status
  // ("Listening…" → "We can hear you!") gives AT users the signal instead.
  let level = 0; // 0..1, smoothed loudness for the bar
  let heardYet = false; // has the level crossed the "we hear you" threshold?
  let audioCtx = null;
  let analyser = null;
  let sourceNode = null;
  let rafId = null;

  function startMeter(stream) {
    try {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      audioCtx = new Ctx();
      sourceNode = audioCtx.createMediaStreamSource(stream);
      analyser = audioCtx.createAnalyser();
      analyser.fftSize = 1024;
      sourceNode.connect(analyser);
      const buf = new Uint8Array(analyser.fftSize);
      heardYet = false;
      const tick = () => {
        analyser.getByteTimeDomainData(buf);
        let sum = 0;
        for (let i = 0; i < buf.length; i++) {
          const v = (buf[i] - 128) / 128;
          sum += v * v;
        }
        const rms = Math.sqrt(sum / buf.length);
        // Scale for visibility and smooth the decay so the bar doesn't flicker.
        level = Math.min(1, Math.max(level * 0.8, rms * 2.5));
        if (!heardYet && rms > 0.05) heardYet = true;
        rafId = requestAnimationFrame(tick);
      };
      tick();
    } catch {
      // The meter is a nicety — if WebAudio isn't available, recording still works.
    }
  }

  function stopMeter() {
    if (rafId) cancelAnimationFrame(rafId);
    rafId = null;
    try {
      sourceNode?.disconnect();
      analyser?.disconnect();
    } catch {
      /* nodes already gone */
    }
    if (audioCtx) {
      audioCtx.close();
      audioCtx = null;
    }
    sourceNode = null;
    analyser = null;
    level = 0;
    heardYet = false;
  }

  async function refreshSufficiency() {
    try {
      const s = await fetchSufficiency();
      sufficiency.set(s);
    } catch {
      // Stay quiet on the meter if the backend isn't up yet.
    }
  }

  async function loadPrompts() {
    try {
      const lang = $project?.language_code || null;
      const res = await getPrompts(lang, 8);
      if (res.prompts && res.prompts.length) {
        prompts = res.prompts;
        promptIndex = 0;
      }
    } catch {
      // Keep the friendly default lines if the backend isn't up yet.
    }
  }

  onMount(() => {
    refreshSufficiency();
    loadPrompts();
    pollTimer = setInterval(refreshSufficiency, 4000);
  });

  onDestroy(() => {
    if (pollTimer) clearInterval(pollTimer);
    if (mediaRecorder && recording) mediaRecorder.stop();
    stopMeter();
  });

  async function startRecording() {
    micError = '';
    lastResult = null;
    // Remember the sentence the child is reading right now; we save it as this
    // clip's words once it's recorded and checked.
    recordingPrompt = prompt;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      chunks = [];
      mediaRecorder = new MediaRecorder(stream);
      mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) chunks.push(e.data);
      };
      mediaRecorder.onstop = async () => {
        stopMeter();
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunks, { type: 'audio/webm' });
        await handleClip(blob, recordingPrompt);
      };
      mediaRecorder.start();
      startMeter(stream);
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

  // `promptText` is the karaoke line for a *recorded* clip (its words). For
  // dropped-in audio files we pass null, since they aren't reading our sentence.
  async function handleClip(blobOrFile, promptText = null) {
    busy = true;
    lastResult = null;
    try {
      lastResult = await analyzeClip(blobOrFile);
      // The sentence the child read becomes the clip's words, so they rarely
      // have to fix anything on the next screen.
      if (promptText && lastResult.clip_id != null) {
        try {
          await saveCorrection(lastResult.clip_id, promptText);
        } catch {
          // Not fatal — they can still fix the words on the Check screen.
        }
      }
      anotherSentence(); // move the karaoke line along
      await refreshSufficiency();
    } catch (e) {
      micError = e.message || "I couldn't listen to that one.";
    } finally {
      busy = false;
    }
  }

  async function addPracticeSet() {
    practiceNote = '';
    busy = true;
    try {
      const res = await selfTest();
      practiceNote = res.message || 'Added a few practice sounds so you can try Teach!';
      await refreshSufficiency();
    } catch (e) {
      practiceNote = e.message || "I couldn't make a practice set.";
    } finally {
      busy = false;
    }
  }

  // --- Drag and drop / pick existing audio --------------------------------
  let fileInput = null;

  function onDrop(e) {
    e.preventDefault();
    dragOver = false;
    const file = e.dataTransfer?.files?.[0];
    if (file) handleClip(file, null);
  }

  function onPick(e) {
    const file = e.target.files?.[0];
    if (file) handleClip(file, null);
    e.target.value = ''; // let the same file be picked again
  }

  // The drop zone doubles as a real button: click or Enter/Space opens the file
  // picker, so it's fully usable without a mouse or drag (#37).
  function activateDrop(e) {
    if (e.type === 'keydown') {
      if (e.key !== 'Enter' && e.key !== ' ') return;
      e.preventDefault();
    }
    fileInput?.click();
  }

  $: s = $sufficiency;
  $: readyToTeach = s && s.status === 'ready';
  $: pct = s ? Math.round((s.fraction || 0) * 100) : 0;
</script>

<section class="screen">
  <Mascot mood={recording ? 'think' : 'happy'} size={90} />
  <h1 tabindex="-1" use:focusOnMount>{$t('record.title')}</h1>
  <p>{$t('record.read_prompt')}</p>

  <!-- Karaoke prompt line: the sentence to read aloud. -->
  <div class="card prompt">{prompt}</div>
  <button class="ghost" on:click={anotherSentence}>{$t('record.another')}</button>

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
    <span aria-live="polite">
      {recording
        ? heardYet
          ? $t('record.hearing')
          : $t('record.listening')
        : $t('record.press_to_talk')}
    </span>

    <!-- Live loudness bar. Decorative + fast-updating, so hidden from screen
         readers — the coarse status above carries the same signal for AT. -->
    {#if recording}
      <div class="level" aria-hidden="true">
        <div class="level-fill" style="width:{Math.round(level * 100)}%"></div>
      </div>
    {/if}
  </div>

  {#if busy}
    <p>{$t('record.checking')}</p>
  {:else if lastResult}
    <div class="card result">
      {#if lastResult.ok}
        <span class="thumb up">👍</span>
        <p>{$t('record.great')}</p>
      {:else}
        <span class="thumb down">👎</span>
        <p>{$t('record.try_again')}</p>
        {#if lastResult.issues && lastResult.issues.length}
          <ul class="issues">
            {#each lastResult.issues as issue}
              <li>{issue}</li>
            {/each}
          </ul>
        {/if}
      {/if}
    </div>
  {/if}

  {#if micError}
    <p class="error">{micError}</p>
  {/if}

  <!-- Drag-and-drop zone for audio you already have -->
  <div
    class="drop"
    class:over={dragOver}
    on:dragover|preventDefault={() => (dragOver = true)}
    on:dragleave={() => (dragOver = false)}
    on:drop={onDrop}
    on:click={activateDrop}
    on:keydown={activateDrop}
    role="button"
    tabindex="0"
    aria-label={$t('record.drop_label')}
  >
    {$t('record.drop')}
  </div>
  <input
    class="visually-hidden"
    type="file"
    accept="audio/*"
    tabindex="-1"
    aria-hidden="true"
    bind:this={fileInput}
    on:change={onPick}
  />

  <!-- "Minutes of good audio" meter -->
  <div class="card">
    <h2>{$t('record.how_much')}</h2>
    <div class="meter"><div class="fill" style="width:{pct}%"></div></div>
    {#if s}
      <p>
        {s.good_minutes?.toFixed?.(1) ?? s.good_minutes} of
        {s.target_minutes} good minutes
      </p>
      {#each s.messages || [] as m}
        <p class="hint">{m}</p>
      {/each}
    {:else}
      <p class="hint">{$t('record.start_hint')}</p>
    {/if}
  </div>

  <!-- No microphone yet? Add a few ready-made sounds so you can still try. -->
  <div class="card practice">
    <p class="hint">{$t('record.no_mic')}</p>
    <button class="secondary" disabled={busy} on:click={addPracticeSet}>
      {$t('record.practice')}
    </button>
    {#if practiceNote}
      <p class="hint">{practiceNote}</p>
    {/if}
  </div>

  <button class="big" disabled={!readyToTeach} on:click={() => dispatch('next')}>
    {readyToTeach ? $t('record.ready_next') : $t('record.not_ready')}
  </button>

  {#if $grownUpMode}
    <div class="grownup">
      <h3>Advanced</h3>
      sufficiency: {JSON.stringify(s)}
      {'\n'}last clip: {JSON.stringify(lastResult)}
    </div>
  {/if}
</section>

<style>
  .prompt {
    font-size: 1.8rem;
    font-weight: 700;
    color: var(--tt-primary-dark);
  }

  /* Live loudness bar — a fast, non-lagging fill (the shared .meter uses a slow
     0.4s width transition meant for progress, which would smear a live signal). */
  .level {
    width: 220px;
    max-width: 80%;
    height: 14px;
    background: #ececf0;
    border-radius: 999px;
    overflow: hidden;
  }

  .level-fill {
    height: 100%;
    width: 0%;
    background: linear-gradient(90deg, var(--tt-happy), var(--tt-sun), var(--tt-oops));
    border-radius: 999px;
    transition: width 0.06s linear;
  }

  .result {
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .issues {
    text-align: left;
    color: var(--tt-oops);
  }

  .drop {
    border: 4px dashed #c6ccd6;
    border-radius: var(--tt-radius);
    padding: 22px;
    color: var(--tt-ink-soft);
    margin: 16px 0;
    cursor: pointer;
  }

  .drop.over {
    border-color: var(--tt-accent);
    background: #e9faf6;
  }

  .visually-hidden {
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

  .hint {
    color: var(--tt-ink-soft);
    font-size: 1rem;
  }

  .error {
    color: var(--tt-oops);
    font-weight: 700;
  }
</style>
