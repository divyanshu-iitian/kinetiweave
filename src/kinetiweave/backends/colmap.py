from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import trimesh

from kinetiweave.backends.base import (
    BackendUnavailable,
    ReconstructionBackend,
    ReconstructionFailed,
    ReconstructionResult,
    artifact_from_path,
)


class ColmapBackend(ReconstructionBackend):
    backend_id = "colmap"

    def __init__(self, executable: Path | None = None, timeout_seconds: int = 10_800) -> None:
        configured = os.getenv("KINETIWEAVE_COLMAP")
        discovered = configured or shutil.which("colmap") or shutil.which("COLMAP.bat")
        self.executable = executable or (Path(discovered).resolve() if discovered else None)
        self.timeout_seconds = timeout_seconds

    def available(self) -> bool:
        return self.executable is not None and self.executable.is_file()

    def reconstruct(self, request, on_progress) -> ReconstructionResult:
        if not self.available():
            raise BackendUnavailable(
                "COLMAP was not found. Set KINETIWEAVE_COLMAP to the official executable."
            )
        workspace = request.output_dir
        workspace.mkdir(parents=True, exist_ok=True)
        use_gpu = "1" if request.gpu_vram_gb is not None else "0"
        quality = {"fast": "low", "balanced": "medium", "quality": "high"}[request.profile.value]
        command = [
            str(self.executable),
            "automatic_reconstructor",
            "--workspace_path",
            str(workspace),
            "--image_path",
            str(request.frames_dir),
            "--data_type",
            "VIDEO",
            "--quality",
            quality,
            "--use_gpu",
            use_gpu,
            "--dense",
            "1",
            "--num_threads",
            str(min(os.cpu_count() or 4, 10)),
        ]
        on_progress(0.05, "Starting COLMAP structure-from-motion")
        log_path = workspace / "colmap.log"
        try:
            with log_path.open("w", encoding="utf-8") as log:
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    cwd=workspace,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                assert process.stdout is not None
                for line in process.stdout:
                    log.write(line)
                    log.flush()
                    progress, message = _parse_progress(line)
                    if message:
                        on_progress(progress, message)
                return_code = process.wait(timeout=self.timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            raise ReconstructionFailed("COLMAP exceeded the three-hour local job limit.") from exc
        if return_code != 0:
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            tail = "\n".join(lines[-30:])
            raise ReconstructionFailed(f"COLMAP failed with exit code {return_code}.\n{tail}")

        on_progress(0.92, "Preparing browser-compatible geometry")
        mesh_candidates = list(workspace.rglob("meshed-poisson.ply")) + list(
            workspace.rglob("meshed-delaunay.ply")
        )
        point_candidates = list(workspace.rglob("fused.ply"))
        source = mesh_candidates or point_candidates
        if not source:
            raise ReconstructionFailed("COLMAP completed without a dense geometry artifact.")
        source_path = max(source, key=lambda item: item.stat().st_size)
        glb_path = workspace / "reconstruction.glb"
        geometry = trimesh.load(source_path, process=False)
        geometry.export(glb_path)
        representation = "surface mesh" if mesh_candidates else "dense point cloud"
        metadata = {
            "quality": quality,
            "gpu_requested": use_gpu == "1",
            "representation": representation,
            "metric_scale": False,
            "source_file": source_path.relative_to(workspace).as_posix(),
        }
        metadata_path = workspace / "reconstruction.json"
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return ReconstructionResult(
            backend=self.backend_id,
            artifacts=(
                artifact_from_path(
                    glb_path,
                    root=workspace.parent,
                    name="Interactive 3D reconstruction",
                    kind="mesh" if mesh_candidates else "point-cloud",
                    media_type="model/gltf-binary",
                    experimental=not bool(mesh_candidates),
                ),
                artifact_from_path(
                    log_path,
                    root=workspace.parent,
                    name="COLMAP processing log",
                    kind="log",
                    media_type="text/plain",
                ),
                artifact_from_path(
                    metadata_path,
                    root=workspace.parent,
                    name="Reconstruction manifest",
                    kind="metadata",
                    media_type="application/json",
                ),
            ),
            metadata=metadata,
            warnings=("Scale is relative until a measured reference is provided.",),
        )


def _parse_progress(line: str) -> tuple[float, str | None]:
    lowered = line.lower()
    if "feature extraction" in lowered:
        return 0.12, "Finding visual features"
    if "matching" in lowered:
        return 0.28, "Matching views"
    if "mapper" in lowered or "registering image" in lowered:
        return 0.45, "Solving camera positions"
    if "undistort" in lowered:
        return 0.6, "Preparing calibrated views"
    if "patch match" in lowered or "stereo" in lowered:
        return 0.72, "Estimating dense geometry"
    if "fusion" in lowered:
        return 0.84, "Fusing depth maps"
    if "meshing" in lowered or "poisson" in lowered:
        return 0.9, "Building the surface mesh"
    return 0.08, None
