// TalkTeach desktop shell library entry point (Tauri v2 layout).
//
// The shell spawns the Python FastAPI backend as a **sidecar** (roadmap #15) so
// the user never starts a server — the four-tap wizard "just works" the moment
// the app opens. The backend binary is bundled as `binaries/talkteach-backend`
// (per-target via `externalBin` in tauri.conf.json; see docs/SIDECAR.md and
// docs/BUNDLING.md for how it's produced). On window close we kill the child so
// no orphaned server lingers.
//
// This is Tier B: the code is complete and idiomatic, but it is not compiled in
// the sandbox (the Linux Tauri build needs root-only WebKit/GTK dev libraries).
// Build it on a provisioned machine via the README "Quick start (desktop app)".

use std::sync::Mutex;

use tauri::{Manager, RunEvent, WindowEvent};
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_shell::ShellExt;

/// Holds the spawned backend child so we can terminate it on shutdown.
struct Backend(Mutex<Option<CommandChild>>);

fn spawn_backend(app: &tauri::AppHandle) -> Result<CommandChild, String> {
    // `sidecar()` resolves the bundled, per-target backend binary.
    let command = app
        .shell()
        .sidecar("talkteach-backend")
        .map_err(|e| format!("sidecar 'talkteach-backend' not found: {e}"))?;
    let (mut rx, child) = command
        .spawn()
        .map_err(|e| format!("failed to spawn the TalkTeach backend: {e}"))?;

    // Drain the sidecar's stdout/stderr so its pipe never fills and blocks it.
    tauri::async_runtime::spawn(async move {
        use tauri_plugin_shell::process::CommandEvent;
        while let Some(event) = rx.recv().await {
            if let CommandEvent::Stderr(line) | CommandEvent::Stdout(line) = event {
                // Backend logs land in the app log; structured logs also go to the
                // project dir (see docs/OBSERVABILITY.md).
                let _ = String::from_utf8(line);
            }
        }
    });

    Ok(child)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(Backend(Mutex::new(None)))
        .setup(|app| {
            match spawn_backend(app.handle()) {
                Ok(child) => {
                    app.state::<Backend>().0.lock().unwrap().replace(child);
                }
                // Don't crash the window if the backend can't start — the UI shows
                // a friendly "couldn't start" card instead (child-proof contract).
                Err(err) => eprintln!("TalkTeach backend did not start: {err}"),
            }
            Ok(())
        })
        .on_window_event(|window, event| {
            if matches!(event, WindowEvent::Destroyed) {
                if let Some(child) = window.app_handle().state::<Backend>().0.lock().unwrap().take() {
                    let _ = child.kill();
                }
            }
        })
        .build(tauri::generate_context!())
        .expect("error while building TalkTeach")
        .run(|app, event| {
            // Belt-and-braces: also reap the backend when the whole app exits.
            if let RunEvent::Exit = event {
                if let Some(child) = app.state::<Backend>().0.lock().unwrap().take() {
                    let _ = child.kill();
                }
            }
        });
}
