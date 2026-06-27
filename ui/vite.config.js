import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

// Tauri expects a fixed port and wants Vite to keep its own console output.
// https://tauri.app/start/frontend/vite/
export default defineConfig({
  plugins: [svelte()],
  // Prevent Vite from clobbering Rust/Tauri error messages in the terminal.
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
  },
});
