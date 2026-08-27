# License and attribution analysis

**Reviewed:** 2026-08-27
**Disclaimer:** engineering policy, not legal advice. Re-check exact versions and seek counsel for high-risk distribution.

## Project license decision

KinetiWeave original code and documentation use **Apache License 2.0**. It is permissive, compatible with commercial and academic use, includes an explicit patent grant/termination provision, and fits key dependencies such as MuJoCo, Gazebo, ROS 2 components, and LeRobot.

Apache-2.0 obligations include providing the license, retaining relevant notices, marking modified upstream files, and carrying applicable `NOTICE` content. The license does not grant trademark rights.

## Intake policy

No dependency, snippet, model, dataset, CAD file, texture, robot asset, or checkpoint enters the repository/default download until its exact version has:

1. canonical URL and owner;
2. SPDX license identifier or captured custom terms;
3. redistribution, modification, commercial-use, and attribution assessment;
4. transitive dependency and training-data/checkpoint review where relevant;
5. immutable revision/digest;
6. placement decision: link, vendor, optional external process, research-only, or reject.

Code license and asset/model license are separate decisions. A permissively licensed library can distribute non-commercial assets; a code checkpoint can inherit constraints from base weights or training datasets.

## Compatibility categories

| Category | Examples | Default handling |
|---|---|---|
| Permissive | Apache-2.0, MIT, BSD-2/3, zlib | May integrate; retain notices and attribution |
| Weak copyleft | MPL-2.0, LGPL variants | Case-by-case; preserve file/library separation and obligations |
| Strong copyleft | GPL-2/3, AGPL | Do not link/vendor into Apache packages without legal review; separate user-installed process may be acceptable |
| Non-commercial/research-only | CC BY-NC, custom INRIA research license, many checkpoints | Never in default commercial-friendly distribution; research adapter and user-supplied artifact only if terms allow |
| No license/unclear | Random CAD/model downloads | Treat as all-rights-reserved; reject redistribution/integration |

## Component register (design-stage)

| Component | License evidence | Intended use | Decision / obligations |
|---|---|---|---|
| MuJoCo | [Apache-2.0 license](https://github.com/google-deepmind/mujoco/blob/main/LICENSE) | First physics backend | Dependency; retain notices, record version |
| Gymnasium | [MIT license](https://github.com/Farama-Foundation/Gymnasium/blob/main/LICENSE) | Environment API | Dependency; reproduce copyright/license in distributions |
| Gymnasium Robotics | [Apache-2.0](https://github.com/Farama-Foundation/Gymnasium-Robotics/blob/main/LICENSE) | Reference/benchmarks | Do not copy assets blindly; inspect each model/source |
| PyBullet/Bullet | [zlib license](https://github.com/bulletphysics/bullet3/blob/master/LICENSE.txt) | Optional backend | Dependency; check separately marked files and data |
| Stable-Baselines3 | [MIT license](https://github.com/DLR-RM/stable-baselines3/blob/master/LICENSE) | First RL algorithms | Dependency; retain MIT notice |
| RL Baselines3 Zoo | [MIT license](https://github.com/DLR-RM/rl-baselines3-zoo/blob/master/LICENSE) | Config/reference | Prefer dependency/reference; attribute adapted configs |
| CleanRL | [MIT license](https://github.com/vwxyzjn/cleanrl/blob/master/LICENSE) | Research reference | Do not import as library; copied/adapted code requires notice |
| TorchRL | [BSD-3-Clause](https://github.com/pytorch/rl/blob/main/LICENSE) | Future adapter | Permissive; preserve notice/non-endorsement |
| Ray/RLlib | [Apache-2.0](https://github.com/ray-project/ray/blob/master/LICENSE) | Future distributed adapter | Optional dependency |
| Gazebo Sim | [Apache-2.0](https://gazebosim.org/libs/sim/) | Later external backend | Process/library adapter; component notices |
| Webots | [Apache-2.0](https://github.com/cyberbotics/webots/blob/master/LICENSE) | Later export/backend | Optional; bundled robot assets need individual review |
| SAPIEN | [Apache-2.0](https://github.com/haosulab/SAPIEN/blob/main/LICENSE) | Future benchmark/adapter | Optional; datasets/assets separate |
| Isaac Lab | [BSD-3-Clause framework](https://github.com/isaac-sim/IsaacLab/blob/main/LICENSE) | External benchmark/export | Isaac Sim and dependencies include proprietary terms; no default dependency |
| ManiSkill | [Apache-2.0 code](https://github.com/haosulab/ManiSkill/blob/main/LICENSE) | Benchmark reference | Assets include CC BY-NC 4.0; exclude from default redistributable bundle |
| robosuite | [BSD-3-Clause](https://github.com/ARISE-Initiative/robosuite/blob/master/LICENSE) | Benchmark/reference | Preserve notice; review robot assets |
| LeRobot | [Apache-2.0](https://github.com/huggingface/lerobot/blob/main/LICENSE) | Future datasets/models integration | Dataset/model cards and licenses mandatory |
| panda-gym | [MIT](https://github.com/qgallouedec/panda-gym/blob/master/LICENSE) | PyBullet comparison | Reference/dependency; inspect assets |
| Three.js | [MIT](https://github.com/mrdoob/three.js/blob/dev/LICENSE) | Browser renderer | Dependency; retain notice |
| React Three Fiber | [MIT](https://github.com/pmndrs/react-three-fiber/blob/master/LICENSE) | Studio renderer binding | Dependency; retain notice |
| trimesh | [MIT](https://github.com/mikedh/trimesh/blob/main/LICENSE.md) | Mesh IO/analysis | Dependency with optional-engine allowlist; optional triangulation engines may differ |
| Open3D | [MIT](https://github.com/isl-org/Open3D/blob/main/LICENSE) | Point-cloud/reconstruction adapter | Optional dependency; review bundled third parties |
| Blender | [GPL-3.0-or-later](https://projects.blender.org/blender/blender/src/branch/main/COPYING) | User-installed conversion/cleanup | Invoke as separate executable; do not embed or redistribute by default |
| PyMeshLab | [GPL-3.0](https://github.com/cnr-isti-vclab/PyMeshLab/blob/main/LICENSE) | Possible mesh processing | Avoid core dependency; separate optional process after review |
| COLMAP | [BSD-3-Clause](https://colmap.github.io/license.html) | Classical reconstruction baseline | Separate process; bundled third-party build can affect obligations |
| DUSt3R | [CC BY-NC-SA 4.0 code/checkpoints terms](https://github.com/naver/dust3r/blob/main/LICENSE) | Research-only learned comparison | No default distribution or commercial path; user-supplied research adapter only |
| 3D Gaussian Splatting reference | [custom research license](https://github.com/graphdeco-inria/gaussian-splatting/blob/main/LICENSE.md) | Research reference | Do not integrate; evaluate permissive independent implementations separately |
| Meta SAM 2 | [Apache-2.0 code/checkpoints](https://github.com/facebookresearch/sam2/blob/main/LICENSE) | Optional segmentation | Re-audit checkpoint and dependencies at integration |

## Asset provenance rules

Every asset manifest must record creator, source URL, retrieval date, original license, attribution text, modifications, units, and SHA-256. Robot manufacturer CAD is not assumed redistributable merely because it is downloadable. Brand names/logos and dataset subject/privacy rights are separate from copyright.

Generated assets retain provenance of all source images, base models, tools, and checkpoints. Outputs from a model are not automatically unencumbered; the tool terms, source rights, and jurisdiction can matter.

Preferred assets are original project-created, CC0, CC BY 4.0, or permissive code/data licenses. CC BY-SA requires share-alike analysis; CC BY-NC is excluded from the default distribution and commercial benchmarks.

## Model and dataset publication

Before publishing to Hugging Face, a model card must list base model/checkpoint, training dataset licenses, task/environment hashes, training configuration, evaluation, limitations, intended/out-of-scope uses, software license, weights license, and citation. If redistribution is unclear, publish only reproducible configuration and instructions—not weights or data.

Never upload API tokens, private telemetry, identifiable capture data, proprietary CAD, or robot credentials. Use repository secret scanning and pre-publication manifest checks.

## Required repository artifacts by implementation phase

- `THIRD_PARTY_NOTICES.md`: runtime and vendored code notices.
- `assets/manifest.json`: per-asset source/license/digest.
- `models/<name>/MODEL_CARD.md`: checkpoint-specific terms and evidence.
- `datasets/<name>/DATASET_CARD.md` or external links: collection/consent/license.
- dependency lockfiles and SBOM per release.
- automated allow/deny policy using SPDX IDs, with manual review for custom licenses.

These files will be added when the first third-party runtime artifact is integrated; an empty notice file would give false assurance.

## Key risks

1. **Asset license laundering:** converting CAD/mesh format does not change its license.
2. **Checkpoint mismatch:** repository code may be permissive while weights/data are non-commercial.
3. **Optional dependency surprise:** geometry packages can call separately installed tools with different terms.
4. **Format/model trademarks:** using a robot model does not grant manufacturer trademark rights.
5. **Copyleft coupling:** embedding/linking GPL code can impose distribution obligations; subprocess separation is not a universal legal safe harbor.
6. **License drift:** `main` branch terms can change; pin immutable versions and store evidence.

## Decision record

KinetiWeave will remain a clean-room integration layer: depend on compatible published APIs, do not copy implementation details unnecessarily, preserve attribution, and isolate incompatible/research-only systems behind opt-in adapters. Uncertain provenance means “do not ship,” not “ship and fix later.”
