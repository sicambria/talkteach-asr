#!/usr/bin/env node
/**
 * @description The single source of truth loader for `.harness/config.yaml`.
 * Every stack/repo coupling in the harness is a named key here. Resolution order for
 * seams is ENV-VAR-FIRST then config then default, so the existing changemappers seams
 * (GUARD_*, *_ROOT, PLAN_WORKFLOW_*) keep working for tests.
 */

import { readFileSync, existsSync } from 'node:fs';
import path from 'node:path';

/** Deep-merge b onto a (objects only; arrays replaced). */
function merge(a, b) {
  if (b === undefined || b === null) return a;
  if (Array.isArray(a) || Array.isArray(b) || typeof a !== 'object' || typeof b !== 'object') return b;
  const out = { ...a };
  for (const k of Object.keys(b)) out[k] = merge(a[k], b[k]);
  return out;
}

/**
 * The default configuration. A bare repo with only these defaults must pass the core
 * `guardrails` chain (the portability acceptance test). Adapters overlay onto this.
 * @param {string} repoName
 */
export function defaultConfig(repoName = 'app') {
  return {
    version: 1,
    defaultBranch: 'main',
    repo: { name: repoName },
    docs: {
      core: [
        { path: 'AGENTS.md', required: true },
        { path: 'README.md', required: false },
      ],
      markdownRoots: ['docs'],
      learningLoop: {
        errorsDir: 'docs/errors',
        auditsDir: 'docs/audits',
        requiredMetadata: ['Date', 'Type', 'Area', 'Status', 'Trigger', 'Guardrail Links', 'Automation Links'],
        requiredSections: ['## Summary', '## Root Cause', '## Prevention', '## Guardrail Updates', '## Automation Follow-Up'],
        allowedTypes: ['incident', 'reference'],
        allowedStatuses: ['active', 'monitoring', 'resolved'],
      },
    },
    plan: {
      planTypes: ['FEATURE', 'BUG', 'RCA', 'TECHDEBT', 'IMPROVEMENT', 'SPIKE', 'CHORE', 'TEST'],
      dirs: {
        active: 'docs/plans',
        worktrees: 'docs/plans/worktrees',
        done: 'docs/plans/done',
      },
      claimsFile: 'docs/plans/worktree-current-state.md',
      evidenceHeading: '## Standards & Guardrails Evidence',
      // Core (portable) dimensions. Adapters append (schema-migrations, i18n, ...).
      dimensions: [
        { key: 'Tests / shift-left', match: 'test', core: true },
        { key: 'Reused patterns / grounding', match: 'reuse|pattern|grounding', core: true },
        { key: 'Security', match: 'security|privacy', core: true },
      ],
      // Prose snippets required to exist in docs. Empty in core; adapters/init populate.
      requiredDocumentation: [],
      // 'grounding' (full path:line citation resolution) or 'structural' (heading/section presence).
      evidenceMode: 'grounding',
    },
    branchGuard: {
      // Exempt = docs-like / trivial. Everything else is substantive (fail-closed default:
      // an empty substantivePaths list means "anything non-exempt is substantive").
      exemptPaths: ['^docs/', '\\.md$', '^\\.gitignore$', '^\\.harness/memory/', '^\\.harness/archive/'],
      substantivePaths: [],
    },
    worktree: {
      base: null, // null => "<repoRoot>-wt"
      dirPrefix: null, // null => repo.name
      sharedLinks: ['node_modules'],
    },
    guard: {
      sessionTokenName: 'harness-session-token',
      maxCalls: 40,
      staleMinutes: 30,
      docs: [],
      scaffolderCommands: ['incident:new', 'audit:finding'],
    },
    hooks: {
      requiredBinaries: [], // core requires none beyond node+git; adapters add e.g. husky/tsx
      prePushLogDir: '.prepush-logs',
      priorHooksPath: null, // captured at install for uninstall
      managed: true,
    },
    verify: { test: '', lint: '', build: '', e2e: '', healthcheck: '' },
    gates: { core: 'core', adapters: [] },
    security: { secretScanner: 'gitleaks' },
    mcp: { registry: [] },
    // Which agent overlays were generated (claude, cursor, codex, opencode, copilot).
    agents: [],
    mode: 'full', // 'full' | 'minimal'
  };
}

/** Resolve the config file path within a repo root. JSON for zero-dependency payload parsing. */
export function configPath(repoRoot) {
  return path.join(repoRoot, '.harness', 'config.json');
}

/**
 * Load config from a repo root, merged onto defaults. Missing file => defaults only.
 * @param {string} repoRoot
 * @param {{repoName?: string}} [opts]
 */
export function loadConfig(repoRoot, opts = {}) {
  const base = defaultConfig(opts.repoName || path.basename(repoRoot || 'app'));
  const p = configPath(repoRoot);
  if (!existsSync(p)) return resolveComputed(base, repoRoot);
  let parsed = {};
  try {
    parsed = JSON.parse(readFileSync(p, 'utf8')) || {};
  } catch (e) {
    throw new Error(`Invalid .harness/config.json: ${e.message}`);
  }
  return resolveComputed(merge(base, parsed), repoRoot);
}

/** Fill in null-computed defaults (worktree base/dirPrefix) and expose helpers. */
function resolveComputed(cfg, repoRoot) {
  const name = cfg.repo?.name || path.basename(repoRoot || 'app');
  if (cfg.worktree.base == null) cfg.worktree.base = `${repoRoot || '.'}-wt`;
  if (cfg.worktree.dirPrefix == null) cfg.worktree.dirPrefix = name;
  cfg.repoRoot = repoRoot;
  return cfg;
}

/** Serialize config to JSON for writing (payload reads it with zero deps). */
export function stringifyConfig(cfg) {
  // Do not persist computed-only fields.
  const { repoRoot, ...persist } = cfg;
  return JSON.stringify(persist, null, 2) + '\n';
}

/** ENV-first-then-config seam resolver. */
export function seam(envName, cfgValue, fallback) {
  if (process.env[envName] != null && process.env[envName] !== '') return process.env[envName];
  return cfgValue != null ? cfgValue : fallback;
}
