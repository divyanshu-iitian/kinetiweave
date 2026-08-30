from __future__ import annotations

from pathlib import Path

import trimesh
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


def test_object_import_and_environment_api(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data"))
    mesh_path = tmp_path / "part.stl"
    trimesh.creation.icosphere(subdivisions=1).export(mesh_path)
    with TestClient(app) as client:
        imported = client.post(
            "/api/assets/import",
            files={"geometry": ("part.stl", mesh_path.read_bytes(), "model/stl")},
        )
        assert imported.status_code == 201
        asset = imported.json()
        assert client.get(f"/api/assets/{asset['id']}/geometry").status_code == 200

        created = client.post(
            "/api/environments",
            json={
                "asset_id": asset["id"],
                "name": "Sphere stability",
                "task_template": "stabilize",
                "mass_kg": 0.2,
                "target_size_m": 0.1,
                "max_episode_steps": 100,
            },
        )
        assert created.status_code == 201
        environment = created.json()
        assert environment["status"] == "ready"
        assert environment["validation"]["status"] == "passed"
        validated = client.post(f"/api/environments/{environment['id']}/validate")
        assert validated.status_code == 200
        assert validated.json()["validation"]["finite_rollout"] is True
        package = client.get(f"/api/environments/{environment['id']}/package")
        assert package.status_code == 200
        assert package.headers["content-type"] == "application/zip"
