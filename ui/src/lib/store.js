// Shared app state for the TalkTeach wizard.
// jargon-free: these stores hold the few things every screen needs to see.
import { writable } from 'svelte/store';

// The project the user is working on: { project_id, name, language_code }.
export const project = writable(null);

// Latest "minutes of good audio" report from GET /api/sufficiency.
// Shape: { status, good_minutes, target_minutes, fraction, messages }
export const sufficiency = writable(null);

// The training run currently in progress (or just finished).
// Shape: { run_id, ...TrainProgress }
export const currentRun = writable(null);

// Hidden "Advanced mode" — when true, screens reveal technical detail panels.
// Off by default so easy mode only ever shows plain language.
export const advancedMode = writable(false);

// The TTS×ASR "Arena" benchmark currently running (or just finished).
// Shape: { benchmark_id, status, report } where report is the scoreboard payload.
export const benchmark = writable(null);
