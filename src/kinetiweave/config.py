from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    data_dir: Path
    max_upload_bytes: int = 1_500_000_000
    max_video_seconds: float = 240.0
    max_workers: int = 1
    host: str = "127.0.0.1"
    port: int = 8765

    @classmethod
    def from_env(cls) -> Settings:
        default_data = Path.cwd() / "var"
        return cls(
            data_dir=Path(os.getenv("KINETIWEAVE_DATA_DIR", default_data)).resolve(),
            max_upload_bytes=int(os.getenv("KINETIWEAVE_MAX_UPLOAD_BYTES", "1500000000")),
            max_video_seconds=float(os.getenv("KINETIWEAVE_MAX_VIDEO_SECONDS", "240")),
            max_workers=max(1, int(os.getenv("KINETIWEAVE_MAX_WORKERS", "1"))),
            host=os.getenv("KINETIWEAVE_HOST", "127.0.0.1"),
            port=int(os.getenv("KINETIWEAVE_PORT", "8765")),
        )

    @property
    def jobs_dir(self) -> Path:
        return self.data_dir / "jobs"

    @property
    def database_path(self) -> Path:
        return self.data_dir / "kinetiweave.sqlite3"

    @property
    def studio_dist(self) -> Path:
        return Path(__file__).resolve().parents[2] / "apps" / "studio" / "dist"

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
