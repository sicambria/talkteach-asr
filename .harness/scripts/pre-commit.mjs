#!/usr/bin/env node
/**
 * @description pre-commit hook driver (Node — the .husky/-style sh idioms are forbidden by
 * verify-script-parity). Runs the consolidated branch-guard, then the core+adapter 'pre-commit'
 * gate chain. Fail-closed. The installer sets KZ_BOOTSTRAP=1 for the single sanctioned install
 * commit so the harness can commit itself without the guard blocking it.
 */
import { loadConfig } from './lib/config.mjs';
import { repoRoot, currentBranch, stagedPaths, mergeInProgress } from './lib/repo.mjs';
import { isBlockedEdit } from './lib/branch-guard.mjs';
import { runChain } from './gates/run-gates.mjs';
import { runChainedHooks } from './lib/chained-hooks.mjs';

const root = repoRoot();
const config = loadConfig(root);
const bootstrap = process.env.KZ_BOOTSTRAP === '1';

const guard = isBlockedEdit({
  branch: currentBranch(),
  paths: stagedPaths(),
  mergeInProgress: mergeInProgress(),
  bootstrap,
  config,
});
if (guard.blocked) {
  console.error(`✗ pre-commit BLOCKED: ${guard.reason}`);
  console.error(`  offending: ${guard.offending.join(', ')}`);
  console.error(`  → create a worktree and merge, or restrict this commit to exempt (docs) paths.`);
  process.exit(1);
}

const rc = runChain('pre-commit', root, config);
if (rc !== 0) process.exit(rc);

// Chain the repo's pre-existing pre-commit controls so kaizen never weakens them (no-op if none).
process.exit(runChainedHooks('pre-commit', root, config, { args: process.argv.slice(2) }));
