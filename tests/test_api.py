from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from kinetiweave.api import create_app
from kinetiweave.config import Settings


def test_health_and_rejects_unknown_upload(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data"))
    with TestClient(app) as client:
        assert client.get("/api/health").json() == {
            "status": "ok",
            "scope": "local",
        }
        response = client.post(
            "/api/jobs",
            files={"video": ("capture.txt", b"not a video", "text/plain")},
        )
    assert response.status_code == 415
    assert response.json()["detail"] == "Unsupported video file extension"
