# KinetiWeave

> From real machines to learning worlds.

KinetiWeave is an open-source research platform for turning real robots and physical objects into reproducible digital twins, robotics simulations, and reinforcement-learning environments.

The project is intentionally being built research-first:

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

**Phase 0 — Research foundation.** The architecture, ecosystem evaluation, benchmark protocol, and license policy are complete. No simulator, editor, reconstruction, or training feature is claimed as implemented yet.

The first executable milestone will be a headless, deterministic pendulum/actuated-link environment backed by MuJoCo and exposed through Gymnasium. The web editor follows only after the schema and backend contract are validated.

## Why KinetiWeave?

Robotics research is fragmented across asset tools, simulator-specific robot formats, task definitions, RL libraries, and experiment trackers. KinetiWeave will connect these parts without hiding their boundaries or pretending that one simulator or reconstruction model fits every task.

The name combines *kinetic* systems with the idea of weaving geometry, articulation, physics, sensing, and learning into one inspectable pipeline.

## Intended workflow

1. Import GLB/GLTF, OBJ, STL, URDF, or reconstruction output.
2. Build a hierarchy of links, joints, actuators, sensors, visuals, and collisions.
3. validate mass, inertia, units, transforms, and joint limits.
4. Compile the same digital twin to supported simulator backends.
5. Define observations, actions, rewards, termination, and randomization.
6. Run the task through the Gymnasium API with or without the GUI.
7. Train and evaluate baselines with complete provenance and multiple seeds.
8. Export environments, policies, model cards, and benchmark artifacts.

## Architecture decision summary

- **Canonical model:** versioned KinetiWeave schema, independent of MJCF, URDF, SDF, or USD.
- **First backend:** MuJoCo; PyBullet is the first compatibility backend.
- **Environment API:** Gymnasium, including explicit termination and truncation.
- **First RL integration:** Stable-Baselines3 for PPO, SAC, and TD3 baselines.
- **Studio direction:** React, Three.js, and React Three Fiber; the browser never becomes the source of physics truth.
- **Geometry tooling:** trimesh/Open3D behind adapters with provenance for every imported asset.
- **Reconstruction:** optional multi-view pipeline; classical COLMAP baseline before learned alternatives.
- **Project license:** Apache-2.0, with per-asset and per-model license manifests.

Full rationale: [architecture](docs/research/03-architecture.md) and [license analysis](docs/research/05-license-analysis.md).

## Repository map

```text
apps/             future user-facing applications
benchmarks/       benchmark definitions and immutable result artifacts
configs/          versioned task, simulator, and training configuration
docs/research/    evidence, decisions, and research protocol
examples/         minimal reproducible examples
models/           model cards and metadata only; weights are not committed
packages/         future Python and TypeScript packages
scripts/          repository and experiment automation
tests/            unit, contract, integration, and determinism tests
```

## Research reports

- [Open-source landscape](docs/research/01-landscape.md)
- [Literature review](docs/research/02-literature-review.md)
- [Technical architecture](docs/research/03-architecture.md)
- [Benchmark plan](docs/research/04-benchmark-plan.md)
- [License analysis](docs/research/05-license-analysis.md)

## Development setup

Phase 0 has no runtime dependencies. To validate the repository:

```bash
python scripts/check_repository.py
```

The supported development baseline is Python 3.11+ on Windows, Linux, and macOS. Simulator-specific support will be stated per backend rather than implied globally.

## Roadmap

See [ROADMAP.md](ROADMAP.md). Milestone order is contract-first: research, schema and headless simulation, then editor, RL baselines, reconstruction, and public benchmark releases.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a change. Major dependencies and assets require a license/provenance review. Experimental features must be labeled; planned features must not appear as working controls.

## Security

Please report vulnerabilities privately using the process in [SECURITY.md](SECURITY.md). Do not attach robot credentials, tokens, private datasets, or proprietary CAD to public issues.

## License and citation

KinetiWeave's original code and documentation are licensed under [Apache-2.0](LICENSE). Third-party code, models, and assets retain their own licenses and must be recorded in the future dependency/asset manifests.

If this foundation is useful in academic work, citation metadata is provided in [CITATION.cff](CITATION.cff).

