from __future__ import annotations

import logging
import mimetypes
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Body, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from kinetiweave.catalog import (
    AssetImportError,
    CatalogService,
    CatalogStore,
    EnvironmentBuildError,
)
from kinetiweave.config import Settings
from kinetiweave.domain import (
    AssetRecord,
    BackendChoice,
    CaptureProfile,
    EnvironmentCreate,
    EnvironmentRecord,
    JobRecord,
    SystemCapabilities,
)
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
ALLOWED_GEOMETRY_SUFFIXES = {
    ".glb",
    ".gltf",
    ".obj",
    ".stl",
    ".ply",
    ".off",
    ".3mf",
    ".step",
    ".stp",
}
MAX_GEOMETRY_BYTES = 750_000_000


def create_app(settings: Settings | None = None) -> FastAPI:
    configured = settings or Settings.from_env()
    configured.ensure_directories()
    store = JobStore(configured.database_path)
    catalog_store = CatalogStore(configured.database_path)
    catalog = CatalogService(configured, catalog_store)
    pipeline = PipelineService(configured, store, catalog=catalog)

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
    app.state.catalog = catalog
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

    @app.get("/api/assets", response_model=list[AssetRecord])
    def list_assets(limit: int = 100) -> list[AssetRecord]:
        return catalog_store.list_assets(limit)

    @app.get("/api/assets/{asset_id}", response_model=AssetRecord)
    def get_asset(asset_id: str) -> AssetRecord:
        try:
            return catalog_store.get_asset(asset_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Object not found") from exc

    @app.get("/api/assets/{asset_id}/geometry")
    def get_asset_geometry(asset_id: str) -> FileResponse:
        try:
            asset = catalog_store.get_asset(asset_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Object not found") from exc
        path = Path(asset.visual_path).resolve()
        allowed_roots = (configured.assets_dir.resolve(), configured.jobs_dir.resolve())
        if not any(root in path.parents for root in allowed_roots) or not path.is_file():
            raise HTTPException(status_code=404, detail="Object geometry not found")
        return FileResponse(path, media_type="model/gltf-binary", filename=f"{asset.name}.glb")

    @app.post("/api/assets/import", response_model=AssetRecord, status_code=201)
    async def import_asset(geometry: Annotated[UploadFile, File()]) -> AssetRecord:
        original_name = Path(geometry.filename or "object.glb").name
        suffix = Path(original_name).suffix.lower()
        if suffix not in ALLOWED_GEOMETRY_SUFFIXES:
            raise HTTPException(
                status_code=415,
                detail=(
                    "Unsupported geometry format. Use STEP, STP, GLB, GLTF, OBJ, "
                    "STL, PLY, OFF, or 3MF."
                ),
            )
        staging_root = configured.assets_dir / ".staging"
        staging_root.mkdir(parents=True, exist_ok=True)
        staging_path = staging_root / f"{uuid.uuid4().hex}{suffix}"
        size = 0
        try:
            with staging_path.open("wb") as target:
                while chunk := await geometry.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_GEOMETRY_BYTES:
                        raise HTTPException(status_code=413, detail="Geometry exceeds 750 MB")
                    target.write(chunk)
            if size < 64:
                raise HTTPException(status_code=400, detail="Geometry file is empty or incomplete")
            return catalog.import_geometry(staging_path, original_name)
        except AssetImportError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        finally:
            await geometry.close()
            staging_path.unlink(missing_ok=True)

    @app.get("/api/environments", response_model=list[EnvironmentRecord])
    def list_environments(limit: int = 100) -> list[EnvironmentRecord]:
        return catalog_store.list_environments(limit)

    @app.get("/api/environments/{environment_id}", response_model=EnvironmentRecord)
    def get_environment(environment_id: str) -> EnvironmentRecord:
        try:
            return catalog_store.get_environment(environment_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="RL environment not found") from exc

    @app.post("/api/environments", response_model=EnvironmentRecord, status_code=201)
    def create_environment(
        environment: Annotated[EnvironmentCreate, Body()],
    ) -> EnvironmentRecord:
        try:
            return catalog.create_environment(environment)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Source object not found") from exc
        except EnvironmentBuildError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/environments/{environment_id}/package")
    def get_environment_package(environment_id: str) -> FileResponse:
        try:
            environment = catalog_store.get_environment(environment_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="RL environment not found") from exc
        if not environment.package_path:
            raise HTTPException(status_code=409, detail="Environment package is not ready")
        path = Path(environment.package_path).resolve()
        root = configured.environments_dir.resolve()
        if root not in path.parents or not path.is_file():
            raise HTTPException(status_code=404, detail="Environment package not found")
        return FileResponse(
            path,
            media_type="application/zip",
            filename=f"kinetiweave-{environment.id[:8]}.zip",
        )

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
