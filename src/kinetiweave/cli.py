from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
import time
import uuid
from pathlib import Path

import uvicorn

from kinetiweave.config import Settings
from kinetiweave.domain import BackendChoice, CaptureProfile, JobStatus
from kinetiweave.jobs import JobStore
from kinetiweave.pipeline import PipelineService
from kinetiweave.system import detect_capabilities


def main() -> None:
    parser = argparse.ArgumentParser(prog="kinetiweave")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve = subparsers.add_parser("serve", help="Run the local API and built Studio")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=None)

    reconstruct = subparsers.add_parser("reconstruct", help="Reconstruct one local video")
    reconstruct.add_argument("video", type=Path)
    reconstruct.add_argument(
        "--profile",
        choices=[item.value for item in CaptureProfile],
        default="fast",
    )
    reconstruct.add_argument(
        "--backend",
        choices=[item.value for item in BackendChoice],
        default="auto",
    )

    subparsers.add_parser("doctor", help="Inspect local reconstruction capabilities")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    settings = Settings.from_env()
    settings.ensure_directories()
    if args.command == "doctor":
        print(detect_capabilities().model_dump_json(indent=2))
        return
    if args.command == "serve":
        uvicorn.run(
            "kinetiweave.api:app",
            host=args.host or settings.host,
            port=args.port or settings.port,
            reload=False,
        )
        return
    if args.command == "reconstruct":
        video = args.video.resolve()
        if not video.is_file():
            parser.error(f"Video does not exist: {video}")
        job_id = uuid.uuid4().hex
        job_root = settings.jobs_dir / job_id
        input_dir = job_root / "input"
        input_dir.mkdir(parents=True)
        destination = input_dir / f"capture{video.suffix.lower()}"
        shutil.copyfile(video, destination)
        store = JobStore(settings.database_path)
        store.create(
            job_id=job_id,
            input_name=video.name,
            input_path=destination,
            profile=CaptureProfile(args.profile),
            backend=BackendChoice(args.backend),
        )
        service = PipelineService(settings, store)
        service.submit(job_id)
        while True:
            job = store.get(job_id)
            print(
                f"\r{job.progress * 100:5.1f}%  {job.stage.value:<16} {job.message:<70}",
                end="",
                flush=True,
            )
            if job.status in {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED}:
                print()
                print(json.dumps(job.model_dump(mode="json"), indent=2, default=str))
                service.shutdown()
                sys.exit(0 if job.status == JobStatus.SUCCEEDED else 1)
            time.sleep(0.7)


if __name__ == "__main__":
    main()
