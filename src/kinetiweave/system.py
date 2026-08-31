from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import subprocess
from pathlib import Path

from kinetiweave.domain import CaptureProfile, SystemCapabilities


def detect_capabilities() -> SystemCapabilities:
    logical_cores = os.cpu_count() or 1
    ram_gb = _ram_gb()
    gpu, vram_gb = _nvidia_gpu()
    cuda_available = False
    cuda_runtime: str | None = None
    try:
        import torch

        cuda_available = bool(torch.cuda.is_available())
        cuda_runtime = torch.version.cuda
        if cuda_available and not gpu:
            gpu = torch.cuda.get_device_name(0)
            properties = torch.cuda.get_device_properties(0)
            vram_gb = round(properties.total_memory / 1024**3, 1)
    except (ImportError, OSError):
        pass

    colmap_path = _colmap_path()
    da3_available = importlib.util.find_spec("depth_anything_3") is not None
    recommended_backend: str | None = None
    limitations: list[str] = []
    if da3_available:
        recommended_backend = "da3"
        if not cuda_available:
            limitations.append(
                "DA3 is installed but CUDA PyTorch is not active. Inference will be slow."
            )
    elif colmap_path:
        recommended_backend = "colmap"
    else:
        limitations.append(
            "Install the DA3 Small adapter or COLMAP before starting reconstruction."
        )

    recommended_profile = CaptureProfile.BALANCED
    if vram_gb is not None and vram_gb < 6:
        recommended_profile = CaptureProfile.FAST
        limitations.append(
            "GPU memory is below 6 GB. Fast mode uses fewer views and retries at lower resolution."
        )
    if ram_gb is not None and ram_gb < 12:
        recommended_profile = CaptureProfile.FAST

    return SystemCapabilities(
        os=f"{platform.system()} {platform.release()}",
        cpu=platform.processor() or "Unknown CPU",
        logical_cores=logical_cores,
        ram_gb=ram_gb,
        gpu=gpu,
        gpu_vram_gb=vram_gb,
        cuda_available=cuda_available,
        cuda_runtime=cuda_runtime,
        da3_available=da3_available,
        colmap_available=colmap_path is not None,
        colmap_path=str(colmap_path) if colmap_path else None,
        ffmpeg_available=shutil.which("ffmpeg") is not None,
        recommended_backend=recommended_backend,
        recommended_profile=recommended_profile,
        limitations=limitations,
    )


def _colmap_path() -> Path | None:
    configured = os.getenv("KINETIWEAVE_COLMAP")
    candidates = [configured, shutil.which("colmap"), shutil.which("COLMAP.bat")]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate).resolve()
    return None


def _nvidia_gpu() -> tuple[str | None, float | None]:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return None, None
    try:
        result = subprocess.run(
            [
                executable,
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=8,
        )
        first_line = result.stdout.strip().splitlines()[0]
        name, memory_mib = [value.strip() for value in first_line.rsplit(",", 1)]
        return name, round(float(memory_mib) / 1024, 1)
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return None, None


def _ram_gb() -> float | None:
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=8,
            )
            return round(int(result.stdout.strip()) / 1024**3, 1)
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        return round(pages * page_size / 1024**3, 1)
    except (AttributeError, OSError, subprocess.SubprocessError, ValueError):
        return None
