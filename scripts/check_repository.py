"""Fast, dependency-free checks for the KinetiWeave repository."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = (
    "README.md",
    "LICENSE",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
    "CITATION.cff",
    "CHANGELOG.md",
    "ROADMAP.md",
    "THIRD_PARTY_NOTICES.md",
    "pyproject.toml",
    "apps/studio/package.json",
    "docs/video-capture-guide.md",
    "docs/research/01-landscape.md",
    "docs/research/02-literature-review.md",
    "docs/research/03-architecture.md",
    "docs/research/04-benchmark-plan.md",
    "docs/research/05-license-analysis.md",
    "docs/research/06-video-to-3d-decision.md",
)
PLACEHOLDER_PATTERNS = (
    re.compile(r"\bTODO\b", re.IGNORECASE),
    re.compile(r"\bTBD\b", re.IGNORECASE),
    re.compile(r"lorem ipsum", re.IGNORECASE),
)


def main() -> int:
    errors: list[str] = []

    for relative in REQUIRED_FILES:
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"missing required file: {relative}")
            continue
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            errors.append(f"empty required file: {relative}")
        for pattern in PLACEHOLDER_PATTERNS:
            if pattern.search(text):
                errors.append(f"placeholder '{pattern.pattern}' in {relative}")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for report in (
        "docs/research/01-landscape.md",
        "docs/research/02-literature-review.md",
        "docs/research/03-architecture.md",
        "docs/research/04-benchmark-plan.md",
        "docs/research/05-license-analysis.md",
        "docs/research/06-video-to-3d-decision.md",
    ):
        if report not in readme:
            errors.append(f"README does not link research report: {report}")

    if errors:
        print("Repository checks failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Repository checks passed ({len(REQUIRED_FILES)} required files).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
