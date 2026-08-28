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


def utc_now() -> datetime:
    return datetime.now(UTC)
