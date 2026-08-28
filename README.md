# KinetiWeave

> From real machines to learning worlds.

KinetiWeave is an open-source, laptop-first workspace for turning real objects and robots into
inspectable 3D reconstructions, digital twins, simulation assets, and reinforcement-learning
environments.

```text
images / video / CAD / 3D assets
                  |
                  v
        simulator-neutral digital twin
                  |
        +---------+---------+
        |                   |
        v                   v
  interactive studio   Python / Gymnasium API
        |                   |
        +---------+---------+
                  |
                  v
       simulation, training, evaluation
```

## Status

**Capture-to-RL vertical slice.** The Studio now persists every successful reconstruction in an
Object Library, imports STEP/STP and common mesh formats, records geometry evidence, and generates
downloadable MuJoCo + Gymnasium environments after the user supplies real scale and mass. Captured
point clouds and non-watertight meshes use an explicitly labeled convex-hull collision proxy.

## Why KinetiWeave?

Robotics research is fragmented across asset tools, simulator-specific robot formats, task
definitions, RL libraries, and experiment trackers. KinetiWeave connects these parts without hiding
their boundaries or pretending that one simulator or reconstruction model fits every task.

The name combines *kinetic* systems with weaving geometry, articulation, physics, sensing, and
learning into one inspectable pipeline.

## Implemented video workflow

1. Upload an MP4, MOV, WebM, AVI, or MKV capture to a loopback-only service.
2. Validate timing, duration, resolution, and decodability.
3. Select sharp, temporally distributed views and report capture-health evidence.
4. Reconstruct relative-scale geometry with DA3 Small or an optional COLMAP installation.
5. Inspect the real GLB artifact in a Three.js viewport and download its provenance manifest.
6. Find the result permanently in Objects, alongside imported CAD and mesh assets.
7. Enter a measured dimension and mass, choose an RL task, and export a runnable environment.

## Object, CAD, and RL workflow

- **Capture:** reconstruct video locally with DA3 Small or COLMAP.
- **Objects:** review saved geometry or import STEP, STP, GLB, GLTF, OBJ, STL, PLY, OFF, or 3MF.
- **Environments:** generate a conservative collision mesh, MJCF model, registered Gymnasium
  package, manifest, and install instructions in one ZIP.

STEP import preserves transferred geometry, not the original CAD application's parametric feature
history. Every generated environment is a starting model: validate physical scale, mass, inertia,
friction, contacts, tasks, and rewards before publishing training claims.

## Architecture decisions

- **Canonical model:** a versioned KinetiWeave schema independent of MJCF, URDF, SDF, or USD.
- **First simulator backend:** MuJoCo; PyBullet is the first compatibility backend.
- **Environment API:** Gymnasium with explicit termination and truncation.
- **Studio:** React and Three.js; the browser never becomes the source of physics truth.
- **Reconstruction:** laptop-first DA3 Small default with an optional classical COLMAP path.
- **Project license:** Apache-2.0 with per-asset and per-model provenance.

Full rationale: [architecture](docs/research/03-architecture.md),
[license analysis](docs/research/05-license-analysis.md), and
[video-to-3D decision](docs/research/06-video-to-3d-decision.md).

Research reports: [landscape](docs/research/01-landscape.md),
[literature review](docs/research/02-literature-review.md),
[architecture](docs/research/03-architecture.md),
[benchmark plan](docs/research/04-benchmark-plan.md),
[license analysis](docs/research/05-license-analysis.md), and
[video-to-3D decision](docs/research/06-video-to-3d-decision.md).

## Run locally on Windows

The setup is isolated in `.venv`, pins the audited DA3 source revision, installs CUDA-enabled
PyTorch, and builds Studio. It does not modify global Python packages.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup-da3.ps1
powershell -ExecutionPolicy Bypass -File scripts/start.ps1
```

Then open `http://127.0.0.1:8765`. Upload a 15-40 second orbit video in which the object stays still
while the camera moves around it. First reconstruction also downloads DA3 Small model weights from
Hugging Face.

Read the [capture guide](docs/video-capture-guide.md) before judging reconstruction quality.

## Developer checks

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check src tests
Set-Location apps\studio
npm run lint
npm run build
```

The supported baseline is Python 3.11 on Windows. Backend support is stated explicitly rather than
implied globally.

## Repository map

```text
apps/studio/      React and Three.js local reconstruction workspace
benchmarks/       benchmark definitions and immutable result artifacts
configs/          versioned task, simulator, and training configuration
docs/research/    evidence, decisions, and research protocol
src/kinetiweave/  local API, capture analysis, jobs, and reconstruction adapters
scripts/          setup, repository, and experiment automation
tests/            unit, contract, integration, and determinism tests
```

## Roadmap and contribution

See [ROADMAP.md](ROADMAP.md). Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a change.
Experimental features must be labeled, and planned features must not appear as working controls.

Report vulnerabilities privately using [SECURITY.md](SECURITY.md). Do not attach robot credentials,
tokens, private datasets, or proprietary CAD to public issues.

KinetiWeave's original code and documentation are licensed under [Apache-2.0](LICENSE). Third-party
software and models retain their own licenses; see [third-party notices](THIRD_PARTY_NOTICES.md).
Citation metadata is provided in [CITATION.cff](CITATION.cff).

## Hugging Face Space

The repository includes a Docker Space definition and a guarded publisher. The free CPU image runs
the Object Library, CAD/mesh import, and RL export; video reconstruction still needs a configured
DA3/COLMAP backend and suitable compute.

```powershell
hf auth login
.\.venv\Scripts\python.exe scripts\publish_huggingface.py
```
