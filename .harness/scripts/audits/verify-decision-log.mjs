#!/usr/bin/env node
/**
 * @description Audited-escape-hatch gate — the enforcement counterpart to the /decide skill.
 * Turns AGENTS.md's "Overrides are audited, never silent" from prose into a real gate: if a staged
 * commit removes/disables a gate, trips a bypass flag, or carries the override marker, but adds NO
 * decision record under .harness/archive/decisions, the commit is BLOCKED with a pointer to /decide.
 *
 * Pure core `detectUnloggedOverride(stagedDiff, stagedFiles, decisionsAddedInCommit)` + a thin CLI
 * that scans the STAGED set (git diff --cached / stagedPaths). Concrete signal examples deliberately
 * live in .harness/archive/decisions/README.md (a .md, excluded from bypass-key scanning) rather than
 * in this file's prose, so the gate never flags edits to its own source once wired.
 */
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { repoRoot as gitRoot, stagedPaths, git } from '../lib/repo.mjs';

// Assembled at runtime so this source never contains the literal marker token (which would otherwise
// make the gate flag edits to itself once wired). A real override annotates the change with this.
const OVERRIDE_MARKER = 'KAIZEN-' + 'OVERRIDE' + ':';

const DECISIONS_DIR = '.harness/archive/decisions/';
// Files under the decisions dir that do NOT count as "a decision record was written".
const DECISION_EXCLUDE = /^(README|TEMPLATE)\.md$|^_/;

// Bypass/skip keys on an ADDED config/script line. The escapes in these patterns mean this file's
// own source lines do not self-match.
const BYPASS_PATTERNS = [
  { re: /"secretScanner"\s*:\s*"none"/, why: 'secret scanner disabled' },
  { re: /"(allow[-_]?fail|lenient|skip|bypass)"\s*:\s*true/i, why: 'bypass/skip flag enabled' },
  { re: /"enabled"\s*:\s*false/, why: 'gate disabled' },
];

const isMarkdown = (p) => p.endsWith('.md');
const isTest = (p) => p.startsWith('test/');
const isGatesFile = (p) => /\.gates\.json$/.test(p);
// Bypass keys are only meaningful in structured config/script files — never docs or test fixtures.
const isConfigLike = (p) => !isMarkdown(p) && !isTest(p) && /\.(json|mjs|cjs|js|ya?ml|toml|sh)$/.test(p);

/** Strip inline `code` spans so a backtick-wrapped doc reference to the marker is never a signal. */
const stripInlineCode = (s) => s.replace(/`[^`]*`/g, '');

/** Parse a unified staged diff into [{ path, added:[], removed:[] }] per file. */
function parseDiff(diff) {
  const files = [];
  let cur = null;
  for (const line of (diff || '').split('\n')) {
    const h = line.match(/^\+\+\+ b\/(.+)$/);
    if (h) { cur = { path: h[1], added: [], removed: [] }; files.push(cur); continue; }
    if (!cur) continue;
    if (line.startsWith('+++') || line.startsWith('---')) continue;
    if (line.startsWith('+')) cur.added.push(line.slice(1));
    else if (line.startsWith('-')) cur.removed.push(line.slice(1));
  }
  return files;
}

/**
 * Pure detector. Given the staged diff and the decisions staged in the SAME commit, decide whether
 * an override is going in unlogged.
 * @param {string} stagedDiff  unified `git diff --cached` text. A test may append a synthetic
 *   `+++ b/COMMIT_MSG` section with `+`-prefixed lines to exercise the marker channel.
 * @param {string[]} stagedFiles  repo-relative staged paths (part of the contract; scoping is done
 *   per-file from the diff, so this is currently informational).
 * @param {string[]|boolean} decisionsAddedInCommit  decision records added/modified in this commit
 *   (array of paths) or a boolean — used DIRECTLY as the has-decision fact (not re-derived here).
 * @returns {{ok:boolean, hasOverride:boolean, hasDecision:boolean, signals:string[]}}
 */
export function detectUnloggedOverride(stagedDiff, stagedFiles, decisionsAddedInCommit) {
  const hasDecision = Array.isArray(decisionsAddedInCommit)
    ? decisionsAddedInCommit.length > 0
    : Boolean(decisionsAddedInCommit);
  const signals = [];

  for (const f of parseDiff(stagedDiff)) {
    // (a) gate removed from a chain — a removed "id" not re-added elsewhere in the file (reorder-safe).
    if (isGatesFile(f.path)) {
      const idOf = (l) => (l.match(/"id"\s*:\s*"([^"]+)"/) || [])[1];
      const addedIds = new Set(f.added.map(idOf).filter(Boolean));
      for (const rl of f.removed) {
        const id = idOf(rl);
        if (id && !addedIds.has(id)) signals.push(`${f.path}: gate "${id}" removed from a chain`);
      }
    }
    // (b) bypass/skip key set on an added config/script line — but only on a NET increase, so a
    // reformat of an already-disabled line (the same value on both sides of the diff, e.g. a sibling
    // key gives `secretScanner:none` a trailing comma) is not a false override. Net-count (not "any
    // removed match") is required because `enabled`/`skip` are multi-context keys: a commit that
    // reformats one block's `enabled:false` AND freshly disables another must still fire on the fresh
    // disable (added 2 / removed 1 → net +1). Counted per-pattern → one signal per pattern per file.
    if (isConfigLike(f.path)) {
      for (const { re, why } of BYPASS_PATTERNS) {
        const addedN = f.added.filter((l) => re.test(l)).length;
        if (addedN === 0) continue;
        const removedN = f.removed.filter((l) => re.test(l)).length;
        if (addedN > removedN) signals.push(`${f.path}: ${why}`);
      }
    }
    // (c) override marker on an added line of any non-test file (inline code spans stripped).
    if (!isTest(f.path)) {
      if (f.added.some((al) => stripInlineCode(al).includes(OVERRIDE_MARKER))) {
        signals.push(`${f.path}: override marker present`);
      }
    }
  }

  const hasOverride = signals.length > 0;
  return { ok: !(hasOverride && !hasDecision), hasOverride, hasDecision, signals };
}

/** CLI: scan the staged set; exit 1 if an override is staged without a decision record. */
export function main() {
  // The single sanctioned install commit (KZ_BOOTSTRAP=1) writes the INITIAL config — e.g.
  // `secretScanner: none` when gitleaks is absent — which is initial setup, not an override of an
  // existing posture. Honor the bootstrap flag exactly as the branch-guard does (pre-commit.mjs), or
  // `kaizen init` fails closed on every machine without gitleaks.
  if (process.env.KZ_BOOTSTRAP === '1') { console.log('✓ decision-log: skipped (sanctioned bootstrap install)'); return 0; }
  const root = gitRoot();
  const staged = stagedPaths();
  const diff = git(['diff', '--cached', '--unified=0'], { cwd: root }).out;
  const decisions = staged.filter(
    (p) => p.startsWith(DECISIONS_DIR) && p.endsWith('.md') && !DECISION_EXCLUDE.test(path.basename(p)),
  );
  const res = detectUnloggedOverride(diff, staged, decisions);
  if (!res.ok) {
    console.error('✗ decision-log: override signal(s) staged with no decision record:');
    for (const s of res.signals) console.error(`    - ${s}`);
    console.error('  → log the override via /decide (writes .harness/archive/decisions/<date>-<slug>.md), then re-stage & commit.');
    return 1;
  }
  if (res.hasOverride) console.log(`✓ decision-log: ${res.signals.length} override signal(s) audited by a decision record`);
  else console.log('✓ decision-log: no override signals');
  return 0;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exit(main());
}
