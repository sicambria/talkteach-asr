// Shared app state for the TalkTeach wizard.
// jargon-free: these stores hold the few things every screen needs to see.
import { writable } from "svelte/store";

// The project the child is working on: { project_id, name, language_code }.
export const project = writable(null);

// Latest "minutes of good audio" report from GET /api/sufficiency.
// Shape: { status, good_minutes, target_minutes, fraction, messages }
export const sufficiency = writable(null);

// The training run currently in progress (or just finished).
// Shape: { run_id, ...TrainProgress }
export const currentRun = writable(null);

// Hidden "Grown-up mode" — when true, screens reveal technical detail panels.
// Off by default so kids only ever see plain language.
export const grownUpMode = writable(false);
