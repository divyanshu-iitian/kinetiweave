from __future__ import annotations

import importlib
import sys
from pathlib import Path

import gymnasium as gym
import mujoco
import numpy as np
import trimesh

from kinetiweave.catalog import CatalogService, CatalogStore
from kinetiweave.config import Settings
from kinetiweave.domain import EnvironmentCreate, EnvironmentStatus, TaskTemplate


def test_import_and_generate_runnable_rl_environment(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data")
    settings.ensure_directories()
    service = CatalogService(settings, CatalogStore(settings.database_path))
    source = tmp_path / "calibration-block.stl"
    trimesh.creation.box(extents=(2.0, 1.0, 0.5)).export(source)

    asset = service.import_geometry(source, "calibration-block.stl")

    assert asset.geometry_kind.value == "mesh"
    assert asset.vertex_count == 8
    assert asset.face_count == 12
    assert asset.rl_eligible
    assert Path(asset.visual_path).is_file()

    environment = service.create_environment(
        EnvironmentCreate(
            asset_id=asset.id,
            name="Block Stabilization",
            task_template=TaskTemplate.STABILIZE,
            mass_kg=0.4,
            target_size_m=0.2,
            max_episode_steps=250,
        )
    )

    assert environment.status is EnvironmentStatus.READY
    assert environment.package_path is not None
    assert Path(environment.package_path).is_file()
    assert environment.metadata["method"] == "convex-hull"

    package_name = f"kinetiweave_env_{environment.id[:8]}"
    project_root = settings.environments_dir / environment.id / package_name
    model_path = project_root / package_name / "assets" / "model.xml"
    assert (project_root / package_name / "assets" / "visual.glb").is_file()
    manifest_text = (project_root / "manifest.json").read_text(encoding="utf-8")
    assert "original_path" not in manifest_text
    assert "visual_path" not in manifest_text
    model = mujoco.MjModel.from_xml_path(str(model_path))
    assert model.nq == 7

    sys.path.insert(0, str(project_root))
    try:
        importlib.import_module(package_name)
        rl_env = gym.make(environment.gymnasium_id)
        observation, info = rl_env.reset(seed=7)
        assert observation.shape == (16,)
        assert np.isfinite(observation).all()
        assert "distance_to_target" in info
        next_observation, reward, terminated, truncated, _ = rl_env.step(
            np.zeros(3, dtype=np.float32)
        )
        assert next_observation.shape == (16,)
        assert np.isfinite(reward)
        assert isinstance(terminated, bool)
        assert isinstance(truncated, bool)
        rl_env.close()
    finally:
        sys.path.remove(str(project_root))
