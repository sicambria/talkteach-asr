// TalkTeach desktop shell library entry point (Tauri v2 layout).
//
// Phase 0: a thin window around the Svelte wizard UI.
// TODO(phase-1): spawn the Python FastAPI backend as a sidecar so the user never
// installs anything (see design report B.7 "no-install runtime").

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("error while running TalkTeach");
}
