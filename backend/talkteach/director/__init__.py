"""The TalkTeach director — zero-config intelligence that removes every
ML decision from the user (hardware probe, data probe, language probe,
sufficiency gate, and the policy that combines them into a TrainingPlan)."""

from .hardware import probe_hardware
from .language import probe_language
from .policy import build_plan, sufficiency
from .types import (
    Compute,
    DataProfile,
    EngineKind,
    GateStatus,
    HardwareProfile,
    LanguageProfile,
    Precision,
    SufficiencyResult,
    TrainingPlan,
)

__all__ = [
    "probe_hardware",
    "probe_language",
    "build_plan",
    "sufficiency",
    "Compute",
    "DataProfile",
    "EngineKind",
    "GateStatus",
    "HardwareProfile",
    "LanguageProfile",
    "Precision",
    "SufficiencyResult",
    "TrainingPlan",
]
