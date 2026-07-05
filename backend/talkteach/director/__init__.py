"""The TalkTeach director — zero-config intelligence that removes every
ML decision from the user (hardware probe, data probe, language probe,
sufficiency gate, and the policy that combines them into a TrainingPlan)."""

from .active_learning import ClipUncertainty, rank_clips
from .hardware import probe_hardware
from .language import probe_language, supported_languages
from .policy import adaptive_target, augmentation_for, build_plan, sufficiency
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
    "supported_languages",
    "build_plan",
    "sufficiency",
    "adaptive_target",
    "augmentation_for",
    "rank_clips",
    "ClipUncertainty",
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
