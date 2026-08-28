# Roadmap

Roadmap items are commitments to investigate or build, not claims of current functionality. A phase exits only when its acceptance criteria, tests, documentation, and benchmark evidence are complete.

M0 is complete. The current mainline focus is M1; a tested M5 video-to-3D vertical slice has also
landed early, but M5 remains open until scale recovery, cleanup, benchmarks, and acceptance evidence
are complete.

## M0 — Research foundation (complete)

- Ecosystem and literature review.
- Architecture and simulator boundary.
- Benchmark and reproducibility protocol.
- License policy and project governance.
- Public repository, issue labels, and milestones.

Exit: repository validation passes and all five research reports are reviewed.

## M1 — Core contracts and headless simulation

- Versioned digital-twin schema with units and coordinate conventions.
- Validation diagnostics with stable error codes.
- `SimulatorBackend` contract and MuJoCo adapter.
- Deterministic one-link reference environment through Gymnasium.
- Schema, serialization, backend-contract, and seed tests.

Exit: reference task passes Gymnasium's environment checker on all supported operating systems and reproduces state traces within documented tolerances.

## M2 — 3D workspace

- Real GLB/GLTF import first; OBJ/STL through conversion adapters.
- Selection, hierarchy, transform gizmos, properties, save/load, undo/redo.
- Visual/collision pairing and validation feedback.
- Browser-to-core command protocol; no physics implemented in UI state.

Exit: an imported articulated asset can be edited, persisted, reopened, and compiled for the M1 backend.

## M3 — Digital-twin authoring

- Links, joints, limits, inertial properties, actuators, and sensors.
- URDF import/export with an explicit loss report.
- Collision proxies and inertia estimation with user confirmation.

Exit: round-trip and golden-model suites pass; unsupported semantics are reported rather than discarded silently.

## M4 — RL and evaluation

- Task specification, reward terms, reset distributions, and domain randomization.
- PPO, SAC, and TD3 via Stable-Baselines3.
- Run manifests, checkpoints, evaluation harness, and model cards.

Exit: at least one manipulation/control task trains across five seeds and produces a reproducible evaluation report.

## M5 — Reconstruction

- Multi-view capture quality checks and COLMAP baseline.
- Segmentation, scale recovery, mesh cleanup, and provenance.
- Optional learned reconstruction adapters with isolated environments.

Exit: a documented image set produces an inspectable asset with geometric accuracy, runtime, memory, and failure-mode measurements.

## M6 — Benchmark suite

- Backend correctness and performance matrix.
- RL statistical reports with bootstrap confidence intervals.
- Reconstruction quality/runtime comparisons.
- Versioned public result bundles.

## M7 — Public research release

- Stable APIs and migration policy.
- External installation test.
- Hugging Face environment/model artifacts with model cards where licensing allows.
- Research contribution statement and limitations.
