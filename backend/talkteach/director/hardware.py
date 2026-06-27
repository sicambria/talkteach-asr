"""Hardware probe — detect accelerator, VRAM, RAM, cores, and free disk.

Dependency-light by design: uses torch *if present* for accurate GPU/VRAM
detection, otherwise falls back to `nvidia-smi`, then to a CPU-only profile.
Never raises on a missing dependency — a missing probe just degrades the answer.
"""

from __future__ import annotations

import os
import shutil
import subprocess

from .types import Compute, HardwareProfile

_GIB = 1024**3


def _ram_gib() -> float:
    # Prefer the portable POSIX path; fall back to /proc on Linux.
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        if pages > 0 and page_size > 0:
            return pages * page_size / _GIB
    except (ValueError, OSError, AttributeError):
        pass
    try:
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) * 1024 / _GIB
    except OSError:
        pass
    return 0.0


def _free_disk_gib(path: str = ".") -> float:
    try:
        return shutil.disk_usage(path).free / _GIB
    except OSError:
        return 0.0


def _probe_gpu_via_torch() -> tuple[Compute, str | None, float] | None:
    try:
        import torch  # type: ignore
    except ImportError:
        return None
    try:
        if torch.cuda.is_available():
            idx = torch.cuda.current_device()
            name = torch.cuda.get_device_name(idx)
            vram = torch.cuda.get_device_properties(idx).total_memory / _GIB
            return Compute.CUDA, name, vram
        # Apple Silicon. MPS exposes no VRAM figure, so fall back to system RAM
        # (unified memory) as a conservative proxy upstream.
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return Compute.MPS, "Apple Silicon (MPS)", 0.0
    except Exception:  # torch present but CUDA driver/runtime broken
        return None
    return None


def _probe_gpu_via_nvidia_smi() -> tuple[Compute, str | None, float] | None:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    first = out.stdout.strip().splitlines()[0]
    try:
        name, mem_mib = (p.strip() for p in first.split(","))
        return Compute.CUDA, name, float(mem_mib) / 1024
    except (ValueError, IndexError):
        return None


def probe_hardware(disk_path: str = ".") -> HardwareProfile:
    """Best-effort hardware snapshot. Always returns a usable profile."""
    gpu = _probe_gpu_via_torch() or _probe_gpu_via_nvidia_smi()
    ram = _ram_gib()
    if gpu is not None:
        compute, name, vram = gpu
        # MPS reports no VRAM; treat unified memory as the budget.
        if compute is Compute.MPS and vram <= 0:
            vram = ram
        return HardwareProfile(
            compute=compute,
            gpu_name=name,
            vram_gib=round(vram, 2),
            ram_gib=round(ram, 2),
            cpu_cores=os.cpu_count() or 1,
            free_disk_gib=round(_free_disk_gib(disk_path), 2),
        )
    return HardwareProfile(
        compute=Compute.CPU,
        gpu_name=None,
        vram_gib=0.0,
        ram_gib=round(ram, 2),
        cpu_cores=os.cpu_count() or 1,
        free_disk_gib=round(_free_disk_gib(disk_path), 2),
    )
