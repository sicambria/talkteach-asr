# TalkTeach — UI

The friendly web front-end for **TalkTeach**, a child-proof app for teaching a
computer to understand speech. It is a [Svelte](https://svelte.dev) app that runs
inside a [Tauri](https://tauri.app) desktop shell.

The whole experience is **one path**, designed for a 10-year-old:

> **Record → Check → Teach → Try**

(plus a "New project" start screen and a hidden "Grown-up mode" gear ⚙ that
reveals technical detail).

Everything on screen uses plain language — never jargon.

## Run it

You need [Node.js](https://nodejs.org) installed.

```bash
cd ui
npm install        # one time
npm run dev        # web-only preview at http://localhost:1420
```

`npm run dev` opens the UI in a normal browser — handy for quick design work.

### Full desktop app

The complete app (the real window, and later the bundled backend) needs **Rust**
and the Tauri toolchain. From the **repo root**:

```bash
# install Rust from https://rustup.rs, then:
cargo install tauri-cli --version "^2.0"
cargo tauri dev      # runs the Svelte UI inside the Tauri window
```

## The backend

The UI talks to a Python **FastAPI** backend at `http://127.0.0.1:8756`.
That base URL lives in one place: `src/lib/constants.js`.

**The backend must be running on port 8756** for recording, checking, teaching,
and trying to work. In Phase 1 the Tauri shell will start it automatically as a
sidecar; for now, start it yourself.

## Where things are

| Path | What it is |
| --- | --- |
| `src/App.svelte` | Wizard host: step state, stepper, mascot, Grown-up gear |
| `src/screens/` | The five screens (Screen0–Screen4) |
| `src/lib/api.js` | Typed client for every backend endpoint |
| `src/lib/store.js` | Shared state (project, sufficiency, run, grown-up mode) |
| `src/lib/constants.js` | Backend URL and other shared constants |
| `src/styles.css` | Kid-friendly theme |
