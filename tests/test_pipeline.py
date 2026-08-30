from __future__ import annotations

from pathlib import Path

from kinetiweave.backends.base import (
    ReconstructionBackend,
    ReconstructionResult,
    artifact_from_path,
)
from kinetiweave.config import Settings
from kinetiweave.domain import BackendChoice, CaptureProfile, JobStatus
from kinetiweave.jobs import JobStore
from kinetiweave.pipeline import PipelineService


class FakeBackend(ReconstructionBackend):
    backend_id = "test-reconstructor"

    def available(self) -> bool:
        return True

    def reconstruct(self, request, on_progress) -> ReconstructionResult:
        request.output_dir.mkdir(parents=True)
        output = request.output_dir / "reconstruction.glb"
        output.write_bytes(b"glTF-test")
        on_progress(0.8, "Creating test geometry")
        return ReconstructionResult(
            backend=self.backend_id,
            artifacts=(
                artifact_from_path(
                    output,
                    root=request.output_dir.parent,
                    name="Test geometry",
                    kind="point-cloud",
                    media_type="model/gltf-binary",
                ),
            ),
            metadata={"representation": "test point cloud"},
            warnings=("Test warning",),
        )


def test_pipeline_success_with_backend(orbit_video: Path, tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data")
    settings.ensure_directories()
    job_id = "pipeline-job"
    input_dir = settings.jobs_dir / job_id / "input"
    input_dir.mkdir(parents=True)
    input_video = input_dir / "capture.avi"
    input_video.write_bytes(orbit_video.read_bytes())
    store = JobStore(settings.database_path)
    store.create(
        job_id=job_id,
        input_name="orbit.avi",
        input_path=input_video,
        profile=CaptureProfile.FAST,
        backend=BackendChoice.DA3,
    )
    service = PipelineService(
        settings,
        store,
        backends={"da3": FakeBackend(), "colmap": FakeBackend()},
    )
    service.run(job_id)
    service.shutdown()

    job = store.get(job_id)
    assert job.status == JobStatus.SUCCEEDED
    assert job.backend_used == "test-reconstructor"
    assert job.artifacts[0].relative_path == "output/reconstruction.glb"
    assert job.metadata["capture"]["selected_frames"] == 12
    assert job.metadata["warnings"] == ["Test warning"]
