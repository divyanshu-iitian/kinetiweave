from __future__ import annotations

import json
import re
import shutil
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

import numpy as np
import trimesh

from kinetiweave.config import Settings
from kinetiweave.domain import (
    AssetRecord,
    AssetSource,
    EnvironmentCreate,
    EnvironmentRecord,
    EnvironmentStatus,
    GeometryKind,
    JobRecord,
    utc_now,
)


class AssetImportError(ValueError):
    pass


class EnvironmentBuildError(ValueError):
    pass


class CatalogStore:
    """Durable asset and environment catalog stored beside reconstruction jobs."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS assets (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    source_job_id TEXT,
                    record_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS assets_source_job_idx
                ON assets(source_job_id) WHERE source_job_id IS NOT NULL
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS assets_created_idx ON assets(created_at DESC)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS environments (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    asset_id TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    FOREIGN KEY(asset_id) REFERENCES assets(id)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS environments_created_idx "
                "ON environments(created_at DESC)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS environments_asset_idx ON environments(asset_id)"
            )

    def put_asset(self, asset: AssetRecord) -> AssetRecord:
        payload = asset.model_dump_json()
        with self._write_lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO assets (id, created_at, updated_at, source_job_id, record_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    updated_at = excluded.updated_at,
                    source_job_id = excluded.source_job_id,
                    record_json = excluded.record_json
                """,
                (
                    asset.id,
                    asset.created_at.isoformat(),
                    asset.updated_at.isoformat(),
                    asset.source_job_id,
                    payload,
                ),
            )
        return asset

    def get_asset(self, asset_id: str) -> AssetRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT record_json FROM assets WHERE id = ?", (asset_id,)
            ).fetchone()
        if row is None:
            raise KeyError(asset_id)
        return AssetRecord.model_validate_json(row["record_json"])

    def get_asset_for_job(self, job_id: str) -> AssetRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT record_json FROM assets WHERE source_job_id = ?", (job_id,)
            ).fetchone()
        return None if row is None else AssetRecord.model_validate_json(row["record_json"])

    def list_assets(self, limit: int = 100) -> list[AssetRecord]:
        safe_limit = min(max(limit, 1), 250)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT record_json FROM assets ORDER BY created_at DESC LIMIT ?",
                (safe_limit,),
            ).fetchall()
        return [AssetRecord.model_validate_json(row["record_json"]) for row in rows]

    def put_environment(self, environment: EnvironmentRecord) -> EnvironmentRecord:
        payload = environment.model_dump_json()
        with self._write_lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO environments (id, created_at, updated_at, asset_id, record_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    updated_at = excluded.updated_at,
                    asset_id = excluded.asset_id,
                    record_json = excluded.record_json
                """,
                (
                    environment.id,
                    environment.created_at.isoformat(),
                    environment.updated_at.isoformat(),
                    environment.asset_id,
                    payload,
                ),
            )
        return environment

    def get_environment(self, environment_id: str) -> EnvironmentRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT record_json FROM environments WHERE id = ?", (environment_id,)
            ).fetchone()
        if row is None:
            raise KeyError(environment_id)
        return EnvironmentRecord.model_validate_json(row["record_json"])

    def list_environments(self, limit: int = 100) -> list[EnvironmentRecord]:
        safe_limit = min(max(limit, 1), 250)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT record_json FROM environments ORDER BY created_at DESC LIMIT ?",
                (safe_limit,),
            ).fetchall()
        return [EnvironmentRecord.model_validate_json(row["record_json"]) for row in rows]


class CatalogService:
    def __init__(self, settings: Settings, store: CatalogStore) -> None:
        self.settings = settings
        self.store = store

    def register_reconstruction(self, job: JobRecord) -> AssetRecord | None:
        existing = self.store.get_asset_for_job(job.id)
        if existing is not None:
            return existing
        artifact = next(
            (
                item
                for item in job.artifacts
                if item.media_type == "model/gltf-binary" and item.kind in {"mesh", "point-cloud"}
            ),
            None,
        )
        if artifact is None:
            return None
        visual_path = (self.settings.jobs_dir / job.id / artifact.relative_path).resolve()
        if not visual_path.is_file():
            return None
        stats = _inspect_geometry(visual_path)
        now = utc_now()
        asset = AssetRecord(
            id=uuid.uuid5(uuid.NAMESPACE_URL, f"kinetiweave:job:{job.id}").hex,
            created_at=job.created_at,
            updated_at=now,
            name=Path(job.input_name).stem[:80] or "Captured object",
            source=AssetSource.CAPTURE,
            source_job_id=job.id,
            source_filename=job.input_name,
            original_path=job.input_path,
            visual_path=str(visual_path),
            geometry_kind=(
                GeometryKind.POINT_CLOUD if artifact.kind == "point-cloud" else GeometryKind.MESH
            ),
            size_bytes=visual_path.stat().st_size,
            vertex_count=stats["vertex_count"],
            face_count=stats["face_count"],
            dimensions_model=stats["dimensions"],
            watertight=stats["watertight"],
            rl_eligible=stats["rl_eligible"],
            warnings=[
                "Physical scale is unknown until you provide one measured dimension.",
                *(
                    [
                        "Captured geometry is a point cloud; RL export uses a "
                        "conservative convex hull."
                    ]
                    if artifact.kind == "point-cloud"
                    else []
                ),
            ],
            metadata={
                "backend": job.backend_used,
                "capture_profile": job.profile.value,
                "job_warnings": job.metadata.get("warnings", []),
            },
        )
        return self.store.put_asset(asset)

    def import_geometry(self, source_path: Path, original_name: str) -> AssetRecord:
        suffix = source_path.suffix.lower()
        asset_id = uuid.uuid4().hex
        asset_root = self.settings.assets_dir / asset_id
        asset_root.mkdir(parents=True, exist_ok=False)
        original_path = asset_root / f"original{suffix}"
        try:
            shutil.move(str(source_path), original_path)
            scene = _load_scene(original_path)
            stats = _inspect_scene(scene)
            visual_path = asset_root / "visual.glb"
            visual_path.write_bytes(scene.export(file_type="glb"))
        except Exception as exc:
            shutil.rmtree(asset_root, ignore_errors=True)
            raise AssetImportError(f"Could not import {suffix or 'this'} geometry: {exc}") from exc

        now = utc_now()
        kind = (
            GeometryKind.CAD
            if suffix in {".step", ".stp"}
            else (GeometryKind.MESH if stats["face_count"] else GeometryKind.POINT_CLOUD)
        )
        warnings = ["Confirm one real-world dimension before generating an RL environment."]
        if stats["face_count"] == 0:
            warnings.append("Point-only geometry will use a conservative convex collision proxy.")
        if stats["watertight"] is False:
            warnings.append(
                "The imported mesh is not watertight; collision export uses its convex hull."
            )
        asset = AssetRecord(
            id=asset_id,
            created_at=now,
            updated_at=now,
            name=Path(original_name).stem[:80] or "Imported object",
            source=AssetSource.IMPORT,
            source_filename=Path(original_name).name,
            original_path=str(original_path.resolve()),
            visual_path=str(visual_path.resolve()),
            geometry_kind=kind,
            size_bytes=visual_path.stat().st_size,
            vertex_count=stats["vertex_count"],
            face_count=stats["face_count"],
            dimensions_model=stats["dimensions"],
            watertight=stats["watertight"],
            rl_eligible=stats["rl_eligible"],
            warnings=warnings,
            metadata={"source_format": suffix.removeprefix(".")},
        )
        return self.store.put_asset(asset)

    def create_environment(self, request: EnvironmentCreate) -> EnvironmentRecord:
        asset = self.store.get_asset(request.asset_id)
        environment_id = uuid.uuid4().hex
        now = utc_now()
        longest_edge = max(asset.dimensions_model)
        errors: list[str] = []
        if not asset.rl_eligible:
            errors.append("Geometry does not contain enough valid 3D points for a collision proxy.")
        if longest_edge <= 0:
            errors.append("Geometry bounds are degenerate and cannot be scaled.")
        scale = request.target_size_m / longest_edge if longest_edge > 0 else 1.0
        slug = _slug(request.name) or f"object-{environment_id[:8]}"
        record = EnvironmentRecord(
            id=environment_id,
            created_at=now,
            updated_at=now,
            name=request.name.strip(),
            asset_id=asset.id,
            status=EnvironmentStatus.BLOCKED if errors else EnvironmentStatus.DRAFT,
            task_template=request.task_template,
            gymnasium_id=f"KinetiWeave/{_pascal_slug(slug)}-v0",
            max_episode_steps=request.max_episode_steps,
            mass_kg=request.mass_kg,
            target_size_m=request.target_size_m,
            scale_to_meters=scale,
            validation_errors=errors,
            metadata={"source_geometry_kind": asset.geometry_kind.value},
        )
        self.store.put_environment(record)
        if errors:
            return record
        try:
            package_path, build_metadata = self._build_environment_package(record, asset)
        except Exception as exc:
            failed = record.model_copy(
                update={
                    "updated_at": utc_now(),
                    "status": EnvironmentStatus.BLOCKED,
                    "validation_errors": [f"Environment package generation failed: {exc}"],
                }
            )
            return self.store.put_environment(failed)
        ready = record.model_copy(
            update={
                "updated_at": utc_now(),
                "status": EnvironmentStatus.READY,
                "package_path": str(package_path),
                "metadata": {**record.metadata, **build_metadata},
            }
        )
        return self.store.put_environment(ready)

    def _build_environment_package(
        self, environment: EnvironmentRecord, asset: AssetRecord
    ) -> tuple[Path, dict[str, Any]]:
        env_root = self.settings.environments_dir / environment.id
        package_name = f"kinetiweave_env_{environment.id[:8]}"
        project_root = env_root / package_name
        module_root = project_root / package_name
        assets_root = module_root / "assets"
        assets_root.mkdir(parents=True, exist_ok=False)

        scene = _load_scene(Path(asset.visual_path))
        points = _scene_points(scene)
        if len(points) > 50_000:
            indices = np.linspace(0, len(points) - 1, 50_000, dtype=int)
            points = points[indices]
        hull = trimesh.points.PointCloud(points).convex_hull
        hull.apply_translation(-hull.centroid)
        hull.apply_scale(environment.scale_to_meters)
        collision_path = assets_root / "collision.stl"
        hull.export(collision_path)
        shutil.copy2(asset.visual_path, assets_root / "visual.glb")
        half_height = float(max(abs(hull.bounds[0, 2]), abs(hull.bounds[1, 2])))
        spawn_z = half_height + 0.015

        model_xml = _mujoco_xml(
            environment.name,
            environment.mass_kg,
            spawn_z,
        )
        (assets_root / "model.xml").write_text(model_xml, encoding="utf-8")
        (module_root / "__init__.py").write_text(
            _package_init(environment, package_name), encoding="utf-8"
        )
        (module_root / "env.py").write_text(
            _environment_module(environment, spawn_z), encoding="utf-8"
        )
        (project_root / "pyproject.toml").write_text(
            _environment_pyproject(package_name), encoding="utf-8"
        )
        (project_root / "README.md").write_text(
            _environment_readme(environment, asset, package_name), encoding="utf-8"
        )
        manifest = {
            "environment": environment.model_dump(mode="json", exclude={"package_path"}),
            "asset": asset.model_dump(mode="json", exclude={"original_path", "visual_path"}),
            "collision_proxy": {
                "method": "convex-hull",
                "vertices": int(len(hull.vertices)),
                "faces": int(len(hull.faces)),
                "watertight": bool(hull.is_watertight),
                "spawn_height_m": spawn_z,
            },
        }
        (project_root / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        archive_base = env_root / package_name
        archive = Path(shutil.make_archive(str(archive_base), "zip", env_root, package_name))
        return archive, manifest["collision_proxy"]


def _load_scene(path: Path) -> trimesh.Scene:
    loaded = trimesh.load_scene(path, process=False)
    if not isinstance(loaded, trimesh.Scene):
        loaded = trimesh.Scene(loaded)
    if not loaded.geometry:
        raise AssetImportError("No 3D geometry was found in the file.")
    return loaded


def _scene_points(scene: trimesh.Scene) -> np.ndarray:
    points: list[np.ndarray] = []
    for node_name in scene.graph.nodes_geometry:
        transform, geometry_name = scene.graph[node_name]
        geometry = scene.geometry[geometry_name]
        if not hasattr(geometry, "vertices") or len(geometry.vertices) == 0:
            continue
        points.append(trimesh.transform_points(np.asarray(geometry.vertices), transform))
    if not points:
        raise AssetImportError("No finite 3D vertices were found in the geometry.")
    combined = np.vstack(points)
    combined = combined[np.isfinite(combined).all(axis=1)]
    if len(combined) < 4:
        raise AssetImportError("At least four finite 3D vertices are required.")
    return combined


def _inspect_geometry(path: Path) -> dict[str, Any]:
    return _inspect_scene(_load_scene(path))


def _inspect_scene(scene: trimesh.Scene) -> dict[str, Any]:
    points = _scene_points(scene)
    dimensions = np.ptp(points, axis=0)
    face_count = 0
    vertex_count = 0
    mesh_watertight: list[bool] = []
    for geometry in scene.geometry.values():
        faces = getattr(geometry, "faces", None)
        if faces is not None and len(faces):
            mesh = geometry.copy()
            mesh.merge_vertices()
            face_count += int(len(faces))
            vertex_count += int(len(mesh.vertices))
            mesh_watertight.append(bool(mesh.is_watertight))
        else:
            vertex_count += int(len(getattr(geometry, "vertices", ())))
    return {
        "vertex_count": vertex_count,
        "face_count": face_count,
        "dimensions": tuple(float(value) for value in dimensions),
        "watertight": all(mesh_watertight) if mesh_watertight else None,
        "rl_eligible": bool(
            len(points) >= 4 and np.isfinite(dimensions).all() and max(dimensions) > 0
        ),
    }


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:48]


def _pascal_slug(value: str) -> str:
    return "".join(part.capitalize() for part in value.split("-") if part) or "Object"


def _mujoco_xml(name: str, mass_kg: float, spawn_z: float) -> str:
    safe_name = escape(name)
    return f"""<mujoco model="{safe_name}">
  <compiler angle="radian" meshdir="."/>
  <option timestep="0.01" gravity="0 0 -9.81"/>
  <asset>
    <mesh name="object_collision" file="collision.stl"/>
  </asset>
  <worldbody>
    <light pos="1 -1 3" diffuse="0.8 0.8 0.8"/>
    <geom name="ground" type="plane" size="2 2 0.1" rgba="0.16 0.17 0.15 1"/>
    <body name="object" pos="0 0 {spawn_z:.8f}">
      <freejoint name="object_free"/>
      <geom name="object_geom" type="mesh" mesh="object_collision" mass="{mass_kg:.8f}"
            friction="0.8 0.02 0.002" rgba="0.82 0.36 0.08 1"/>
    </body>
    <site name="target" pos="0.35 0 0.02" size="0.035" rgba="0.2 0.8 0.4 0.8"/>
  </worldbody>
</mujoco>
"""


def _package_init(environment: EnvironmentRecord, package_name: str) -> str:
    return f'''from gymnasium.envs.registration import register

register(
    id="{environment.gymnasium_id}",
    entry_point="{package_name}.env:KinetiWeaveObjectEnv",
    max_episode_steps={environment.max_episode_steps},
)
'''


def _environment_module(environment: EnvironmentRecord, spawn_z: float) -> str:
    task = environment.task_template.value
    return f'''from __future__ import annotations

from pathlib import Path

import gymnasium as gym
import mujoco
import numpy as np
from gymnasium import spaces


class KinetiWeaveObjectEnv(gym.Env):
    """Generated MuJoCo environment with explicit provenance in manifest.json."""

    metadata = {{"render_modes": []}}

    def __init__(self):
        model_path = Path(__file__).with_name("assets") / "model.xml"
        self.model = mujoco.MjModel.from_xml_path(str(model_path))
        self.data = mujoco.MjData(self.model)
        self.body_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, "object")
        self.task = "{task}"
        self.spawn_z = {spawn_z:.8f}
        self.target = np.array([0.35, 0.0, self.spawn_z], dtype=np.float64)
        self.frame_skip = 5
        self.force_scale = {environment.mass_kg:.8f} * 9.81
        self.action_space = spaces.Box(-1.0, 1.0, shape=(3,), dtype=np.float32)
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(16,), dtype=np.float64
        )

    def _observation(self):
        return np.concatenate((self.data.qpos.copy(), self.data.qvel.copy(), self.target))

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        mujoco.mj_resetData(self.model, self.data)
        self.data.qpos[:3] = [0.0, 0.0, self.spawn_z]
        self.data.qpos[3:7] = [1.0, 0.0, 0.0, 0.0]
        self.data.qpos[:2] += self.np_random.uniform(-0.025, 0.025, size=2)
        mujoco.mj_forward(self.model, self.data)
        return self._observation(), self._info()

    def step(self, action):
        action = np.clip(np.asarray(action, dtype=np.float64), -1.0, 1.0)
        self.data.xfrc_applied[self.body_id, :3] = action * self.force_scale
        mujoco.mj_step(self.model, self.data, nstep=self.frame_skip)
        self.data.xfrc_applied[self.body_id] = 0.0
        position = self.data.qpos[:3]
        distance = float(np.linalg.norm(position[:2] - self.target[:2]))
        rotation = np.empty(9, dtype=np.float64)
        mujoco.mju_quat2Mat(rotation, self.data.qpos[3:7])
        upright = float(rotation.reshape(3, 3)[2, 2])
        control_cost = 0.01 * float(np.square(action).sum())
        if self.task == "push-to-target":
            reward = -distance - control_cost + (2.0 if distance < 0.05 else 0.0)
            success = distance < 0.05
        else:
            displacement = float(np.linalg.norm(position[:2]))
            reward = upright - 0.5 * displacement - control_cost
            success = upright > 0.9 and displacement < 0.05
        terminated = bool(position[2] < -0.05 or np.linalg.norm(position[:2]) > 2.0)
        return self._observation(), reward, terminated, False, self._info(success)

    def _info(self, success=False):
        return {{
            "success": bool(success),
            "distance_to_target": float(np.linalg.norm(self.data.qpos[:2] - self.target[:2])),
        }}

    def close(self):
        pass
'''


def _environment_pyproject(package_name: str) -> str:
    return f'''[build-system]
requires = ["hatchling>=1.27"]
build-backend = "hatchling.build"

[project]
name = "{package_name.replace("_", "-")}"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["gymnasium>=1.1,<2", "mujoco>=3.3,<4", "numpy>=1.26,<3"]

[tool.hatch.build.targets.wheel]
packages = ["{package_name}"]
'''


def _environment_readme(
    environment: EnvironmentRecord, asset: AssetRecord, package_name: str
) -> str:
    smoke_test = (
        f"import gymnasium as gym, {package_name}; "
        f'env=gym.make("{environment.gymnasium_id}"); print(env.reset()[0])'
    )
    return f"""# {environment.name}

Generated by KinetiWeave from `{asset.source_filename}`.

- Gymnasium ID: `{environment.gymnasium_id}`
- Task: `{environment.task_template.value}`
- Simulator: MuJoCo
- Mass: {environment.mass_kg:g} kg
- Longest physical dimension: {environment.target_size_m:g} m
- Collision proxy: conservative convex hull

```powershell
python -m pip install -e .
python -c '{smoke_test}'
```

This package is a generated baseline, not a validated dynamics model. Confirm scale, mass, friction,
inertia, task semantics, and reward behavior before training or publishing results.
"""
