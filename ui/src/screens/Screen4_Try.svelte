<script>
  // Screen 4 — Try it!
  // Record into the mic, send it to the trained model, and show what it heard.
  // Then: Save, "Use on my computer" (export), or "Make it better" (go back).
  // jargon-free.
  import { createEventDispatcher, onDestroy } from "svelte";
  import { transcribe, exportModel } from "../lib/api.js";
  import { currentRun, grownUpMode } from "../lib/store.js";
  import Mascot from "../components/Mascot.svelte";

  const dispatch = createEventDispatcher();

  let recording = false;
  let mediaRecorder = null;
  let chunks = [];
  let heardText = "";
  let busy = false;
  let micError = "";
  let exportNote = "";
  let saved = false;

  onDestroy(() => {
    if (mediaRecorder && recording) mediaRecorder.stop();
  });

  async function startRecording() {
    micError = "";
    heardText = "";
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
        await sendForText(blob);
      };
      mediaRecorder.start();
      recording = true;
    } catch (e) {
      micError = "I couldn't use the microphone. Can a grown-up help?";
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
      heardText = res.text || "";
    } catch (e) {
      micError = e.message || "I couldn't understand that one.";
    } finally {
      busy = false;
    }
  }

  function save() {
    // TODO(backend): persist this try result if needed.
    saved = true;
  }

  async function useOnMyComputer() {
    exportNote = "";
    const run = $currentRun;
    if (!run?.run_id) {
      exportNote = "Teach the computer first, then you can use it here.";
      return;
    }
    busy = true;
    try {
      const res = await exportModel(run.run_id, "onnx");
      exportNote = res.notes
        ? res.notes
        : `Saved as ${res.format} at ${res.path}`;
    } catch (e) {
      exportNote = e.message || "I couldn't get it ready for your computer.";
    } finally {
      busy = false;
    }
  }
</script>

<section class="screen">
  <Mascot mood="cheer" size={100} />
  <h1>Try it!</h1>
  <p>Say something and see if the computer understands you now.</p>

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
    <p>Thinking…</p>
  {/if}

  {#if heardText}
    <div class="card heard">
      <h2>It heard:</h2>
      <p class="big-text">{heardText}</p>
    </div>
  {/if}

  {#if micError}
    <p class="error">{micError}</p>
  {/if}

  <div class="row">
    <button class="secondary" on:click={save}>
      {saved ? "Saved ✓" : "💾 Save"}
    </button>
    <button on:click={useOnMyComputer} disabled={busy}>
      🖥 Use on my computer
    </button>
    <button class="ghost" on:click={() => dispatch("again")}>
      🔁 Make it better
    </button>
  </div>

  {#if exportNote}
    <p class="note">{exportNote}</p>
  {/if}

  {#if $grownUpMode}
    <div class="grownup">
      <h3>Grown-up mode</h3>
      run: {JSON.stringify($currentRun)}
      {"\n"}heard: {heardText}
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
