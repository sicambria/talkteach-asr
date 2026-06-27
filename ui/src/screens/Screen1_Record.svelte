<script>
  // Screen 1 — Record.
  // Big mic button (MediaRecorder). When you stop, we send the clip to be
  // checked and show a thumbs up/down. A meter shows "minutes of good audio"
  // from /api/sufficiency. You can also drop in audio files you already have.
  // The "Teach" button only wakes up when there's enough good audio.
  // jargon-free everywhere.
  import { onMount, onDestroy, createEventDispatcher } from "svelte";
  import { analyzeClip, sufficiency as fetchSufficiency } from "../lib/api.js";
  import { sufficiency, grownUpMode } from "../lib/store.js";
  import Mascot from "../components/Mascot.svelte";

  const dispatch = createEventDispatcher();

  // A friendly placeholder line for "karaoke" prompt reading.
  const PROMPTS = [
    "The big red bus goes fast.",
    "My dog likes to jump and play.",
    "We had pancakes for breakfast.",
    "Look at the bright yellow sun!",
  ];
  let promptIndex = 0;
  $: prompt = PROMPTS[promptIndex % PROMPTS.length];

  let recording = false;
  let mediaRecorder = null;
  let chunks = [];
  let lastResult = null; // ClipQuality
  let busy = false;
  let micError = "";
  let dragOver = false;

  let pollTimer = null;

  async function refreshSufficiency() {
    try {
      const s = await fetchSufficiency();
      sufficiency.set(s);
    } catch {
      // Stay quiet on the meter if the backend isn't up yet.
    }
  }

  onMount(() => {
    refreshSufficiency();
    pollTimer = setInterval(refreshSufficiency, 4000);
  });

  onDestroy(() => {
    if (pollTimer) clearInterval(pollTimer);
    if (mediaRecorder && recording) mediaRecorder.stop();
  });

  async function startRecording() {
    micError = "";
    lastResult = null;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      chunks = [];
      mediaRecorder = new MediaRecorder(stream);
      mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) chunks.push(e.data);
      };
      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunks, { type: "audio/webm" });
        await handleClip(blob);
      };
      mediaRecorder.start();
      recording = true;
    } catch (e) {
      micError = "I couldn't use the microphone. Can a grown-up help turn it on?";
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

  async function handleClip(blobOrFile) {
    busy = true;
    lastResult = null;
    try {
      lastResult = await analyzeClip(blobOrFile);
      promptIndex += 1; // move the karaoke line along
      await refreshSufficiency();
    } catch (e) {
      micError = e.message || "I couldn't listen to that one.";
    } finally {
      busy = false;
    }
  }

  // --- Drag and drop existing audio ---------------------------------------
  function onDrop(e) {
    e.preventDefault();
    dragOver = false;
    const file = e.dataTransfer?.files?.[0];
    if (file) handleClip(file);
  }

  $: s = $sufficiency;
  $: readyToTeach = s && s.status === "ready";
  $: pct = s ? Math.round((s.fraction || 0) * 100) : 0;
</script>

<section class="screen">
  <Mascot mood={recording ? "think" : "happy"} size={90} />
  <h1>Let's record!</h1>
  <p>Read this out loud, then press the big button.</p>

  <!-- Karaoke prompt line placeholder -->
  <div class="card prompt">{prompt}</div>

  <div class="stack">
    <button
      class="mic"
      class:recording
      on:click={toggleRecording}
      aria-pressed={recording}
      aria-label={recording ? "Stop recording" : "Start recording"}
    >
      {recording ? "⏹" : "🎤"}
    </button>
    <span>{recording ? "Listening… press to stop" : "Press to talk"}</span>
  </div>

  {#if busy}
    <p>Checking your recording…</p>
  {:else if lastResult}
    <div class="card result">
      {#if lastResult.ok}
        <span class="thumb up">👍</span>
        <p>Great recording!</p>
      {:else}
        <span class="thumb down">👎</span>
        <p>Let's try that one again.</p>
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
    role="button"
    tabindex="0"
    aria-label="Drop audio files here"
  >
    📁 Drag sound files here too
  </div>

  <!-- "Minutes of good audio" meter -->
  <div class="card">
    <h2>How much have we recorded?</h2>
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
      <p class="hint">Press the mic to start filling this up!</p>
    {/if}
  </div>

  <button
    class="big"
    disabled={!readyToTeach}
    on:click={() => dispatch("next")}
  >
    {readyToTeach ? "Next: Check the words ▶" : "Record a bit more first…"}
  </button>

  {#if $grownUpMode}
    <div class="grownup">
      <h3>Grown-up mode</h3>
      sufficiency: {JSON.stringify(s)}
      {"\n"}last clip: {JSON.stringify(lastResult)}
    </div>
  {/if}
</section>

<style>
  .prompt {
    font-size: 1.8rem;
    font-weight: 700;
    color: var(--tt-primary-dark);
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

  .hint {
    color: var(--tt-ink-soft);
    font-size: 1rem;
  }

  .error {
    color: var(--tt-oops);
    font-weight: 700;
  }
</style>
