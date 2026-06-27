"""TalkTeach backend — a child-proof, zero-config ASR-training job server.

This is Phase 0 of the build described in
`reports/ASR_training_GUI_wizard_research_and_design_2026-06-27.md` (Part B) in
the companion Turan_engine repo. The director and the audio/data/reliability
logic are real and tested; the ML training path runs in a dependency-free
simulation mode until the `[ml]` extra is installed (see engines/).
"""

__version__ = "0.0.1"
