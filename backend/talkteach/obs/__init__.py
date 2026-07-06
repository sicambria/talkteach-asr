"""Observability — structured logging + a help-bundle exporter (roadmap #41).

Privacy posture (project/docs/DECISIONS.md D-008): logs are **local-only**, off no network.
There is no telemetry. When something goes wrong, the user can export a "help
bundle" (a zip of logs + redacted environment) to share *deliberately* — never an
automatic phone-home. This matters doubly for a local app handling voice.
"""

from .logging import configure_logging, export_help_bundle, get_logger

__all__ = ["configure_logging", "export_help_bundle", "get_logger"]
