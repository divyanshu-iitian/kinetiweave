from __future__ import annotations

from pathlib import Path

from kinetiweave.domain import BackendChoice, CaptureProfile, JobStage, JobStatus
from kinetiweave.jobs import JobStore


def test_job_store_round_trip(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "state.sqlite3")
    created = store.create(
        job_id="job-01",
        input_name="orbit.mp4",
        input_path=tmp_path / "orbit.mp4",
        profile=CaptureProfile.FAST,
        backend=BackendChoice.AUTO,
    )
    assert created.status == JobStatus.QUEUED

    updated = store.update(
        created.id,
        status=JobStatus.RUNNING,
        stage=JobStage.RECONSTRUCTING,
        progress=0.5,
        message="Solving camera positions",
    )
    assert updated.progress == 0.5
    assert store.list()[0].id == created.id
