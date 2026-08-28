from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kinetiweave.domain import Artifact, CaptureProfile

ProgressCallback = Callable[[float, str], None]


class BackendUnavailable(RuntimeError):
    pass


class ReconstructionFailed(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ReconstructionRequest:
    frames_dir: Path
    output_dir: Path
    profile: CaptureProfile
    gpu_vram_gb: float | None


@dataclass(frozen=True, slots=True)
class ReconstructionResult:
    backend: str
    artifacts: tuple[Artifact, ...]
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


class ReconstructionBackend(ABC):
    backend_id: str

    @abstractmethod
    def available(self) -> bool: ...

    @abstractmethod
    def reconstruct(
        self, request: ReconstructionRequest, on_progress: ProgressCallback
    ) -> ReconstructionResult: ...


def artifact_from_path(
    path: Path,
    *,
    root: Path,
    name: str,
    kind: str,
    media_type: str,
    experimental: bool = False,
) -> Artifact:
    return Artifact(
        name=name,
        kind=kind,
        relative_path=path.relative_to(root).as_posix(),
        size_bytes=path.stat().st_size,
        media_type=media_type,
        experimental=experimental,
    )
