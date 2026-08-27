# Benchmark plan

**Status:** protocol approved; no performance results exist yet.

## Principles

1. Correctness gates performance.
2. Compare equivalent semantics, not similarly named tasks.
3. Publish raw per-run data and exact commands.
4. Separate environment throughput, learner throughput, and end-to-end training.
5. Never tune on final evaluation seeds or scenes.
6. Report uncertainty and failures, not only successful runs.

The protocol follows the reproducibility concerns in [Henderson et al.](https://doi.org/10.1609/aaai.v32i1.11694), the robust aggregation recommendations in [Agarwal et al.](https://arxiv.org/abs/2108.13264), and Stable-Baselines3's [evaluation guidance](https://stable-baselines3.readthedocs.io/en/master/guide/rl_tips.html).

## Benchmark levels

### B0 — Schema and compiler correctness

Fixtures: one hinge, two-link arm, fixed-base 6-DoF arm, floating rigid body, joint-limit/contact case, invalid models.

Metrics/tests:

- validation precision on curated valid/invalid fixtures;
- deterministic serialization and content hash;
- import/export semantic-loss report;
- pose, joint-limit, mass, center-of-mass, and inertia agreement;
- golden compiled model diff (normalized, ignoring non-semantic ordering);
- compile time and peak resident memory.

Gate: zero silent field loss; all invalid fixtures produce the expected stable diagnostic code.

### B1 — Simulation correctness and performance

For each supported backend/configuration:

- deterministic seeded reset and state-trace comparison;
- free-fall acceleration, pendulum period, energy drift without damping;
- actuator step response and joint-limit behavior;
- contact penetration/settling and friction incline threshold;
- initialization/reset/step/render latency;
- headless simulation steps per second;
- peak RSS, CPU utilization, and optional GPU memory/utilization.

Timing protocol: one warm-up phase, then at least 30 timed samples; report median, p5/p95, mean ± SD, machine-readable raw samples. Use fixed CPU power mode where controllable and report it.

Comparisons:

1. KinetiWeave-compiled MuJoCo vs direct canonical MJCF fixture.
2. KinetiWeave-compiled PyBullet vs direct PyBullet/URDF fixture after semantic matching.
3. Cross-backend state/behavior deltas; not a claim that either is ground truth.

### B2 — Environment API overhead

- raw backend step vs KinetiWeave session vs Gymnasium environment;
- vectorized 1/4/8/16 environment throughput where supported;
- observation/reward construction time and allocations;
- reset distribution reproducibility;
- render modes tested separately from headless runs.

Acceptance target: wrapper overhead below 10% of backend step time for the M1 reference environment, or a documented profile and optimization plan. This is a target, not a current result.

### B3 — RL learning

Tasks begin with one reference continuous-control task, then reach/push manipulation only after B0-B2 pass.

Algorithms: random policy, scripted/controller oracle where possible, PPO, SAC, TD3. Baseline implementation is pinned Stable-Baselines3; tuned parameters originate from a declared search on training seeds.

Per run record:

- algorithm/package version, policy architecture, optimizer and all hyperparameters;
- twin/task/backend hashes and resolved simulator parameters;
- seed and separate train/evaluation seeds;
- requested and actual environment transitions;
- episodic return, success, length, constraint violations;
- wall time, environment FPS, learner updates/sec, inference latency;
- CPU/GPU/RAM, OS, Python, compiler, driver/CUDA where relevant;
- commit and dirty-worktree status.

Evaluation uses deterministic policies where algorithm-appropriate, at least 100 episodes per seed for stable success estimates, and fixed held-out initial states. Time limits are truncations, not terminations.

Statistical report:

- raw learning curves per seed;
- mean ± standard deviation for continuity;
- median and interquartile mean (IQM);
- stratified bootstrap 95% confidence intervals;
- performance profiles over normalized task scores when multiple tasks exist;
- probability of improvement for pairwise algorithm/backend claims.

Five seeds are the release smoke minimum. Comparative research claims target at least 10 independent seeds and must state any deviations.

### B4 — Reconstruction

Dataset tiers:

- synthetic objects with exact geometry/cameras/scale;
- permissively licensed tabletop scans with reference meshes;
- a documented in-house capture set that can legally be released.

Methods: COLMAP baseline; selected learned multi-view method only after license/hardware review; single-image method as an explicitly non-metric visual baseline.

Metrics:

- camera pose error (where ground truth exists);
- scale error;
- accuracy/completeness and Chamfer distance after declared alignment;
- normal consistency, watertightness, connected components, non-manifold edges;
- simplified collision proxy error and triangle count;
- contact-relevant dimensional error at annotated surfaces;
- runtime, peak RAM/VRAM, input count, failure rate;
- optional PSNR/SSIM/LPIPS only for view-synthesis outputs, never as geometry evidence.

Each result records capture conditions, masks/depth/calibration, model/checkpoint hash, checkpoint/data license, preprocessing, and user interventions.

### B5 — Workflow usability

After the editor works, conduct a small preregistered task study:

- import and configure a known articulated model;
- identify/fix injected unit, inertia, joint-axis, and collision errors;
- compile, run, and create a simple RL task.

Measure completion rate, time, errors remaining, validation messages used, and standardized usability feedback. Compare KinetiWeave to a documented direct-format workflow; do not claim general usability from developer self-testing.

## Hardware tiers

| Tier | Purpose | Example constraints |
|---|---|---|
| L | Laptop reference | 4–8 CPU cores, 16 GB RAM, integrated graphics acceptable, no CUDA requirement |
| W | Workstation | 12+ CPU cores, 32+ GB RAM, one consumer NVIDIA/AMD GPU |
| C | Optional cloud | Exact instance/GPU image and hourly cost recorded |

The M1 correctness and headless benchmarks must run on Tier L. Learned reconstruction and massive parallel simulation may be W/C-only but cannot be required for core authoring.

## Experiment lifecycle

```text
immutable config + source + assets
              |
          resolve / hash
              |
         warm-up and run
              |
      append-only raw metrics
              |
        evaluate held-out set
              |
    aggregate with confidence intervals
              |
     signed/checksummed result bundle
```

Failed and interrupted runs remain in the manifest with reason/status. Exclusion criteria are declared before aggregation. A benchmark report cannot overwrite raw data.

## Versioning and regression policy

- Correctness fixtures run in CI; performance runs on controlled scheduled hardware.
- A schema/backend change invalidates the affected benchmark key.
- Flag >10% median regression in environment throughput or >20% peak-memory regression; investigate before release.
- Learning regressions require multiple seeds and uncertainty analysis, not a single CI training run.
- Published result tables link to immutable artifact hashes and the exact source tag.

## First executable benchmark matrix

| ID | Task | Backend | Mode | Seeds/runs | Purpose |
|---|---|---|---|---|---|
| KW-B0-001 | one-hinge fixture | compiler | headless | deterministic | schema/compiler correctness |
| KW-B1-001 | unactuated pendulum | MuJoCo | headless | 30 timings | physics trace + throughput |
| KW-B1-002 | unactuated pendulum | PyBullet | headless | 30 timings | secondary backend delta |
| KW-B2-001 | actuated pendulum | MuJoCo/Gymnasium | headless | 30 timings | wrapper overhead |
| KW-B3-001 | actuated pendulum | SB3 PPO/SAC/TD3 | headless | 5 smoke, 10 report | learning and reproducibility |

## Prohibited claims

- “Real-time” without a stated model, hardware, rendering mode, and rate.
- “Best” or “state of the art” without a preregistered fair comparison.
- “Digital twin” as proof of real-world fidelity without calibration/validation.
- Geometry quality based only on screenshots or view-synthesis metrics.
- Reproducibility based on a seed alone without software/hardware/artifact provenance.
