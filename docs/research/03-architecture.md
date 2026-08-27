# Technical architecture

**Status:** accepted for Phase 0; contracts will be validated in M1 before the UI is built.

## Drivers

1. Headless research use is equal in importance to the GUI.
2. The digital twin is not owned by any simulator, renderer, or editor.
3. Conversions must expose semantic loss.
4. A normal laptop must run the reference environment.
5. Heavy/GPU/proprietary integrations remain optional and isolated.
6. Every artifact and experiment carries provenance and a schema version.

## System context

```text
capture / CAD / URDF / assets
             |
             v
   [ingest + provenance] ---> immutable asset store
             |
             v
   [canonical digital twin] <----> [web studio]
             |
        validate / compile
             |
       +-----+------+----------------+
       |            |                |
       v            v                v
    MuJoCo       PyBullet       future backends
       |            |                |
       +------------+----------------+
                    |
             Gymnasium task
                    |
       +------------+-------------+
       |                          |
    direct API             training adapters
                                  |
                         runs / reports / models
```

## Architectural layers

### 1. Domain core

Pure Python models and validation with no simulator, web, ROS, or deep-learning import. Core entities:

- `ProjectManifest`: schema version, coordinate convention, units, assets, twins, tasks.
- `AssetRef`: content digest, origin, license, media type, units, import transform.
- `DigitalTwin`: named root, links, joints, actuators, sensors, materials, metadata.
- `Link`: frame, inertial properties, visual geometries, collision geometries, child joints.
- `Joint`: parent/child, type, axis, origin, limits, dynamics, mimic/constraint metadata.
- `Actuator`: control mode, target, limits, gain/bias semantics.
- `Sensor`: type, attachment frame, update rate, noise, output specification.
- `TaskSpec`: environment, observation/action terms, reward terms, resets, terminal conditions, truncations, randomization.

Canonical units are SI: metre, kilogram, second, radian, Newton, Newton-metre. The world is right-handed with +Z up. Quaternions are stored as `(w, x, y, z)` and identified explicitly at external boundaries. Transforms are parent-to-child poses. Array ordering and frame ownership are schema fields, never implicit documentation.

### 2. Application services

- Asset import and content-addressed storage.
- Command handlers for create/update/delete/reparent operations.
- Validation and diagnostic aggregation.
- Undo/redo through reversible commands or event snapshots.
- Compiler orchestration and compile reports.
- Run manifest creation and artifact cataloguing.

Services depend on domain interfaces; they do not import UI components or concrete simulators.

### 3. Ports and adapters

```python
class SimulatorBackend(Protocol):
    backend_id: str
    capabilities: BackendCapabilities

    def compile(self, twin, task, output_dir) -> CompileReport: ...
    def create_session(self, compiled, *, render_mode=None) -> SimulationSession: ...

class SimulationSession(Protocol):
    def reset(self, seed: int, options: dict | None = None) -> State: ...
    def step(self, control, n_substeps: int = 1) -> StepResult: ...
    def render(self, mode: str): ...
    def close(self) -> None: ...
```

`CompileReport` contains backend/version, generated files and hashes, source paths, warnings, approximations, unsupported features, and effective parameters/defaults. Capability negotiation prevents loading a sensor or joint type the backend cannot represent.

Adapters are grouped by role:

- simulator: MuJoCo, PyBullet, future Gazebo/Webots/Isaac;
- format: GLTF, OBJ/STL, URDF, MJCF, future SDF/USD;
- geometry: trimesh, Open3D, Blender subprocess;
- reconstruction: COLMAP subprocess, optional learned services;
- training: SB3 first, future TorchRL/RLlib;
- integration: ROS 2 and Hugging Face.

### 4. Interfaces

The Python API directly composes services and environment factories. A local API service exposes the same commands to the Studio. The Studio holds selection, camera, panels, and transient drag state; persisted scene truth returns from the core.

Long-running reconstruction/training jobs use a job interface with states `queued`, `running`, `succeeded`, `failed`, and `cancelled`, structured progress, log stream, and artifact references. A local in-process runner comes first; a durable queue can replace it without changing the job contract.

## Package plan

```text
packages/
  core-python/          schema, validation, commands, serialization
  backend-mujoco/       compiler and runtime adapter
  backend-pybullet/     compatibility compiler and runtime
  env-gymnasium/        Gymnasium environment and task compiler
  train-sb3/            run adapter, callbacks, evaluation
  api/                  local service and job API
  studio/               reusable TypeScript editor packages
apps/
  studio-web/           browser application
  cli/                  import, validate, compile, run, train, benchmark
```

Packages are introduced only when their phase begins; empty package shells are not treated as implementation.

## Digital-twin schema strategy

- JSON-compatible, human-diffable source representation.
- JSON Schema emitted from typed models for external validation.
- Semantic version plus migration functions; unknown fields are rejected by default.
- Stable IDs are UUIDs; user-facing names need only be unique within their scope.
- Asset bytes live outside the document and are referenced by SHA-256.
- Derived values store `source = measured | imported | estimated | calibrated`, method, uncertainty where available, and input hashes.
- Extensions use namespaced keys and cannot override core semantics.

### Invariants

- A twin has one acyclic link tree unless a declared backend-supported constraint closes a loop.
- Every dynamic link has positive mass and a positive-definite inertia tensor in its declared inertial frame.
- Joint axes are normalized and limits are dimensionally valid.
- Collision geometry declares purpose and contact material; visual geometry is never silently reused.
- Asset units and transforms are known before physics compilation.
- Observation/action/reward references resolve to declared entities and shapes.

## M1 reference vertical slice

The smallest real implementation is one actuated hinge with a rigid body and ground/reference frame:

1. load a checked-in KinetiWeave JSON document;
2. validate graph, units, inertia, limits, and task references;
3. compile to MJCF and emit a report;
4. expose continuous torque action and angle/angular-velocity observation through Gymnasium;
5. pass Gymnasium `check_env`;
6. reproduce seeded resets and N-step state traces;
7. run an SB3 smoke training only after environment tests pass.

This slice proves the contracts without pretending to solve reconstruction or CAD editing.

## Data and artifact layout

```text
project.kweave.json
assets/sha256/<digest>
compiled/<backend>/<source-digest>/...
runs/<run-id>/
  manifest.json
  config.resolved.json
  metrics.jsonl
  evaluation.json
  environment.lock.json
  checkpoints/
  videos/
```

A run ID is unique; a reproducibility key hashes source revision, resolved config, environment/twin hashes, dependency lock, and seed. Result artifacts are append-only during execution and finalized atomically.

## Trust boundaries and safety

- Treat uploaded 3D files, archives, URDF XML, checkpoints, and datasets as untrusted.
- Enforce size/count/depth limits, safe archive extraction, timeouts, and isolated subprocess working directories.
- Never load arbitrary pickle checkpoints from untrusted sources.
- Browser requests cannot choose arbitrary filesystem paths or executable commands.
- Simulator/reconstruction subprocesses receive explicit inputs and minimal environment variables.
- A future ROS/physical bridge is separate, opt-in, authenticated, rate/limit bounded, and disabled by default.

## Failure semantics

Errors have stable codes, entity paths, human remediation, and severity. Examples: `KW_UNIT_UNKNOWN`, `KW_INERTIA_NOT_POSITIVE_DEFINITE`, `KW_JOINT_AXIS_ZERO`, `KW_BACKEND_UNSUPPORTED_SENSOR`, and `KW_CONVERSION_LOSSY`. A compile with errors produces no runnable artifact. Warnings require explicit acknowledgement for release benchmarks.

## Technology choices

- Python 3.11+ for domain/backend/RL integration.
- Pydantic or equivalent typed validation will be selected in M1 after a micro-benchmark against dataclasses + JSON Schema; the schema contract matters more than the library.
- MuJoCo native Python bindings, Gymnasium, NumPy, and pytest in M1.
- React + TypeScript + Three.js/R3F for Studio in M2; state library selected after interaction prototype.
- HTTP/WebSocket local API only when the Studio needs it; direct Python remains first-class.
- `uv`-generated lockfiles and platform-aware optional dependency groups are the intended packaging direction.

## Architecture decisions

| ID | Decision | Alternatives | Consequence |
|---|---|---|---|
| ADR-001 | KinetiWeave schema is canonical | MJCF, URDF, USD as source of truth | More compiler work; avoids backend lock-in and makes loss explicit |
| ADR-002 | MuJoCo is first backend | PyBullet, Gazebo, SAPIEN | Strong contact/control baseline and laptop fit; must keep adapter tests honest |
| ADR-003 | Gymnasium is public environment API | Custom API, dm_env, TorchRL-only | Broad compatibility and correct termination semantics |
| ADR-004 | Stable-Baselines3 supplies first algorithms | Reimplementation, CleanRL import, RLlib | Reliable small baseline; metadata/orchestration remain ours |
| ADR-005 | Apache-2.0 for original work | MIT, GPL | Permissive use plus explicit patent terms; stricter attribution process |
| ADR-006 | Reconstruction is optional and multi-view-first | Single-image-first | Less flashy, more defensible metric geometry |
| ADR-007 | UI communicates through core commands | Scene graph owned by browser | One validation/serialization path for CLI, API, and GUI |

## Deferred decisions

- Exact persistence database: filesystem manifests are enough through M2.
- Cloud execution and multi-user auth: excluded from laptop-first milestones.
- Natural-language scene generation: excluded until deterministic authoring works.
- Physical deployment: excluded until threat model and hardware safety design exist.

