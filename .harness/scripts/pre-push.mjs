#!/usr/bin/env node
/**
 * @description pre-push hook driver (Node). Order: (1) fail-closed /doctor — a push must not
 * proceed with broken enforcement; (2) the core+adapter 'pre-push' gate chain (learning-loop +
 * verify contract). Output is tee'd to a timestamped log for post-mortem diagnosability; RC is
 * captured fail-closed (empty/non-numeric → 1). Bypass via --no-verify is possible locally; the
 * un-bypassable guarantee is the CI backstop gated by branch protection.
 */
import { spawnSync } from 'node:child_process';
import { mkdirSync, existsSync, appendFileSync, readdirSync, unlinkSync } from 'node:fs';
import path from 'node:path';
import { loadConfig } from './lib/config.mjs';
import { repoRoot } from './lib/repo.mjs';
import { runChain } from './gates/run-gates.mjs';

const root = repoRoot();
const config = loadConfig(root);
const logDir = path.join(root, config.hooks?.prePushLogDir || '.prepush-logs');

function log(line) {
  process.stdout.write(line + '\n');
  try {
    if (!existsSync(logDir)) mkdirSync(logDir, { recursive: true });
    appendFileSync(logFile, line + '\n');
  } catch { /* logging must never block */ }
}
const stamp = new Date(process.env.KZ_NOW_MS ? Number(process.env.KZ_NOW_MS) : Date.now())
  .toISOString().replace(/[:.]/g, '').replace('T', 'T').slice(0, 15);
const logFile = path.join(logDir, `${stamp}-${process.pid}.log`);

// Prune to newest 20 logs.
try {
  if (existsSync(logDir)) {
    const logs = readdirSync(logDir).filter((f) => f.endsWith('.log')).map((f) => path.join(logDir, f)).sort();
    for (const f of logs.slice(0, Math.max(0, logs.length - 20))) unlinkSync(f);
  }
} catch { /* best effort */ }

let rc = 0;

// (1) fail-closed doctor
log('→ pre-push: doctor (enforcement integrity)');
const doc = spawnSync('node', ['.harness/scripts/doctor.mjs', '--quiet'], { cwd: root, stdio: 'inherit' });
if (doc.status !== 0) { log('✗ pre-push: /doctor failed — enforcement is broken; push refused.'); process.exit(doc.status == null ? 1 : doc.status); }

// (2) pre-push gate chain
log('→ pre-push: gate chain');
rc = runChain('pre-push', root, config);

if (rc === 0) log(`[pre-push] OK — log ${path.relative(root, logFile)}`);
else log(`[pre-push] FAILED (rc ${rc}) — log ${path.relative(root, logFile)}`);
process.exit(Number.isInteger(rc) ? rc : 1);
