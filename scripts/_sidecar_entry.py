"""Frozen-binary entry point for the TalkTeach backend sidecar.

PyInstaller freezes this into the `talkteach-backend-<triple>` executable the
Tauri shell spawns (see scripts/build_sidecar.py and project/docs/SIDECAR.md). It just
boots the FastAPI app on the configured host/port.
"""

from talkteach.app import main

if __name__ == "__main__":
    main()
