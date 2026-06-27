"""Pre-flight checks — the friendly "ready to teach?" screen.

Before a child (or grown-up) hits "Teach!", we quietly look at the machine:
is there room on disk, enough memory, a GPU to go fast, a microphone to
record with? Nothing here ever crashes the app or blocks training unless it
genuinely *cannot* run. Slow is fine — we degrade gracefully (CPU/int8, or a
one-tap cloud GPU later) instead of failing.

Design report Part B.7: "Pre-flight check screen: verifies disk, RAM,
GPU/driver, microphone; degrades gracefully (CPU/int8, or one-tap cloud)
instead of failing."

Standard library only. Reuses the existing hardware probe in
``talkteach.director``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum

from talkteach.director import HardwareProfile, probe_hardware

# Sentinel literal for "figure the microphone out yourself".
_AUTO = "auto"


class CheckStatus(str, Enum):
    """How a single pre-flight check turned out."""

    OK = "ok"  # all good
    WARN = "warn"  # not ideal, but we can carry on (maybe slower)
    FAIL = "fail"  # genuinely can't proceed for this check


@dataclass(frozen=True)
class CheckResult:
    """The outcome of one check, in language a child-app can show directly."""

    name: str
    status: CheckStatus
    detail: str
    remedy: str | None = None


@dataclass(frozen=True)
class PreflightReport:
    """All checks rolled up, with simple yes/no properties for the UI."""

    results: list[CheckResult] = field(default_factory=list)

    # Checks that, when failing, mean we cannot train at all.
    _BLOCKING = frozenset({"Disk", "Memory"})

    @property
    def ok(self) -> bool:
        """True when nothing failed at all (everything is OK or WARN)."""
        return not any(r.status is CheckStatus.FAIL for r in self.results)

    @property
    def can_train(self) -> bool:
        """True unless a *blocking* check (disk/RAM) failed.

        A CPU-only machine or a missing microphone never blocks training —
        the app degrades gracefully (slower CPU mode, or drag in existing
        recordings).
        """
        return not any(
            r.status is CheckStatus.FAIL and r.name in self._BLOCKING for r in self.results
        )

    @property
    def summary(self) -> str:
        """One friendly sentence for the top of the pre-flight screen."""
        fails = sum(1 for r in self.results if r.status is CheckStatus.FAIL)
        warns = sum(1 for r in self.results if r.status is CheckStatus.WARN)
        if fails == 0 and warns == 0:
            return "All set — everything looks great!"
        if self.can_train:
            # Only Disk/Memory can FAIL and both block, so reaching here with
            # can_train True means warnings only.
            return "Ready to teach! A few things could be better, but nothing's stopping you."
        return "Not quite ready yet — let's fix one thing first."


def _microphone_via_sounddevice() -> bool | None:
    """Real cross-platform input-device probe via PortAudio, if available.

    ``sounddevice`` (optional) gives a true device list on Windows/macOS/Linux —
    far better than the ``/dev/snd`` heuristic. Returns True/False when it can
    enumerate devices, or None when the library/PortAudio backend is absent so the
    caller falls back to the per-OS heuristic.
    """
    try:
        import sounddevice as sd  # type: ignore
    except Exception:
        return None
    try:
        devices = sd.query_devices()
    except Exception:
        return None
    return any(d.get("max_input_channels", 0) > 0 for d in devices)


def _microphone_present() -> bool | None:
    """Best-effort microphone presence check (roadmap #18).

    Prefers a real PortAudio device query (cross-platform) when ``sounddevice``
    is installed; otherwise falls back to the ``/dev/snd`` heuristic on Linux, or
    None ("unknown") on macOS/Windows where we can't sniff without an audio lib.
    """
    via_lib = _microphone_via_sounddevice()
    if via_lib is not None:
        return via_lib
    if os.name == "posix" and os.path.isdir("/dev/snd"):
        try:
            # A bare /dev/snd with only "controlC*"/no card devices can exist;
            # any entry is a good-enough signal of an audio device.
            return any(os.scandir("/dev/snd"))
        except OSError:
            return True
    if os.name == "posix" and os.path.exists("/dev/snd"):
        return True
    # Linux without /dev/snd → confidently absent.
    if _is_linux():
        return False
    # Anything else (mac/windows): we can't tell without a real audio lib.
    return None


def _is_linux() -> bool:
    try:
        return os.uname().sysname == "Linux"  # type: ignore[attr-defined]
    except AttributeError:
        return False


def _check_disk(free_disk_gib: float, min_free_disk_gib: float) -> CheckResult:
    name = "Disk"
    if free_disk_gib < min_free_disk_gib:
        return CheckResult(
            name=name,
            status=CheckStatus.FAIL,
            detail=(
                f"There's only {free_disk_gib:.1f} GB of space left, and teaching "
                f"needs about {min_free_disk_gib:.0f} GB."
            ),
            remedy="Free up some space (empty the trash or remove old files), then try again.",
        )
    if free_disk_gib < 2 * min_free_disk_gib:
        return CheckResult(
            name=name,
            status=CheckStatus.WARN,
            detail=f"Space is a little tight — about {free_disk_gib:.1f} GB free.",
            remedy="It'll work, but freeing up some space makes things smoother.",
        )
    return CheckResult(
        name=name,
        status=CheckStatus.OK,
        detail=f"Plenty of room — about {free_disk_gib:.1f} GB free.",
    )


def _check_ram(ram_gib: float, min_ram_gib: float) -> CheckResult:
    name = "Memory"
    if ram_gib < min_ram_gib:
        return CheckResult(
            name=name,
            status=CheckStatus.FAIL,
            detail=(
                f"This computer has about {ram_gib:.1f} GB of memory, and teaching "
                f"needs at least {min_ram_gib:.0f} GB."
            ),
            remedy="Close some other apps, or try on a computer with more memory.",
        )
    if ram_gib < 1.5 * min_ram_gib:
        return CheckResult(
            name=name,
            status=CheckStatus.WARN,
            detail=f"Memory is a bit limited — about {ram_gib:.1f} GB.",
            remedy="Closing other apps will help things run smoothly.",
        )
    return CheckResult(
        name=name,
        status=CheckStatus.OK,
        detail=f"Lots of memory — about {ram_gib:.1f} GB.",
    )


def _check_compute(hw: HardwareProfile) -> CheckResult:
    name = "Speed"
    if hw.has_gpu:
        gpu = hw.gpu_name or "a graphics card"
        return CheckResult(
            name=name,
            status=CheckStatus.OK,
            detail=f"Found {gpu} — teaching will be nice and fast.",
        )
    return CheckResult(
        name=name,
        status=CheckStatus.WARN,
        detail="No graphics card found, so teaching will be slower.",
        remedy="We'll use the slower CPU mode, or you can connect to a cloud GPU later.",
    )


def _check_microphone(present: bool | None) -> CheckResult:
    name = "Microphone"
    if present is True:
        return CheckResult(
            name=name,
            status=CheckStatus.OK,
            detail="A microphone is ready — you can record new sounds.",
        )
    if present is False:
        return CheckResult(
            name=name,
            status=CheckStatus.WARN,
            detail="We couldn't find a microphone.",
            remedy="Plug in or allow your microphone; you can still drag in existing recordings.",
        )
    # Unknown — softer wording.
    return CheckResult(
        name=name,
        status=CheckStatus.WARN,
        detail="We couldn't check the microphone on this computer.",
        remedy="If recording doesn't work, plug in or allow your microphone — "
        "you can also drag in existing recordings.",
    )


def run_preflight(
    hw: HardwareProfile | None = None,
    *,
    min_free_disk_gib: float = 5.0,
    min_ram_gib: float = 4.0,
    check_microphone: bool = True,
    mic_present: bool | None | str = _AUTO,
) -> PreflightReport:
    """Run all pre-flight checks and return a friendly, non-fatal report.

    Args:
        hw: A hardware profile; if None, ``probe_hardware()`` is called.
        min_free_disk_gib: Below this, Disk FAILs; below 2x, it WARNs.
        min_ram_gib: Below this, Memory FAILs; below 1.5x, it WARNs.
        check_microphone: Whether to include the microphone check at all.
        mic_present: Override for the microphone result. ``"auto"`` (default)
            sniffs the system; True/False/None forces present/absent/unknown.
    """
    if hw is None:
        hw = probe_hardware()

    results: list[CheckResult] = [
        _check_disk(hw.free_disk_gib, min_free_disk_gib),
        _check_ram(hw.ram_gib, min_ram_gib),
        _check_compute(hw),
    ]

    if check_microphone:
        # if/else (not a ternary) so mypy can narrow away the _AUTO str sentinel.
        present: bool | None
        if mic_present == _AUTO:  # noqa: SIM108
            present = _microphone_present()
        else:
            # Narrowed: anything other than the _AUTO sentinel is a bool|None override.
            present = mic_present  # type: ignore[assignment]
        results.append(_check_microphone(present))

    return PreflightReport(results=results)
