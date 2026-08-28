from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest


@pytest.fixture
def orbit_video(tmp_path: Path) -> Path:
    path = tmp_path / "orbit.avi"
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"MJPG"),
        12.0,
        (640, 480),
    )
    assert writer.isOpened()
    for index in range(72):
        frame = np.full((480, 640, 3), 28, dtype=np.uint8)
        x = 150 + index * 4
        cv2.rectangle(frame, (x, 150), (x + 110, 320), (220, 135, 45), -1)
        cv2.line(frame, (x, 150), (x + 110, 320), (255, 255, 255), 4)
        cv2.putText(
            frame,
            str(index),
            (x + 25, 245),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (10, 10, 10),
            2,
        )
        writer.write(frame)
    writer.release()
    return path
