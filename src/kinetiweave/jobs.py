from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from kinetiweave.domain import (
    Artifact,
    BackendChoice,
    CaptureProfile,
    JobRecord,
    JobStage,
    JobStatus,
    utc_now,
)


class JobStore:
    """SQLite job store with one short-lived connection per operation."""

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
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    progress REAL NOT NULL CHECK(progress >= 0 AND progress <= 1),
                    message TEXT NOT NULL,
                    input_name TEXT NOT NULL,
                    input_path TEXT NOT NULL,
                    profile TEXT NOT NULL,
                    backend_requested TEXT NOT NULL,
                    backend_used TEXT,
                    error_code TEXT,
                    error_detail TEXT,
                    artifacts_json TEXT NOT NULL DEFAULT '[]',
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS jobs_created_at_idx ON jobs(created_at DESC)"
            )

    def create(
        self,
        *,
        job_id: str,
        input_name: str,
        input_path: Path,
        profile: CaptureProfile,
        backend: BackendChoice,
    ) -> JobRecord:
        now = utc_now()
        with self._write_lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO jobs (
                    id, created_at, updated_at, status, stage, progress, message,
                    input_name, input_path, profile, backend_requested
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    now.isoformat(),
                    now.isoformat(),
                    JobStatus.QUEUED,
                    JobStage.UPLOADED,
                    0.0,
                    "Upload stored. Waiting for the reconstruction worker.",
                    input_name,
                    str(input_path),
                    profile,
                    backend,
                ),
            )
        return self.get(job_id)

    def get(self, job_id: str) -> JobRecord:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        return self._to_record(row)

    def list(self, limit: int = 25) -> list[JobRecord]:
        safe_limit = min(max(limit, 1), 100)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (safe_limit,)
            ).fetchall()
        return [self._to_record(row) for row in rows]

    def update(self, job_id: str, **changes: Any) -> JobRecord:
        allowed = {
            "status",
            "stage",
            "progress",
            "message",
            "backend_used",
            "error_code",
            "error_detail",
            "artifacts_json",
            "metadata_json",
        }
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError(f"Unsupported job fields: {sorted(unknown)}")
        if not changes:
            return self.get(job_id)

        if "artifacts" in changes or "metadata" in changes:
            raise ValueError("Use set_artifacts or set_metadata")

        changes["updated_at"] = utc_now().isoformat()
        assignments = ", ".join(f"{key} = ?" for key in changes)
        values = [self._sql_value(value) for value in changes.values()]
        with self._write_lock, self._connect() as connection:
            cursor = connection.execute(
                f"UPDATE jobs SET {assignments} WHERE id = ?",  # noqa: S608
                (*values, job_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(job_id)
        return self.get(job_id)

    def set_artifacts(self, job_id: str, artifacts: Iterable[Artifact]) -> JobRecord:
        payload = json.dumps([artifact.model_dump(mode="json") for artifact in artifacts])
        return self.update(job_id, artifacts_json=payload)

    def set_metadata(self, job_id: str, metadata: dict[str, Any]) -> JobRecord:
        return self.update(job_id, metadata_json=json.dumps(metadata))

    @staticmethod
    def _sql_value(value: Any) -> Any:
        if hasattr(value, "value"):
            return value.value
        return value

    @staticmethod
    def _to_record(row: sqlite3.Row) -> JobRecord:
        data = dict(row)
        data["artifacts"] = json.loads(data.pop("artifacts_json"))
        data["metadata"] = json.loads(data.pop("metadata_json"))
        return JobRecord.model_validate(data)
