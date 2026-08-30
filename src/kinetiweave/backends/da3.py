from __future__ import annotations

import gc
import importlib.util
import json
from pathlib import Path

from kinetiweave.backends.base import (
    BackendUnavailable,
    ReconstructionBackend,
    ReconstructionFailed,
    ReconstructionResult,
    artifact_from_path,
)
from kinetiweave.domain import CaptureProfile


class Da3Backend(ReconstructionBackend):
    backend_id = "da3-small"
    model_id = "depth-anything/DA3-SMALL"

    def __init__(self) -> None:
        self._model = None
        self._device: str | None = None

    def available(self) -> bool:
        return importlib.util.find_spec("depth_anything_3") is not None

    def reconstruct(self, request, on_progress) -> ReconstructionResult:
        if not self.available():
            raise BackendUnavailable(
                "Depth Anything 3 is not installed. Run: powershell -File scripts/setup-da3.ps1"
            )
        try:
            import torch
            from depth_anything_3.api import DepthAnything3
        except ImportError as exc:
            raise BackendUnavailable(
                "The DA3 adapter is incomplete. Re-run scripts/setup-da3.ps1."
            ) from exc

        device = "cuda" if torch.cuda.is_available() else "cpu"
        if device == "cpu":
            on_progress(0.02, "CUDA is unavailable. DA3 will run on CPU and may take a long time")
        if self._model is None or self._device != device:
            on_progress(0.05, "Loading the Apache-2.0 DA3 Small model")
            self._model = DepthAnything3.from_pretrained(self.model_id).to(device)
            self._model.eval()
            self._device = device

        all_frames = sorted(request.frames_dir.glob("*.jpg"))
        frame_limit, resolution = _da3_budget(request.profile, request.gpu_vram_gb)
        selected = _evenly_spaced(all_frames, min(frame_limit, len(all_frames)))
        if len(selected) < 3:
            raise ReconstructionFailed("DA3 needs at least three extracted views.")
        request.output_dir.mkdir(parents=True, exist_ok=True)

        on_progress(0.12, f"Reconstructing {len(selected)} views at {resolution}px")
        retried = False
        try:
            self._infer(selected, request.output_dir, resolution)
        except torch.OutOfMemoryError:
            if device != "cuda" or len(selected) <= 4:
                raise
            retried = True
            torch.cuda.empty_cache()
            gc.collect()
            selected = _evenly_spaced(selected, max(4, len(selected) // 2))
            resolution = min(resolution, 336)
            on_progress(
                0.2,
                f"VRAM limit reached. Retrying safely with {len(selected)} views at {resolution}px",
            )
            self._infer(selected, request.output_dir, resolution)

        on_progress(0.92, "Indexing reconstructed geometry")
        glb_files = sorted(request.output_dir.rglob("*.glb"), key=lambda item: item.stat().st_size)
        if not glb_files:
            raise ReconstructionFailed("DA3 completed without producing a GLB artifact.")
        glb = glb_files[-1]
        metadata = {
            "model": self.model_id,
            "device": device,
            "input_views": len(selected),
            "process_resolution": resolution,
            "representation": "colored point cloud",
            "metric_scale": False,
            "retried_after_oom": retried,
        }
        metadata_path = request.output_dir / "reconstruction.json"
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return ReconstructionResult(
            backend=self.backend_id,
            artifacts=(
                artifact_from_path(
                    glb,
                    root=request.output_dir.parent,
                    name="Interactive 3D reconstruction",
                    kind="point-cloud",
                    media_type="model/gltf-binary",
                ),
                artifact_from_path(
                    metadata_path,
                    root=request.output_dir.parent,
                    name="Reconstruction manifest",
                    kind="metadata",
                    media_type="application/json",
                ),
            ),
            metadata=metadata,
            warnings=(
                "Scale is relative until the user supplies a measured reference.",
                "This output is a colored point cloud, not collision-ready geometry.",
            ),
        )

    def _infer(self, frames: list[Path], output_dir: Path, resolution: int) -> None:
        import torch

        assert self._model is not None
        with torch.inference_mode():
            self._model.inference(
                image=[str(frame) for frame in frames],
                process_res=resolution,
                process_res_method="upper_bound_resize",
                export_dir=str(output_dir),
                export_format="mini_npz-glb",
                conf_thresh_percentile=55.0,
                num_max_points=350_000,
                show_cameras=False,
                export_kwargs={},
            )


def _da3_budget(profile: CaptureProfile, vram_gb: float | None) -> tuple[int, int]:
    budgets = {
        CaptureProfile.FAST: (8, 336),
        CaptureProfile.BALANCED: (12, 392),
        CaptureProfile.QUALITY: (18, 504),
    }
    frame_limit, resolution = budgets[profile]
    if vram_gb is not None and vram_gb < 6:
        frame_limit = min(frame_limit, 8)
        resolution = min(resolution, 336)
    return frame_limit, resolution


def _evenly_spaced(items: list[Path], count: int) -> list[Path]:
    if count >= len(items):
        return items
    if count <= 1:
        return items[:count]
    indices = [round(index * (len(items) - 1) / (count - 1)) for index in range(count)]
    return [items[index] for index in indices]
