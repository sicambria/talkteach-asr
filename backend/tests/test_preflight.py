"""Tests for talkteach.reliability.preflight — pytest, stdlib only.

Run from the backend/ directory; pyproject sets pythonpath=["."].
"""

from __future__ import annotations

from talkteach.director import Compute, HardwareProfile
from talkteach.reliability.preflight import CheckStatus, run_preflight


def _profile(
    *,
    compute: Compute = Compute.CUDA,
    gpu_name: str | None = "NVIDIA RTX 4090",
    vram_gib: float = 24.0,
    ram_gib: float = 32.0,
    cpu_cores: int = 16,
    free_disk_gib: float = 200.0,
) -> HardwareProfile:
    return HardwareProfile(
        compute=compute,
        gpu_name=gpu_name,
        vram_gib=vram_gib,
        ram_gib=ram_gib,
        cpu_cores=cpu_cores,
        free_disk_gib=free_disk_gib,
    )


def _by_name(report, name: str):
    for r in report.results:
        if r.name == name:
            return r
    raise AssertionError(f"no check named {name!r} in {[r.name for r in report.results]}")


def test_healthy_profile_all_ok():
    report = run_preflight(_profile(), mic_present=True)
    assert report.ok is True
    assert report.can_train is True
    assert _by_name(report, "Disk").status is CheckStatus.OK
    assert _by_name(report, "Memory").status is CheckStatus.OK
    assert _by_name(report, "Speed").status is CheckStatus.OK
    assert _by_name(report, "Microphone").status is CheckStatus.OK
    assert all(r.status is CheckStatus.OK for r in report.results)


def test_low_disk_fails_and_blocks_training():
    report = run_preflight(_profile(free_disk_gib=1.0), mic_present=True)
    assert _by_name(report, "Disk").status is CheckStatus.FAIL
    assert report.ok is False
    assert report.can_train is False


def test_cpu_only_warns_but_can_train():
    report = run_preflight(
        _profile(compute=Compute.CPU, gpu_name=None, vram_gib=0.0),
        mic_present=True,
    )
    assert _by_name(report, "Speed").status is CheckStatus.WARN
    # CPU-only is a graceful-degradation WARN, never a FAIL.
    assert _by_name(report, "Speed").status is not CheckStatus.FAIL
    assert report.can_train is True


def test_missing_microphone_warns_but_does_not_block():
    report = run_preflight(_profile(), mic_present=False)
    mic = _by_name(report, "Microphone")
    assert mic.status is CheckStatus.WARN
    assert mic.remedy is not None
    assert report.can_train is True


def test_unknown_microphone_warns_softly():
    report = run_preflight(_profile(), mic_present=None)
    assert _by_name(report, "Microphone").status is CheckStatus.WARN
    assert report.can_train is True


def test_microphone_can_be_skipped():
    report = run_preflight(_profile(), check_microphone=False)
    names = [r.name for r in report.results]
    assert "Microphone" not in names


def test_low_ram_fails_and_blocks_training():
    report = run_preflight(_profile(ram_gib=2.0), mic_present=True)
    assert _by_name(report, "Memory").status is CheckStatus.FAIL
    assert report.ok is False
    assert report.can_train is False


def test_disk_warn_does_not_block():
    # Between min and 2x min -> WARN, still trainable.
    report = run_preflight(_profile(free_disk_gib=7.0), mic_present=True)
    assert _by_name(report, "Disk").status is CheckStatus.WARN
    assert report.can_train is True
    assert report.ok is True
