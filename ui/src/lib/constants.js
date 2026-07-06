// One place for shared constants. Change the backend address here only.
export const API_BASE = 'http://127.0.0.1:8756';

// How often the Teach screen asks "how's training going?" (milliseconds).
export const TRAIN_POLL_MS = 1500;

// How often the Advanced Arena polls a benchmark run for fresh cells (ms).
export const BENCH_POLL_MS = 2000;

// The four friendly wizard steps, in order. Screen 0 ("New project") sits
// before these and is not part of the visible stepper.
// jargon-free: Record -> Check -> Teach -> Try
export const STEPS = ['Record', 'Check', 'Teach', 'Try'];
