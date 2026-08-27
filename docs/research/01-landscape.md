# Open-source landscape

**Reviewed:** 2026-08-27
**Decision scope:** components to integrate, wrap, benchmark, or use only as references.

## Executive conclusion

KinetiWeave should not build a physics engine, RL algorithm library, mesh kernel, or reconstruction foundation model. Its useful contribution is a rigorous, simulator-neutral digital-twin and task specification; loss-aware compilers; an editor built on those contracts; and reproducible evaluation across existing tools.

The laptop-first default stack is MuJoCo + Gymnasium + Stable-Baselines3. PyBullet is the first secondary backend because it is lightweight and permissively licensed. Gazebo/ROS 2 and Webots are later integration targets; SAPIEN/ManiSkill and Isaac Lab are benchmark/reference targets whose GPU/platform or licensing constraints make them unsuitable defaults.

## Evaluation rubric

Each project was assessed on purpose, license, maintenance, laptop/OS fit, modularity, reproducibility, and overlap with KinetiWeave. “Integrate” means a normal dependency; “adapter” means an optional boundary; “reference/benchmark” means no code dependency.

## Simulation and environment APIs

| Project | Purpose and source | License | Strengths | Weaknesses / constraints | Decision |
|---|---|---|---|---|---|
| MuJoCo | Contact-rich multibody physics; [repository](https://github.com/google-deepmind/mujoco) | Apache-2.0 | Mature robotics dynamics, MJCF, native Python, cross-platform binaries, strong Gymnasium ecosystem; optional MJX acceleration | MJCF-specific semantics and contact parameters; renderer is not an editor | **Integrate first** behind `SimulatorBackend`; compile canonical schema to MJCF |
| PyBullet / Bullet | General physics and Python robotics bindings; [repository](https://github.com/bulletphysics/bullet3) | zlib, except separately marked files | Easy laptop installation, broad format support, direct GUI/headless use | Python API and documentation are less cohesive; release cadence and numerical behavior differ from MuJoCo | **Optional second adapter** and cross-backend comparison |
| Gymnasium | Standard single-agent environment API; [documentation](https://gymnasium.farama.org/) | MIT | Maintained `reset`/`step` contract, wrappers, checkers, seeding conventions | Not a robotics data model or simulator abstraction | **Integrate as public RL API** |
| Gymnasium Robotics | MuJoCo robotics/goal environments; [documentation](https://robotics.farama.org/main/) | Apache-2.0 | Maintained goal API and familiar manipulation baselines | Environment assets/semantics remain MuJoCo-oriented | **Reference and benchmark**; adopt compatible goal semantics where useful |
| Gazebo Sim | Robotics simulator with pluggable physics/rendering/sensors; [documentation](https://gazebosim.org/libs/sim/) | Apache-2.0 | ROS ecosystem, SDF, rich sensors and transport, multiple physics engines | Heavy installation and distributed system complexity; Gazebo Classic is EOL | **Later process adapter**; target modern Gazebo only |
| Webots | Integrated robot simulator/editor; [documentation](https://www.cyberbotics.com/doc/guide/index) | Apache-2.0 | Cross-platform desktop experience, sensors, many robot examples | Own world/model conventions; less aligned with high-throughput RL | **Reference and later export target** |
| SAPIEN | Physics-rich embodied-AI platform; [repository](https://github.com/haosulab/SAPIEN) | Apache-2.0 code; inspect assets separately | Articulation, rendering, and manipulation ecosystem | GPU/Vulkan/platform requirements; assets have independent terms | **Benchmark/reference**, optional adapter after laptop core |
| Isaac Lab / Isaac Sim | GPU-parallel robot learning; [repository](https://github.com/isaac-sim/IsaacLab) | Isaac Lab BSD-3; Isaac Sim includes proprietary terms | Massive parallelism, RTX sensors, domain randomization | NVIDIA hardware/software footprint and mixed dependency terms | **External benchmark/export target**, never default |

### Simulator boundary lesson

Simulator formats are not interchangeable serialization syntaxes. MJCF, URDF, SDF, and USD differ in frames, actuator semantics, defaults, constraint models, sensors, and materials. KinetiWeave must produce a compile report containing approximations, warnings, and unsupported fields rather than promise lossless conversion.

## Reinforcement learning

| Project | Purpose and source | License | Strengths | Weaknesses / constraints | Decision |
|---|---|---|---|---|---|
| Stable-Baselines3 | Reliable PyTorch baselines; [repository](https://github.com/DLR-RM/stable-baselines3) | MIT | PPO/SAC/TD3, Gymnasium support, checkers, community hyperparameters | Deliberately not a fully modular research framework; single-machine focus | **First training integration**, called through our run specification |
| RL Baselines3 Zoo | Training/evaluation/tuning around SB3; [repository](https://github.com/DLR-RM/rl-baselines3-zoo) | MIT | Reproducible configs and tuned baselines | Configuration conventions are tied to SB3 ecosystem | **Reference/adapt experiment metadata**, do not fork |
| CleanRL | Auditable single-file implementations; [repository](https://github.com/vwxyzjn/cleanrl) | MIT | Excellent research reference, benchmarked scripts, explicit details | Explicitly not intended as an importable modular library | **Reference baseline**, optional subprocess runner later |
| TorchRL | Modular PyTorch-first RL stack; [documentation](https://docs.pytorch.org/rl/) | BSD-3-Clause | Collectors, TensorDict, transforms, performance tooling | Larger abstraction surface than required for the first baseline | **Evaluate after M4** for advanced research |
| RLlib | Distributed RL runtime; [documentation](https://docs.ray.io/en/latest/rllib/) | Apache-2.0 | Scales runners/learners across clusters; multi-agent support | Operational and dependency weight conflicts with laptop-first baseline | **Future scale adapter**, not core dependency |

The training layer owns metadata and orchestration, not algorithms. An algorithm plugin receives a Gymnasium environment factory and a typed run configuration, then returns checkpoints and metrics in a standard artifact layout.

## Robotics platforms and benchmark suites

| Project | Purpose and source | License notes | Relevance and decision |
|---|---|---|---|
| ROS 2 | Robot middleware; [documentation](https://docs.ros.org/en/rolling/) | Core commonly Apache-2.0/BSD; DDS vendors vary | Later bridge for state, commands, sensors, rosbag/MCAP, and sim-to-real. Keep out of core package. |
| MoveIt 2 | Motion planning/manipulation on ROS 2; [documentation](https://moveit.picknik.ai/) | Primarily BSD-3-Clause; verify package-by-package | Later validation/planning bridge, not an RL or physics backend. |
| panda-gym | Goal-conditioned Panda tasks on PyBullet; [repository](https://github.com/qgallouedec/panda-gym) | MIT | Useful small secondary-backend comparison and API reference. |
| ManiSkill | GPU-parallel manipulation benchmark; [repository](https://github.com/haosulab/ManiSkill) | Apache-2.0 code; assets include CC BY-NC 4.0 | Benchmark ideas and external comparison; non-commercial assets cannot enter default distribution. |
| robosuite | Modular MuJoCo manipulation; [repository](https://github.com/ARISE-Initiative/robosuite) | BSD-3-Clause | Reference controllers, task composition, sensors, and demonstrations. |
| LeRobot | Real-robot datasets, policies, hardware interfaces; [repository](https://github.com/huggingface/lerobot) | Apache-2.0 code; datasets/models vary | Future dataset/model publication interoperability; not initial RL baseline. |
| Meta-World | Multi-task/meta-RL manipulation benchmark; [repository](https://github.com/Farama-Foundation/Metaworld) | MIT | Later task-diversity comparison after single-task correctness. |
| LIBERO | Lifelong robot learning tasks/demonstrations; [repository](https://github.com/Lifelong-Robot-Learning/LIBERO) | MIT code, CC BY 4.0 dataset | Later knowledge-transfer reference; GPU and imitation-learning scope exceed initial milestone. |

## 3D, geometry, and authoring

| Project | Purpose and source | License | Decision |
|---|---|---|---|
| Blender | DCC, mesh editing, Python automation; [source](https://projects.blender.org/blender/blender) | GPL-3.0-or-later | Invoke as a separate optional tool; do not embed/link Blender code into Apache packages. |
| Three.js | Browser 3D engine; [repository](https://github.com/mrdoob/three.js) | MIT | Studio renderer and import preview. |
| React Three Fiber | React renderer for Three.js; [repository](https://github.com/pmndrs/react-three-fiber) | MIT | Studio scene composition; mutations flow through commands to the canonical model. |
| Open3D | Point clouds, registration, reconstruction; [repository](https://github.com/isl-org/Open3D) | MIT; audit bundled optional components | Optional reconstruction/geometry adapter. |
| trimesh | Python mesh IO and analysis; [repository](https://github.com/mikedh/trimesh) | MIT; optional engines vary | First server-side geometry adapter with a strict allowlist of optional dependencies. |
| MeshLab / PyMeshLab | Mesh processing; [repository](https://github.com/cnr-isti-vclab/PyMeshLab) | GPL-3.0 | Separate user-installed process only if needed; not a linked core dependency. |

GLB is the preferred visual interchange format. STL has no standard scale/material; OBJ lacks articulation; each import therefore requires units and provenance. Collision meshes are derived artifacts, never assumed equivalent to visuals.

## Reconstruction candidates

| Approach/project | Strength | Main limitation | Decision |
|---|---|---|---|
| COLMAP | Auditable structure-from-motion and multi-view stereo; [docs](https://colmap.github.io/) | Needs overlap/texture; compute-heavy dense stage | **First classical baseline** through a process adapter |
| NeRF | High-quality novel-view representation; [paper](https://arxiv.org/abs/2003.08934) | Scene-specific optimization; density field is not simulation-ready geometry | Research reference/visual preview, not collision source |
| 3D Gaussian Splatting | Fast high-quality view synthesis; [paper](https://doi.org/10.1145/3592433) | Official implementation is research-only; splats are not watertight meshes | Benchmark permissive implementations only; never treat splats as collision geometry |
| DUSt3R | Pose-free pairwise pointmaps and global alignment; [paper/code](https://github.com/naver/dust3r) | Code/checkpoints are non-commercial and dataset-constrained | Research-only adapter outside default distribution |
| Depth Anything V2 | Strong monocular depth prior; [repository](https://github.com/DepthAnything/Depth-Anything-V2) | Scale ambiguity; model-size licenses differ | Optional depth prior after checkpoint-specific review |
| Segment Anything 2 | General image/video segmentation; [repository](https://github.com/facebookresearch/sam2) | Masks do not establish geometry or object identity | Optional preprocessing plugin |
| InstantMesh / TripoSR class | Fast single-image asset generation | Hidden geometry is hallucinated; model/checkpoint terms vary | Experimental visual bootstrap only; multi-view is required for metric claims |

## Build / buy / wrap decisions

We will build the canonical model, validation system, compile reports, task schema, experiment manifest, editor interaction model, and benchmark harness. We will wrap physics, geometry, reconstruction, and RL systems. We will reference rather than integrate research-only/non-commercial projects. This boundary is the central defense against both technical lock-in and license contamination.

## Open questions

- Whether URDF or SDFormat should be the first interchange exporter after MJCF.
- How much inertia/collision derivation can be automatic without producing unsafe confidence.
- Which open, redistributable reconstruction checkpoint provides the best laptop-quality tradeoff.
- Whether the first ROS bridge targets Jazzy LTS or the active LTS at implementation time.
