// Thin, typed client for the TalkTeach FastAPI backend.
// Every function returns parsed JSON and throws an Error with a friendly,
// jargon-free message when something goes wrong.
//
// The Python server is being built in parallel; these match the agreed
// contract and will "just work" once it is running on :8756.
import { API_BASE } from "./constants.js";

/**
 * Turn a fetch Response into JSON, or throw a kid-friendly Error.
 * @param {Response} res
 * @param {string} friendly - what to say if it failed
 */
async function unwrap(res, friendly) {
  if (!res.ok) {
    // Try to pull a helpful detail out of the body, but never show raw jargon.
    let detail = "";
    try {
      const body = await res.json();
      detail = body && (body.detail || body.message) ? `: ${body.detail || body.message}` : "";
    } catch {
      /* ignore non-JSON error bodies */
    }
    throw new Error(`${friendly}${detail}`);
  }
  // Some endpoints (rare) may return empty bodies; guard against that.
  const text = await res.text();
  return text ? JSON.parse(text) : {};
}

function url(path) {
  return `${API_BASE}${path}`;
}

// --- Health -----------------------------------------------------------------

/** GET /api/health -> { ... } */
export async function health() {
  const res = await fetch(url("/api/health"));
  return unwrap(res, "I can't reach the helper program. Is it turned on?");
}

// --- Project ----------------------------------------------------------------

/**
 * POST /api/project
 * @param {string} name
 * @param {string|null} languageCode - null means "let it figure out"
 * @returns {Promise<{project_id: string}>}
 */
export async function createProject(name, languageCode = null) {
  const res = await fetch(url("/api/project"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, language_code: languageCode }),
  });
  return unwrap(res, "I couldn't start your project");
}

// --- Preflight / "Is everything ready?" -------------------------------------

/**
 * GET /api/preflight
 * @returns {Promise<{results: Array<{name,status,detail,remedy}>, ok: boolean, can_train: boolean, summary: string}>}
 */
export async function preflight() {
  const res = await fetch(url("/api/preflight"));
  return unwrap(res, "I couldn't check if everything is ready");
}

// --- Clip quality -----------------------------------------------------------

/**
 * POST /api/clips/analyze (multipart audio OR { path }).
 * Pass a Blob/File to upload it, or a string path that the backend can read.
 * @param {Blob|File|string} audioOrPath
 * @returns {Promise<{ok: boolean, issues: string[], duration_s: number}>}
 */
export async function analyzeClip(audioOrPath) {
  let res;
  if (typeof audioOrPath === "string") {
    res = await fetch(url("/api/clips/analyze"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: audioOrPath }),
    });
  } else {
    const form = new FormData();
    form.append("audio", audioOrPath, audioOrPath.name || "clip.webm");
    res = await fetch(url("/api/clips/analyze"), { method: "POST", body: form });
  }
  return unwrap(res, "I couldn't listen to that recording");
}

// --- Sufficiency / "minutes of good audio" ----------------------------------

/**
 * GET /api/sufficiency
 * @returns {Promise<{status:"ready"|"blocked", good_minutes:number, target_minutes:number, fraction:number, messages:string[]}>}
 */
export async function sufficiency() {
  const res = await fetch(url("/api/sufficiency"));
  return unwrap(res, "I couldn't check how much we've recorded");
}

// --- Draft transcript -------------------------------------------------------

/**
 * POST /api/transcribe/draft
 * @param {string} clipId
 * @returns {Promise<{text: string}>}
 */
export async function transcribeDraft(clipId) {
  const res = await fetch(url("/api/transcribe/draft"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ clip_id: clipId }),
  });
  return unwrap(res, "I couldn't write down the words for that clip");
}

// --- Training ---------------------------------------------------------------

/**
 * POST /api/train -> { run_id }
 * @returns {Promise<{run_id: string}>}
 */
export async function startTraining() {
  const res = await fetch(url("/api/train"), { method: "POST" });
  return unwrap(res, "I couldn't start teaching the computer");
}

/**
 * GET /api/train/{run_id}
 * @param {string} runId
 * @returns {Promise<{epoch:number,total_epochs:number,fraction:number,smartness:number,message:string,done:boolean,failed:boolean}>}
 */
export async function trainProgress(runId) {
  const res = await fetch(url(`/api/train/${encodeURIComponent(runId)}`));
  return unwrap(res, "I lost track of how the teaching is going");
}

// --- The "Try it" mic -------------------------------------------------------

/**
 * POST /api/transcribe (multipart audio) -> { text }
 * @param {Blob|File} audio
 * @returns {Promise<{text: string}>}
 */
export async function transcribe(audio) {
  const form = new FormData();
  form.append("audio", audio, audio.name || "try.webm");
  const res = await fetch(url("/api/transcribe"), { method: "POST", body: form });
  return unwrap(res, "I couldn't understand that recording");
}

// --- Export -----------------------------------------------------------------

/**
 * POST /api/export
 * @param {string} runId
 * @param {string} fmt
 * @returns {Promise<{format: string, path: string, notes: string}>}
 */
export async function exportModel(runId, fmt) {
  const res = await fetch(url("/api/export"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ run_id: runId, fmt }),
  });
  return unwrap(res, "I couldn't get it ready for your computer");
}
