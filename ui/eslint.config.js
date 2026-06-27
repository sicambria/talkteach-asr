// Flat ESLint config (ESLint 9+) for the Svelte UI. Kept intentionally light:
// svelte-check does the heavy type/template validation; ESLint catches JS-level
// foot-guns. Prettier owns formatting (eslint-config-prettier disables stylistic
// rules so the two never fight).
import js from '@eslint/js';
import svelte from 'eslint-plugin-svelte';
import prettier from 'eslint-config-prettier';
import globals from 'globals';

export default [
  js.configs.recommended,
  ...svelte.configs['flat/recommended'],
  prettier,
  ...svelte.configs['flat/prettier'],
  {
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: { ...globals.browser, ...globals.node },
    },
  },
  {
    ignores: ['dist/', 'node_modules/', 'src/lib/credits.json'],
  },
];
