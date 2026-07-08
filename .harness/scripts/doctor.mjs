#!/usr/bin/env node
/**
 * @description Fail-closed health check. Exits non-zero when enforcement is broken — this is the
 * mechanism that makes the whole harness fail-closed (pre-push and CI both call it). WARNs are
 * visible but non-fatal. `--quiet` suppresses OK lines; `--fix` attempts safe repairs.
 *
 * Checks: hooks wired via core.hooksPath (present, executable, kaizen-managed); verify contract
 * filled; secret scanner status; memory committed in-repo (WARN-not-FAIL until the first .harness
 * commit exists — resolves the bootstrap deadlock); learning-loop scaffold; gate manifest present;
 * node/sh available; guard-session config sanity (WARN-only — see guard-sanity check below).
 */
import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync, accessSync, constants } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { loadConfig } from './lib/config.mjs';
import { repoRoot as gitRoot, git, isTracked } from './lib/repo.mjs';
import { commandExists } from './lib/platform.mjs';
import { guardStatus, GUARD_CONSUMERS } from './lib/guard-session.mjs';
import { SCAFFOLD_COMMANDS } from './lib/scaffold-note.mjs';
import { checkCanary, readCanaryFiles } from './audits/verify-canary.mjs';

function harnessEverCommitted() {
  return git(['log', '-1', '--format=%H', '--', '.harness']).out !== '';
}

export function runChecks(root, config) {
  const fails = [];
  const warns = [];
  const oks = [];

  // 1. hooks wired
  const hp = git(['config', '--get', 'core.hooksPath']).out;
  if (hp !== '.harness/hooks') fails.push(`git core.hooksPath is '${hp || '(unset)'}', expected '.harness/hooks' — hooks not wired`);
  else {
    for (const h of ['pre-commit', 'pre-push']) {
      const hf = path.join(root, '.harness', 'hooks', h);
      if (!existsSync(hf)) { fails.push(`hook missing: .harness/hooks/${h}`); continue; }
      try { accessSync(hf, constants.X_OK); } catch { fails.push(`hook not executable: .harness/hooks/${h}`); }
      if (!readFileSync(hf, 'utf8').includes('kaizen-managed-hook')) fails.push(`hook not kaizen-managed: .harness/hooks/${h} (a foreign hook occupies this path)`);
    }
    if (fails.length === 0) oks.push('hooks wired via core.hooksPath');
  }

  // 2. runtime present
  if (!commandExists('node')) fails.push('node not found on PATH (payload scripts require it)');
  else oks.push('node available');

  // 3. verify contract filled (required: test/lint/build non-empty or explicit "N/A")
  const v = config.verify || {};
  const filled = (x) => x && String(x).trim(); // non-empty; explicit "N/A" counts as intentionally filled
  const unfilled = ['test', 'lint', 'build'].filter((k) => !filled(v[k]));
  if (unfilled.length) fails.push(`verify contract unfilled: ${unfilled.join(', ')} (edit .harness/config.json → verify; use "N/A" if a step genuinely does not apply)`);
  else oks.push('verify contract filled');

  // 4. secret scanner
  const scanner = config.security?.secretScanner || 'none';
  if (scanner === 'gitleaks' && !commandExists('gitleaks', ['version'])) fails.push('secret scanner is gitleaks but gitleaks is not installed');
  else if (scanner === 'none') warns.push('secret scanning on pure-Node FALLBACK (gitleaks not found at install) — the fallback ruleset enforces on staged diffs; install gitleaks + `kaizen doctor --fix` for full-depth history scanning');
  else oks.push(`secret scanner: ${scanner}`);

  // 5. memory committed in-repo (bootstrap-aware)
  const memRel = '.harness/memory/memory.md';
  if (!existsSync(path.join(root, memRel))) fails.push('memory file missing: .harness/memory/memory.md');
  else if (!isTracked(memRel)) {
    if (harnessEverCommitted()) fails.push('memory not committed in-repo: .harness/memory/memory.md (git add + commit it)');
    else warns.push('memory not yet committed (fresh install) — will be committed by the bootstrap commit');
  } else oks.push('memory committed in-repo');

  // 6. gate manifest present
  if (!existsSync(path.join(root, '.harness', 'gates', 'core.gates.json'))) fails.push('missing gate manifest: .harness/gates/core.gates.json');
  else oks.push('gate manifest present');

  // 7. learning-loop scaffold (WARN if absent/empty)
  const errorsDir = path.join(root, config.docs?.learningLoop?.errorsDir || 'docs/errors');
  if (!existsSync(errorsDir)) warns.push(`learning-loop dir absent: ${path.relative(root, errorsDir)} (created on first incident)`);
  else oks.push('learning-loop scaffold present');

  // 8. CI backstop (WARN — branch protection can't be verified locally)
  if (!existsSync(path.join(root, '.github', 'workflows', 'kaizen-gate.yml'))) warns.push('CI backstop workflow absent (.github/workflows/kaizen-gate.yml) — fail-closed is local-only until added + branch protection enabled');

  // 9. guard-session config sanity + consumer wiring. FAIL-closed now that a real requireGuard() consumer
  //    exists (`next:execute`, roadmap Debt #4 closed): a malformed guard config or a guarded command with
  //    no wired consumer is broken enforcement, so it FAILs. A missing/idle *session* stays OK — idle is a
  //    normal state, not broken enforcement.
  const g = config.guard || {};
  if (!(Number.isFinite(g.maxCalls) && g.maxCalls > 0)) fails.push(`guard.maxCalls is not a positive number: ${JSON.stringify(g.maxCalls)}`);
  if (!(Number.isFinite(g.staleMinutes) && g.staleMinutes > 0)) fails.push(`guard.staleMinutes is not a positive number: ${JSON.stringify(g.staleMinutes)}`);
  if (!Array.isArray(g.scaffolderCommands)) fails.push(`guard.scaffolderCommands is not an array: ${JSON.stringify(g.scaffolderCommands)}`);
  // Each declared guarded command must map to a wired consumer (a note-scaffolder in SCAFFOLD_COMMANDS or a
  // non-scaffolder consumer in GUARD_CONSUMERS), else the guard gates a command that nothing implements.
  for (const cmd of Array.isArray(g.scaffolderCommands) ? g.scaffolderCommands : []) {
    if (!(cmd in SCAFFOLD_COMMANDS) && !GUARD_CONSUMERS.has(cmd)) fails.push(`guard.scaffolderCommands lists '${cmd}' but no consumer is wired for it (see scripts/lib/scaffold-note.mjs SCAFFOLD_COMMANDS or scripts/lib/guard-session.mjs GUARD_CONSUMERS)`);
  }
  if (Number.isFinite(g.maxCalls) && g.maxCalls > 0 && Number.isFinite(g.staleMinutes) && g.staleMinutes > 0 && Array.isArray(g.scaffolderCommands)) {
    const status = guardStatus(root, config);
    oks.push(status.active ? `guard session active (${status.callsRemaining} call(s) remaining)` : 'guard-session config sane (no active session)');
  }

  // 10. contract-read canary integrity (L4). Drift — a marker added/removed out of sync with the
  //     AGENTS.md protocol section — fails closed once the harness is committed. On a fresh pre-bootstrap
  //     tree the markers ship with `init`, so it only WARNs (mirrors the memory-not-yet-committed case).
  const canary = checkCanary(readCanaryFiles(root));
  if (canary.ok) oks.push('contract-read canary intact');
  else if (harnessEverCommitted()) for (const e of canary.errors) fails.push(`canary: ${e}`);
  else warns.push('contract-read canary not yet in place (fresh install — ships via init)');

  return { fails, warns, oks };
}

export function main(argv) {
  const quiet = argv.includes('--quiet');
  const root = gitRoot();
  const config = loadConfig(root);
  const { fails, warns, oks } = runChecks(root, config);

  if (!quiet) for (const o of oks) console.log(`✓ ${o}`);
  for (const w of warns) console.error(`! ${w}`);
  for (const f of fails) console.error(`✗ ${f}`);

  if (fails.length) { console.error(`\n✗ doctor: ${fails.length} failure(s) — enforcement is not intact.`); return 1; }
  if (!quiet) console.log(`\n✓ doctor: enforcement intact${warns.length ? ` (${warns.length} warning(s))` : ''}.`);
  return 0;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exit(main(process.argv.slice(2)));
}
