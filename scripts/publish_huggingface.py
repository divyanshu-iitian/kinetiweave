from __future__ import annotations

import argparse
from pathlib import Path

from huggingface_hub import HfApi
from huggingface_hub.errors import LocalTokenNotFoundError


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish KinetiWeave as a Docker Space")
    parser.add_argument("--repo-id", help="Target such as username/kinetiweave")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    api = HfApi()
    try:
        account = api.whoami()
    except LocalTokenNotFoundError as exc:
        raise SystemExit(
            "Hugging Face login required. Run: .venv\\Scripts\\hf.exe auth login"
        ) from exc
    repo_id = args.repo_id or f"{account['name']}/kinetiweave"
    api.create_repo(
        repo_id=repo_id,
        repo_type="space",
        space_sdk="docker",
        private=False,
        exist_ok=True,
    )
    api.upload_folder(
        repo_id=repo_id,
        repo_type="space",
        folder_path=root,
        ignore_patterns=[
            ".git/**",
            ".venv/**",
            ".tools/**",
            ".playwright-cli/**",
            "**/node_modules/**",
            "apps/studio/dist/**",
            "var/**",
            "output/**",
            "*.pyc",
        ],
        commit_message="Publish KinetiWeave capture-to-RL Studio",
    )
    api.upload_file(
        repo_id=repo_id,
        repo_type="space",
        path_or_fileobj=root / "deploy" / "huggingface" / "README.md",
        path_in_repo="README.md",
        commit_message="Add Hugging Face Space card",
    )
    print(f"Published: https://huggingface.co/spaces/{repo_id}")


if __name__ == "__main__":
    main()
