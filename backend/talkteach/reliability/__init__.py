"""TalkTeach reliability — pre-flight checks and graceful-degradation helpers.

The pre-flight module verifies disk, memory, GPU/compute and microphone before
training, and reports problems in child-app language without ever crashing or
hard-blocking unless training truly cannot run.
"""

from .preflight import (
    CheckResult,
    CheckStatus,
    PreflightReport,
    run_preflight,
)

__all__ = [
    "CheckResult",
    "CheckStatus",
    "PreflightReport",
    "run_preflight",
]
