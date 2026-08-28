from __future__ import annotations

import json
import logging
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from typing import Any

from kinetiweave.backends import ColmapBackend, Da3Backend, ReconstructionBackend
from kinetiweave.backends.base import (
    BackendUnavailable,
    ReconstructionFailed,
    ReconstructionRequest,
    artifact_from_path,
)
from kinetiweave.capture import VideoValidationError, extract_frames
from kinetiweave.catalog import CatalogService, CatalogStore
from kinetiweave.config import Settings
from kinetiweave.domain import BackendChoice, JobStage, JobStatus
from kinetiweave.jobs import JobStore
from kinetiweave.system import detect_capabilities

LOGGER = logging.getLogger("kinetiweave.pipeline")


class PipelineService:
    def __init__(
        self,
        settings: Settings,
        store: JobStore,
        backends: dict[str, ReconstructionBackend] | None = None,
        catalog: CatalogService | None = None,
    ) -> None:
        self.settings = settings
        self.store = store
        self.catalog = catalog or CatalogService(settings, CatalogStore(settings.database_path))
        self.capabilities = detect_capabilities()
        self.backends = backends or {"da3": Da3Backend(), "colmap": ColmapBackend()}
        self.executor = ThreadPoolExecutor(
            max_workers=settings.max_workers, thread_name_prefix="kinetiweave-reconstruction"
        )
        self._recover_interrupted_jobs()
        self._backfill_catalog()

    def submit(self, job_id: str) -> None:
        self.executor.submit(self.run, job_id)

    def run(self, job_id: str) -> None:
        job = self.store.get(job_id)
        job_root = self.settings.jobs_dir / job_id
        frames_dir = job_root / "frames"
        output_dir = job_root / "output"
        try:
            self.store.update(
                job_id,
                status=JobStatus.RUNNING,
                stage=JobStage.INSPECTING,
                progress=0.02,
                message="Inspecting the uploaded video.",
                error_code=None,
                error_detail=None,
            )
            report = extract_frames(
                Path(job.input_path),
                frames_dir,
                job.profile,
                self.settings.max_video_seconds,
                on_progress=lambda progress, message: self._progress(
                    job_id,
                    JobStage.EXTRACTING,
                    0.03 + progress * 0.25,
                    message,
                ),
            )
            metadata: dict[str, Any] = {"capture": asdict(report)}
            self.store.set_metadata(job_id, metadata)

            backend_key, backend = self._select_backend(job.backend_requested)
            completed = self.store.update(
                job_id,
                stage=JobStage.RECONSTRUCTING,
                progress=0.3,
                message=f"Starting {backend.backend_id} reconstruction.",
                backend_used=backend.backend_id,
            )
            result = backend.reconstruct(
                ReconstructionRequest(
                    frames_dir=frames_dir,
                    output_dir=output_dir,
                    profile=job.profile,
                    gpu_vram_gb=self.capabilities.gpu_vram_gb,
                ),
                on_progress=lambda progress, message: self._progress(
                    job_id,
                    JobStage.RECONSTRUCTING,
                    0.3 + progress * 0.62,
                    message,
                ),
            )
            try:
                self.catalog.register_reconstruction(completed)
            except Exception:
                LOGGER.exception("Could not register reconstructed asset for job %s", job_id)
            metadata["reconstruction"] = result.metadata
            metadata["warnings"] = [*report.warnings, *result.warnings]
            metadata["backend_key"] = backend_key
            manifest_path = job_root / "job-manifest.json"
            manifest_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
            self.store.set_metadata(job_id, metadata)
            job_manifest = artifact_from_path(
                manifest_path,
                root=job_root,
                name="Job provenance manifest",
                kind="metadata",
                media_type="application/json",
            )
            self.store.set_artifacts(job_id, (*result.artifacts, job_manifest))
            self.store.update(
                job_id,
                status=JobStatus.SUCCEEDED,
                stage=JobStage.COMPLETE,
                progress=1.0,
                message=(
                    "Reconstruction complete. Inspect the geometry before using it for physics."
                ),
            )
        except VideoValidationError as exc:
            self._fail(job_id, "KW_VIDEO_INVALID", str(exc))
        except BackendUnavailable as exc:
            self._fail(job_id, "KW_BACKEND_UNAVAILABLE", str(exc))
        except ReconstructionFailed as exc:
            self._fail(job_id, "KW_RECONSTRUCTION_FAILED", str(exc))
        except Exception as exc:  # keep background failures visible to the user
            LOGGER.exception("Unexpected reconstruction failure for job %s", job_id)
            self._fail(job_id, "KW_INTERNAL_ERROR", str(exc), traceback.format_exc())

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)

    def _select_backend(self, requested: BackendChoice) -> tuple[str, ReconstructionBackend]:
        if requested != BackendChoice.AUTO:
            backend = self.backends[requested.value]
            if not backend.available():
                raise BackendUnavailable(f"Requested backend '{requested.value}' is not available.")
            return requested.value, backend
        for key in ("da3", "colmap"):
            backend = self.backends[key]
            if backend.available():
                return key, backend
        raise BackendUnavailable(
            "No reconstruction backend is available. Install DA3 Small or configure COLMAP."
        )

    def _progress(self, job_id: str, stage: JobStage, progress: float, message: str) -> None:
        self.store.update(
            job_id,
            stage=stage,
            progress=min(max(progress, 0), 0.99),
            message=message,
        )

    def _fail(self, job_id: str, code: str, detail: str, diagnostic: str | None = None) -> None:
        self.store.update(
            job_id,
            status=JobStatus.FAILED,
            progress=1.0,
            message="Reconstruction stopped. Review the diagnostic and capture guidance.",
            error_code=code,
            error_detail=detail,
        )
        if diagnostic:
            job_root = self.settings.jobs_dir / job_id
            (job_root / "error.log").write_text(diagnostic, encoding="utf-8")

    def _recover_interrupted_jobs(self) -> None:
        for job in self.store.list(limit=100):
            if job.status == JobStatus.RUNNING:
                self.store.update(
                    job.id,
                    status=JobStatus.FAILED,
                    progress=1.0,
                    message="The previous local process stopped before this job completed.",
                    error_code="KW_PROCESS_INTERRUPTED",
                    error_detail="Re-submit the original video to start a clean reconstruction.",
                )

    def _backfill_catalog(self) -> None:
        for job in self.store.list(limit=100):
            if job.status != JobStatus.SUCCEEDED:
                continue
            try:
                self.catalog.register_reconstruction(job)
            except Exception:
                LOGGER.exception("Could not backfill reconstructed asset for job %s", job.id)
