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
    PhysicsValidation,
    TaskTemplate,
    ValidationStatus,
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
            package_path, build_metadata, validation = self._build_environment_package(
                record, asset
            )
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
                "validation": validation,
                "metadata": {**record.metadata, **build_metadata},
            }
        )
        return self.store.put_environment(ready)

    def _build_environment_package(
        self, environment: EnvironmentRecord, asset: AssetRecord
    ) -> tuple[Path, dict[str, Any], PhysicsValidation]:
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
        half_width = float(max(abs(hull.bounds[0, 0]), abs(hull.bounds[1, 0])))
        spawn_z = half_height + 0.015
        pusher_start_x = -(half_width + 0.075)
        target_x = (
            max(0.30, half_width * 3.0)
            if environment.task_template is TaskTemplate.PUSH_TO_TARGET
            else 0.0
        )

        model_xml = _mujoco_xml(
            environment.name,
            environment.mass_kg,
            spawn_z,
            target_x,
            pusher_start_x,
        )
        model_path = assets_root / "model.xml"
        model_path.write_text(model_xml, encoding="utf-8")
        (module_root / "__init__.py").write_text(
            _package_init(environment, package_name), encoding="utf-8"
        )
        (module_root / "env.py").write_text(
            _environment_module(environment, spawn_z, target_x), encoding="utf-8"
        )
        (project_root / "pyproject.toml").write_text(
            _environment_pyproject(package_name), encoding="utf-8"
        )
        (project_root / "README.md").write_text(
            _environment_readme(environment, asset, package_name), encoding="utf-8"
        )
        validation = _run_physics_validation(model_path, spawn_z, target_x)
        if validation.status is ValidationStatus.FAILED:
            raise EnvironmentBuildError(
                "MuJoCo compiled the package but its deterministic rollout was unstable."
            )
        collision_proxy = {
            "method": "convex-hull",
            "vertices": int(len(hull.vertices)),
            "faces": int(len(hull.faces)),
            "watertight": bool(hull.is_watertight),
            "spawn_height_m": spawn_z,
        }
        task_model = {
            "controller": "actuated-planar-pusher",
            "action": "2D pusher velocity",
            "action_dimensions": 2,
            "observation": "goal-aware Dict",
            "reward": (
                "dense object-goal distance with control cost"
                if environment.task_template is TaskTemplate.PUSH_TO_TARGET
                else "upright stability and displacement with control cost"
            ),
            "target_x_m": target_x,
            "pusher_start_x_m": pusher_start_x,
        }
        manifest = {
            "environment": environment.model_dump(mode="json", exclude={"package_path"}),
            "asset": asset.model_dump(mode="json", exclude={"original_path", "visual_path"}),
            "collision_proxy": collision_proxy,
            "task_model": task_model,
            "physics_validation": validation.model_dump(mode="json"),
        }
        (project_root / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        (project_root / "validation.json").write_text(
            validation.model_dump_json(indent=2), encoding="utf-8"
        )
        archive_base = env_root / package_name
        archive = Path(shutil.make_archive(str(archive_base), "zip", env_root, package_name))
        return (
            archive,
            {"collision_proxy": collision_proxy, "task_model": task_model},
            validation,
        )

    def validate_environment(self, environment_id: str) -> EnvironmentRecord:
        environment = self.store.get_environment(environment_id)
        if not environment.package_path:
            raise EnvironmentBuildError("Environment package is not ready for validation.")
        package_path = Path(environment.package_path)
        package_name = package_path.stem
        project_root = package_path.parent / package_name
        model_path = project_root / package_name / "assets" / "model.xml"
        task_model = environment.metadata.get("task_model")
        if not isinstance(task_model, dict) or task_model.get("controller") != (
            "actuated-planar-pusher"
        ):
            raise EnvironmentBuildError(
                "This legacy package predates embodied control. Rebuild it from Objects."
            )
        collision = environment.metadata.get("collision_proxy", {})
        spawn_z = float(collision.get("spawn_height_m", 0.05))
        target_x = float(task_model.get("target_x_m", 0.0))
        validation = _run_physics_validation(model_path, spawn_z, target_x)
        manifest_path = project_root / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["physics_validation"] = validation.model_dump(mode="json")
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        (project_root / "validation.json").write_text(
            validation.model_dump_json(indent=2), encoding="utf-8"
        )
        shutil.make_archive(
            str(package_path.with_suffix("")), "zip", package_path.parent, package_name
        )
        updated = environment.model_copy(
            update={
                "updated_at": utc_now(),
                "status": (
                    EnvironmentStatus.READY
                    if validation.status is ValidationStatus.PASSED
                    else EnvironmentStatus.BLOCKED
                ),
                "validation": validation,
                "validation_errors": (
                    []
                    if validation.status is ValidationStatus.PASSED
                    else ["Deterministic MuJoCo rollout failed stability checks."]
                ),
            }
        )
        return self.store.put_environment(updated)


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


def _mujoco_xml(
    name: str,
    mass_kg: float,
    spawn_z: float,
    target_x: float,
    pusher_start_x: float,
) -> str:
    safe_name = escape(name)
    return f"""<mujoco model="{safe_name}">
  <compiler angle="radian" meshdir="."/>
  <option timestep="0.005" gravity="0 0 -9.81" integrator="implicitfast"/>
  <default>
    <joint damping="1.2" armature="0.02"/>
  </default>
  <asset>
    <mesh name="object_collision" file="collision.stl"/>
  </asset>
  <worldbody>
    <light pos="1 -1 3" diffuse="0.8 0.8 0.8"/>
    <geom name="ground" type="plane" size="2 2 0.1" contype="1" conaffinity="1"
          friction="0.9 0.02 0.002" rgba="0.16 0.17 0.15 1"/>
    <body name="pusher" pos="{pusher_start_x:.8f} 0 0">
      <joint name="pusher_x" type="slide" axis="1 0 0" range="-0.1 0.8"/>
      <joint name="pusher_y" type="slide" axis="0 1 0" range="-0.45 0.45"/>
      <geom name="pusher_geom" type="capsule" fromto="0 0 0.015 0 0 0.16"
            size="0.025" mass="0.15" contype="2" conaffinity="1"
            friction="1.0 0.02 0.002" rgba="0.20 0.62 0.90 1"/>
      <site name="pusher_tip" pos="0 0 0.08" size="0.018" rgba="0.3 0.75 1 1"/>
    </body>
    <body name="object" pos="0 0 {spawn_z:.8f}">
      <freejoint name="object_free"/>
      <geom name="object_geom" type="mesh" mesh="object_collision" mass="{mass_kg:.8f}"
            contype="1" conaffinity="3" friction="0.8 0.02 0.002"
            rgba="0.82 0.36 0.08 1"/>
    </body>
    <site name="target" pos="{target_x:.8f} 0 0.012" type="cylinder"
          size="0.055 0.002" rgba="0.20 0.78 0.42 0.72"/>
  </worldbody>
  <actuator>
    <velocity name="pusher_x_velocity" joint="pusher_x" kv="25" ctrlrange="-0.6 0.6"/>
    <velocity name="pusher_y_velocity" joint="pusher_y" kv="25" ctrlrange="-0.6 0.6"/>
  </actuator>
</mujoco>
"""


def _run_physics_validation(model_path: Path, spawn_z: float, target_x: float) -> PhysicsValidation:
    try:
        import mujoco
    except ImportError as exc:
        raise EnvironmentBuildError(
            "MuJoCo is required to validate generated environments. Install the rl extra."
        ) from exc

    model = mujoco.MjModel.from_xml_path(str(model_path))
    data = mujoco.MjData(model)
    object_body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "object")
    pusher_body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "pusher")
    object_geom = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "object_geom")
    pusher_geom = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "pusher_geom")
    object_joint = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "object_free")
    object_qpos_adr = int(model.jnt_qposadr[object_joint])
    data.qpos[object_qpos_adr : object_qpos_adr + 3] = [0.0, 0.0, spawn_z]
    data.qpos[object_qpos_adr + 3 : object_qpos_adr + 7] = [1.0, 0.0, 0.0, 0.0]
    mujoco.mj_forward(model, data)

    finite = True
    contact_steps = 0
    min_height = float(data.xpos[object_body, 2])
    max_speed = 0.0
    simulation_steps = 180
    for _ in range(simulation_steps):
        if target_x > 0:
            pusher_position = data.xpos[pusher_body, :2]
            object_position = data.xpos[object_body, :2]
            desired = object_position + np.array([-0.035, 0.0])
            data.ctrl[:] = np.clip((desired - pusher_position) * 4.0, -0.45, 0.45)
        else:
            data.ctrl[:] = 0.0
        mujoco.mj_step(model, data, nstep=5)
        finite = finite and bool(
            np.isfinite(data.qpos).all()
            and np.isfinite(data.qvel).all()
            and np.isfinite(data.qacc).all()
        )
        min_height = min(min_height, float(data.xpos[object_body, 2]))
        max_speed = max(max_speed, float(np.linalg.norm(data.qvel)))
        for contact in data.contact[: data.ncon]:
            if {int(contact.geom1), int(contact.geom2)} == {object_geom, pusher_geom}:
                contact_steps += 1
                break

    target = np.array([target_x, 0.0])
    target_error = float(np.linalg.norm(data.xpos[object_body, :2] - target))
    stable_height = min_height > -0.02
    bounded_speed = max_speed < 50.0
    contact_ok = target_x <= 0 or contact_steps > 0
    passed = finite and stable_height and bounded_speed and contact_ok
    checks = [
        "MJCF compiled successfully.",
        (
            "All generalized positions, velocities, and accelerations remained finite."
            if finite
            else "Non-finite simulator state was detected."
        ),
        (
            "Object remained above the world floor tolerance."
            if stable_height
            else "Object crossed the world floor tolerance."
        ),
        (
            "Actuated pusher made object contact."
            if contact_ok and target_x > 0
            else (
                "Passive stability task does not require pusher contact."
                if target_x <= 0
                else "Actuated pusher did not make object contact."
            )
        ),
    ]
    return PhysicsValidation(
        status=ValidationStatus.PASSED if passed else ValidationStatus.FAILED,
        checked_at=utc_now(),
        model_compiled=True,
        finite_rollout=finite,
        simulation_steps=simulation_steps * 5,
        simulated_seconds=simulation_steps * 5 * float(model.opt.timestep),
        pusher_object_contacts=contact_steps,
        final_target_error_m=target_error,
        min_object_height_m=min_height,
        max_generalized_speed=max_speed,
        nq=int(model.nq),
        nv=int(model.nv),
        nu=int(model.nu),
        checks=checks,
    )


def _package_init(environment: EnvironmentRecord, package_name: str) -> str:
    return f'''from gymnasium.envs.registration import register

register(
    id="{environment.gymnasium_id}",
    entry_point="{package_name}.env:KinetiWeaveObjectEnv",
    max_episode_steps={environment.max_episode_steps},
)
'''


def _environment_module(environment: EnvironmentRecord, spawn_z: float, target_x: float) -> str:
    task = environment.task_template.value
    return f'''from __future__ import annotations

from pathlib import Path

import gymnasium as gym
import mujoco
import numpy as np
from gymnasium import spaces


class KinetiWeaveObjectEnv(gym.Env):
    """Goal-aware contact task with an actuated planar pusher."""

    metadata = {{"render_modes": []}}

    def __init__(self):
        model_path = Path(__file__).with_name("assets") / "model.xml"
        self.model = mujoco.MjModel.from_xml_path(str(model_path))
        self.data = mujoco.MjData(self.model)
        self.body_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, "object")
        self.pusher_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, "pusher")
        object_joint = mujoco.mj_name2id(
            self.model, mujoco.mjtObj.mjOBJ_JOINT, "object_free"
        )
        pusher_x_joint = mujoco.mj_name2id(
            self.model, mujoco.mjtObj.mjOBJ_JOINT, "pusher_x"
        )
        pusher_y_joint = mujoco.mj_name2id(
            self.model, mujoco.mjtObj.mjOBJ_JOINT, "pusher_y"
        )
        self.object_qpos_adr = int(self.model.jnt_qposadr[object_joint])
        self.pusher_qpos_adrs = (
            int(self.model.jnt_qposadr[pusher_x_joint]),
            int(self.model.jnt_qposadr[pusher_y_joint]),
        )
        self.pusher_dof_adrs = (
            int(self.model.jnt_dofadr[pusher_x_joint]),
            int(self.model.jnt_dofadr[pusher_y_joint]),
        )
        self.task = "{task}"
        self.spawn_z = {spawn_z:.8f}
        self.target = np.array([{target_x:.8f}, 0.0, self.spawn_z], dtype=np.float64)
        self.frame_skip = 10
        self.action_space = spaces.Box(-1.0, 1.0, shape=(2,), dtype=np.float32)
        vector_space = spaces.Box(low=-1e6, high=1e6, shape=(21,), dtype=np.float64)
        goal_space = spaces.Box(low=-10.0, high=10.0, shape=(3,), dtype=np.float64)
        self.observation_space = spaces.Dict({{
            "observation": vector_space,
            "achieved_goal": goal_space,
            "desired_goal": goal_space,
        }})

    def _observation(self):
        object_position = self.data.xpos[self.body_id].copy()
        pusher_position = self.data.xpos[self.pusher_id].copy()
        quaternion = self.data.qpos[
            self.object_qpos_adr + 3 : self.object_qpos_adr + 7
        ].copy()
        pusher_velocity = np.array([
            self.data.qvel[self.pusher_dof_adrs[0]],
            self.data.qvel[self.pusher_dof_adrs[1]],
        ])
        object_velocity = self.data.cvel[self.body_id].copy()
        vector = np.concatenate((
            pusher_position,
            object_position,
            object_position - pusher_position,
            quaternion,
            pusher_velocity,
            object_velocity,
        ))
        return {{
            "observation": vector,
            "achieved_goal": object_position,
            "desired_goal": self.target.copy(),
        }}

    def compute_reward(self, achieved_goal, desired_goal, info):
        distance = np.linalg.norm(
            np.asarray(achieved_goal)[..., :2] - np.asarray(desired_goal)[..., :2],
            axis=-1,
        )
        return -distance

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        mujoco.mj_resetData(self.model, self.data)
        start = self.object_qpos_adr
        self.data.qpos[start : start + 3] = [0.0, 0.0, self.spawn_z]
        self.data.qpos[start + 3 : start + 7] = [1.0, 0.0, 0.0, 0.0]
        self.data.qpos[start : start + 2] += self.np_random.uniform(-0.015, 0.015, size=2)
        self.data.qpos[list(self.pusher_qpos_adrs)] = 0.0
        mujoco.mj_forward(self.model, self.data)
        return self._observation(), self._info()

    def step(self, action):
        action = np.clip(np.asarray(action, dtype=np.float64), -1.0, 1.0)
        self.data.ctrl[:] = action * 0.6
        mujoco.mj_step(self.model, self.data, nstep=self.frame_skip)
        position = self.data.xpos[self.body_id]
        distance = float(np.linalg.norm(position[:2] - self.target[:2]))
        rotation = np.empty(9, dtype=np.float64)
        start = self.object_qpos_adr
        mujoco.mju_quat2Mat(rotation, self.data.qpos[start + 3 : start + 7])
        upright = float(rotation.reshape(3, 3)[2, 2])
        control_cost = 0.01 * float(np.square(action).sum())
        if self.task == "push-to-target":
            reward = float(self.compute_reward(position, self.target, {{}})) - control_cost
            success = distance < 0.05
        else:
            displacement = float(np.linalg.norm(position[:2]))
            reward = upright - 0.5 * displacement - control_cost
            success = upright > 0.9 and displacement < 0.05
        terminated = bool(position[2] < -0.05 or np.linalg.norm(position[:2]) > 2.0)
        return self._observation(), reward, terminated, False, self._info(success)

    def _info(self, success=False):
        position = self.data.xpos[self.body_id]
        return {{
            "success": bool(success),
            "distance_to_target": float(np.linalg.norm(position[:2] - self.target[:2])),
            "controller": "actuated-planar-pusher",
            "contacts": int(self.data.ncon),
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
- Controller: actuated 2-DoF planar pusher (contact-only object interaction)
- Observation: goal-aware Gymnasium Dict for HER-compatible training
- Validation: MJCF compile plus deterministic finite-state rollout

```powershell
python -m pip install -e .
python -c '{smoke_test}'
```

The package passes a computational physics smoke test, not real-world system identification. Confirm
scale, mass, inertia, friction, contact behavior, task semantics, and rewards before publishing.
"""
