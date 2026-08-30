from __future__ import annotations

import json
from pathlib import Path

from kinetiweave.capture import extract_frames, probe_video
from kinetiweave.domain import CaptureProfile


def test_probe_and_extract_fast_profile(orbit_video: Path, tmp_path: Path) -> None:
    probe = probe_video(orbit_video, max_duration_seconds=20)
    assert probe.width == 640
    assert probe.height == 480
    assert 5.9 < probe.duration_seconds < 6.1

    report = extract_frames(
        orbit_video,
        tmp_path / "job" / "frames",
        CaptureProfile.FAST,
        max_duration_seconds=20,
    )
    assert report.selected_frames == 12
    assert report.median_sharpness > 0
    assert len(report.frames) == 12
    assert [item.source_index for item in report.frames] == sorted(
        item.source_index for item in report.frames
    )
    manifest = json.loads((tmp_path / "job" / "capture.json").read_text())
    assert manifest["selected_frames"] == 12
