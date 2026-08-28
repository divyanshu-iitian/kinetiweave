from __future__ import annotations

import logging
import mimetypes
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from kinetiweave.config import Settings
from kinetiweave.domain import BackendChoice, CaptureProfile, JobRecord, SystemCapabilities
from kinetiweave.jobs import JobStore
from kinetiweave.pipeline import PipelineService
from kinetiweave.system import detect_capabilities

LOGGER = logging.getLogger("kinetiweave.api")
ALLOWED_VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".avi", ".webm", ".mkv"}
ALLOWED_VIDEO_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/x-msvideo",
    "video/webm",
    "video/x-matroska",
    "application/octet-stream",
}


def create_app(settings: Settings | None = None) -> FastAPI:
    configured = settings or Settings.from_env()
    configured.ensure_directories()
    store = JobStore(configured.database_path)
    pipeline = PipelineService(configured, store)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        pipeline.shutdown()

    app = FastAPI(
        title="KinetiWeave Local API",
        version="0.1.0",
        description="Local video-to-3D reconstruction service. Binds to loopback by default.",
        lifespan=lifespan,
    )
    app.state.settings = configured
    app.state.store = store
    app.state.pipeline = pipeline
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            f"http://127.0.0.1:{configured.port}",
        ],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "scope": "local"}

    @app.get("/api/system", response_model=SystemCapabilities)
    def system() -> SystemCapabilities:
        return detect_capabilities()

    @app.get("/api/jobs", response_model=list[JobRecord])
    def list_jobs(limit: int = 25) -> list[JobRecord]:
        return store.list(limit)

    @app.get("/api/jobs/{job_id}", response_model=JobRecord)
    def get_job(job_id: str) -> JobRecord:
        try:
            return store.get(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc

    @app.post("/api/jobs", response_model=JobRecord, status_code=202)
    async def create_job(
        video: Annotated[UploadFile, File()],
        profile: Annotated[CaptureProfile, Form()] = CaptureProfile.FAST,
        backend: Annotated[BackendChoice, Form()] = BackendChoice.AUTO,
    ) -> JobRecord:
        original_name = Path(video.filename or "capture.mp4").name
        suffix = Path(original_name).suffix.lower()
        if suffix not in ALLOWED_VIDEO_SUFFIXES:
            raise HTTPException(status_code=415, detail="Unsupported video file extension")
        if video.content_type and video.content_type not in ALLOWED_VIDEO_TYPES:
            raise HTTPException(status_code=415, detail="Unsupported video content type")

        job_id = uuid.uuid4().hex
        job_root = configured.jobs_dir / job_id
        input_dir = job_root / "input"
        input_dir.mkdir(parents=True, exist_ok=False)
        destination = input_dir / f"capture{suffix}"
        size = 0
        try:
            with destination.open("wb") as target:
                while chunk := await video.read(1024 * 1024):
                    size += len(chunk)
                    if size > configured.max_upload_bytes:
                        raise HTTPException(
                            status_code=413,
                            detail="Video exceeds the local upload limit",
                        )
                    target.write(chunk)
        except Exception:
            shutil.rmtree(job_root, ignore_errors=True)
            raise
        finally:
            await video.close()

        if size < 1024:
            shutil.rmtree(job_root, ignore_errors=True)
            raise HTTPException(status_code=400, detail="Uploaded video is empty or incomplete")
        job = store.create(
            job_id=job_id,
            input_name=original_name,
            input_path=destination,
            profile=profile,
            backend=backend,
        )
        pipeline.submit(job_id)
        return job

    @app.get("/api/jobs/{job_id}/artifacts/{artifact_path:path}")
    def get_artifact(job_id: str, artifact_path: str) -> FileResponse:
        try:
            job = store.get(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc
        allowed = {artifact.relative_path for artifact in job.artifacts}
        if artifact_path not in allowed:
            raise HTTPException(status_code=404, detail="Artifact not found")
        job_root = (configured.jobs_dir / job_id).resolve()
        resolved = (job_root / artifact_path).resolve()
        if job_root not in resolved.parents or not resolved.is_file():
            raise HTTPException(status_code=404, detail="Artifact not found")
        media_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
        return FileResponse(resolved, media_type=media_type, filename=resolved.name)

    studio_dist = configured.studio_dist
    if studio_dist.is_dir():
        assets = studio_dist / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="studio-assets")

        @app.get("/{path:path}")
        def studio(request: Request, path: str) -> FileResponse:
            if path.startswith("api/"):
                raise HTTPException(status_code=404, detail="API route not found")
            candidate = (studio_dist / path).resolve()
            if studio_dist.resolve() in candidate.parents and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(studio_dist / "index.html")

    return app


app = create_app()
