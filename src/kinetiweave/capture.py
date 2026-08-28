from __future__ import annotations

import json
import math
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np

from kinetiweave.domain import CaptureProfile


class VideoValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class VideoProbe:
    width: int
    height: int
    fps: float
    frame_count: int
    duration_seconds: float


@dataclass(frozen=True, slots=True)
class FrameMetric:
    name: str
    source_index: int
    timestamp_seconds: float
    sharpness: float


@dataclass(frozen=True, slots=True)
class CaptureReport:
    probe: VideoProbe
    selected_frames: int
    median_sharpness: float
    median_motion_px: float | None
    warnings: tuple[str, ...]
    frames: tuple[FrameMetric, ...]


PROFILE_CONFIG = {
    CaptureProfile.FAST: {"frames": 12, "max_edge": 960},
    CaptureProfile.BALANCED: {"frames": 24, "max_edge": 1280},
    CaptureProfile.QUALITY: {"frames": 40, "max_edge": 1600},
}


def probe_video(path: Path, max_duration_seconds: float) -> VideoProbe:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise VideoValidationError("The uploaded file is not a readable video.")
    try:
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    finally:
        capture.release()

    if width < 320 or height < 240:
        raise VideoValidationError("Video resolution must be at least 320 x 240.")
    if not math.isfinite(fps) or fps <= 0 or frame_count < 8:
        raise VideoValidationError("Video timing metadata is invalid or the clip is too short.")
    duration = frame_count / fps
    if duration > max_duration_seconds:
        raise VideoValidationError(
            f"Video is {duration:.1f}s. The local limit is {max_duration_seconds:.0f}s."
        )
    return VideoProbe(width, height, fps, frame_count, duration)


def extract_frames(
    video_path: Path,
    frames_dir: Path,
    profile: CaptureProfile,
    max_duration_seconds: float,
    on_progress: Callable[[float, str], None] | None = None,
) -> CaptureReport:
    config = PROFILE_CONFIG[profile]
    target_count = int(config["frames"])
    max_edge = int(config["max_edge"])
    probe = probe_video(video_path, max_duration_seconds)
    frames_dir.mkdir(parents=True, exist_ok=True)

    candidate_count = min(probe.frame_count, max(target_count * 4, target_count))
    start = max(0, int(probe.frame_count * 0.02))
    stop = min(probe.frame_count - 1, int(probe.frame_count * 0.98))
    indices = np.linspace(start, stop, candidate_count, dtype=int)

    capture = cv2.VideoCapture(str(video_path))
    candidates: list[tuple[int, np.ndarray, float]] = []
    try:
        for position, frame_index in enumerate(indices):
            capture.set(cv2.CAP_PROP_POS_FRAMES, int(frame_index))
            ok, frame = capture.read()
            if not ok or frame is None:
                continue
            frame = _resize(frame, max_edge)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            candidates.append((int(frame_index), frame, sharpness))
            if on_progress:
                on_progress((position + 1) / max(candidate_count, 1) * 0.55, "Reading video frames")
    finally:
        capture.release()

    if len(candidates) < min(8, target_count):
        raise VideoValidationError("Too few decodable frames were found in the video.")

    selected = _select_sharp_coverage(candidates, min(target_count, len(candidates)))
    metrics: list[FrameMetric] = []
    written_gray: list[np.ndarray] = []
    for position, (source_index, frame, sharpness) in enumerate(selected):
        name = f"frame_{position:04d}.jpg"
        destination = frames_dir / name
        if not cv2.imwrite(str(destination), frame, [cv2.IMWRITE_JPEG_QUALITY, 94]):
            raise OSError(f"Could not write extracted frame: {destination}")
        metrics.append(
            FrameMetric(
                name=name,
                source_index=source_index,
                timestamp_seconds=source_index / probe.fps,
                sharpness=round(sharpness, 3),
            )
        )
        written_gray.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
        if on_progress:
            on_progress(0.55 + (position + 1) / len(selected) * 0.45, "Saving sharp views")

    sharpness_values = [item.sharpness for item in metrics]
    motion = _median_motion(written_gray)
    warnings: list[str] = []
    if float(np.median(sharpness_values)) < 55:
        warnings.append("Many views are soft. Use brighter light and move more slowly.")
    if motion is not None and motion < 2.0:
        warnings.append("Camera movement is very low. Walk around the object instead of zooming.")
    if motion is not None and motion > 85:
        warnings.append(
            "Frame-to-frame movement is high. Capture a slower orbit with more overlap."
        )
    if probe.duration_seconds < 4:
        warnings.append(
            "The orbit is short. A 15-40 second capture usually gives stronger coverage."
        )

    report = CaptureReport(
        probe=probe,
        selected_frames=len(metrics),
        median_sharpness=round(float(np.median(sharpness_values)), 3),
        median_motion_px=None if motion is None else round(motion, 3),
        warnings=tuple(warnings),
        frames=tuple(metrics),
    )
    (frames_dir.parent / "capture.json").write_text(
        json.dumps(asdict(report), indent=2), encoding="utf-8"
    )
    return report


def _resize(frame: np.ndarray, max_edge: int) -> np.ndarray:
    height, width = frame.shape[:2]
    scale = min(1.0, max_edge / max(height, width))
    if scale == 1.0:
        return frame
    return cv2.resize(
        frame,
        (max(1, round(width * scale)), max(1, round(height * scale))),
        interpolation=cv2.INTER_AREA,
    )


def _select_sharp_coverage(
    candidates: list[tuple[int, np.ndarray, float]], target_count: int
) -> list[tuple[int, np.ndarray, float]]:
    bins = np.array_split(np.arange(len(candidates)), target_count)
    selected: list[tuple[int, np.ndarray, float]] = []
    for group in bins:
        if len(group) == 0:
            continue
        best_index = max(group, key=lambda index: candidates[int(index)][2])
        selected.append(candidates[int(best_index)])
    return selected


def _median_motion(frames: list[np.ndarray]) -> float | None:
    medians: list[float] = []
    for first, second in zip(frames, frames[1:], strict=False):
        points = cv2.goodFeaturesToTrack(first, maxCorners=300, qualityLevel=0.01, minDistance=8)
        if points is None or len(points) < 12:
            continue
        tracked, status, _ = cv2.calcOpticalFlowPyrLK(first, second, points, None)
        if tracked is None or status is None:
            continue
        valid = status.reshape(-1) == 1
        if int(valid.sum()) < 8:
            continue
        displacement = np.linalg.norm(tracked[valid] - points[valid], axis=2)
        medians.append(float(np.median(displacement)))
    if not medians:
        return None
    return float(np.median(medians))
