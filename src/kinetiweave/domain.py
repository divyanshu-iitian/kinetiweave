from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobStage(StrEnum):
    UPLOADED = "uploaded"
    INSPECTING = "inspecting"
    EXTRACTING = "extracting"
    RECONSTRUCTING = "reconstructing"
    FINALIZING = "finalizing"
    COMPLETE = "complete"


class CaptureProfile(StrEnum):
    FAST = "fast"
    BALANCED = "balanced"
    QUALITY = "quality"


class BackendChoice(StrEnum):
    AUTO = "auto"
    DA3 = "da3"
    COLMAP = "colmap"


class AssetSource(StrEnum):
    CAPTURE = "capture"
    IMPORT = "import"


class GeometryKind(StrEnum):
    POINT_CLOUD = "point-cloud"
    MESH = "mesh"
    CAD = "cad"


class EnvironmentStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    BLOCKED = "blocked"


class TaskTemplate(StrEnum):
    STABILIZE = "stabilize"
    PUSH_TO_TARGET = "push-to-target"


class Artifact(BaseModel):
    name: str
    kind: str
    relative_path: str
    size_bytes: int = Field(ge=0)
    media_type: str
    experimental: bool = False


class JobRecord(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime
    status: JobStatus
    stage: JobStage
    progress: float = Field(ge=0, le=1)
    message: str
    input_name: str
    input_path: str
    profile: CaptureProfile
    backend_requested: BackendChoice
    backend_used: str | None = None
    error_code: str | None = None
    error_detail: str | None = None
    artifacts: list[Artifact] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SystemCapabilities(BaseModel):
    os: str
    cpu: str
    logical_cores: int
    ram_gb: float | None
    gpu: str | None
    gpu_vram_gb: float | None
    cuda_available: bool
    cuda_runtime: str | None
    da3_available: bool
    colmap_available: bool
    colmap_path: str | None
    ffmpeg_available: bool
    recommended_backend: str | None
    recommended_profile: CaptureProfile
    limitations: list[str]


class AssetRecord(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime
    name: str
    source: AssetSource
    source_job_id: str | None = None
    source_filename: str
    original_path: str
    visual_path: str
    geometry_kind: GeometryKind
    media_type: str = "model/gltf-binary"
    size_bytes: int = Field(ge=0)
    vertex_count: int = Field(ge=0)
    face_count: int = Field(ge=0)
    dimensions_model: tuple[float, float, float]
    watertight: bool | None = None
    rl_eligible: bool = False
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EnvironmentRecord(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime
    name: str
    asset_id: str
    status: EnvironmentStatus
    task_template: TaskTemplate
    simulator: str = "mujoco"
    gymnasium_id: str
    max_episode_steps: int = Field(ge=10, le=100_000)
    mass_kg: float = Field(gt=0)
    target_size_m: float = Field(gt=0)
    scale_to_meters: float = Field(gt=0)
    package_path: str | None = None
    validation_errors: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EnvironmentCreate(BaseModel):
    asset_id: str
    name: str = Field(min_length=1, max_length=80)
    task_template: TaskTemplate = TaskTemplate.STABILIZE
    mass_kg: float = Field(gt=0, le=100_000)
    target_size_m: float = Field(gt=0, le=1000)
    max_episode_steps: int = Field(default=500, ge=10, le=100_000)


def utc_now() -> datetime:
    return datetime.now(UTC)
