# Literature review

**Reviewed:** 2026-08-27  
**Question:** What evidence should shape a real-object-to-RL environment platform?

## Synthesis

The literature points to five separable problems: physically meaningful robot modeling, environment/API design, stable RL baselines, observation-to-geometry reconstruction, and sim-to-real validity. No paper eliminates the need for engineering judgment between them. In particular, photorealistic view synthesis does not imply metric, watertight, articulated, or contact-correct geometry.

KinetiWeave's research hypothesis is therefore architectural: a provenance-carrying, simulator-neutral model plus loss-aware compilation and statistically disciplined benchmarks can reduce the cost and ambiguity of creating robotics learning environments. This is an integration contribution until measured evidence demonstrates more.

## Physics and robot simulation

MuJoCo introduced an efficient contact dynamics engine aimed at model-based control ([Todorov, Erez & Tassa, 2012](https://doi.org/10.1109/IROS.2012.6386109)). Its generalized-coordinate formulation, actuator model, and robotics ecosystem make it a strong first backend, not a universal ground truth. Contact solver choices, time steps, friction models, and inertial errors can change learned behavior.

SAPIEN connects articulated object datasets, physics, rendering, and interaction tasks ([Xiang et al., 2020](https://openaccess.thecvf.com/content_CVPR_2020/html/Xiang_SAPIEN_A_SImulAted_Part-Based_Interactive_ENvironment_CVPR_2020_paper.html)). ManiSkill2/3 extend that direction with manipulation tasks and parallelized simulation. The lesson is that articulation-rich assets and reproducible task initialization matter as much as raw physics throughput.

Robosuite presents modular robot/task/controller composition on MuJoCo ([Zhu et al., 2020](https://arxiv.org/abs/2009.12293)). Meta-World supplies task diversity for multi-task/meta-RL ([Yu et al., 2020](https://proceedings.mlr.press/v100/yu20a.html)), while LIBERO focuses on knowledge transfer across lifelong manipulation tasks ([Liu et al., 2023](https://arxiv.org/abs/2306.03310)). KinetiWeave should begin with one inspectable control task; breadth before correctness would make failures hard to localize.

### Implication

The reference environment needs golden state traces, energy/contact sanity checks, explicit integrator/time-step configuration, and comparisons between compiled models. “It renders” is not physics validation.

## Environment interfaces and goal semantics

Gymnasium's current API distinguishes `terminated` (an MDP terminal state) from `truncated` (an external time/resource boundary). Conflating them biases bootstrapped value targets. KinetiWeave will make both conditions explicit in its task schema and compile them into a Gymnasium environment.

Gymnasium Robotics' `GoalEnv` separates observation, achieved goal, desired goal, and recomputable reward/termination functions ([multi-goal API](https://robotics.farama.org/main/content/multi-goal_api/)). This is useful for reach/push/pick tasks and Hindsight Experience Replay. It should be an optional task capability, not mandatory for every environment.

### Implication

Observations, actions, rewards, resets, termination, truncation, and randomization are versioned domain data. Arbitrary Python callbacks may be supported as an escape hatch but cannot be the only reproducible representation.

## RL algorithms and empirical reliability

PPO constrains policy updates with a clipped surrogate objective ([Schulman et al., 2017](https://arxiv.org/abs/1707.06347)); it is robust and parallel-friendly but on-policy and often sample hungry. TD3 reduces overestimation and policy-update error in deterministic actor-critic learning ([Fujimoto, van Hoof & Meger, 2018](https://proceedings.mlr.press/v80/fujimoto18a.html)). SAC combines off-policy learning with entropy regularization ([Haarnoja et al., 2018](https://proceedings.mlr.press/v80/haarnoja18b.html)). These complementary properties justify the requested PPO/SAC/TD3 baseline set for continuous control.

Stable-Baselines3 provides maintained implementations and explicitly recommends multiple runs, normalized inputs, tuned hyperparameters, and separate evaluation environments ([SB3 guidance](https://stable-baselines3.readthedocs.io/en/master/guide/rl_tips.html)). CleanRL is valuable as an auditable reference, but its maintainers explicitly describe it as non-modular and not intended to be imported.

Henderson et al. show that algorithm, codebase, hyperparameter, environment, and seed variance can reverse conclusions ([Deep Reinforcement Learning That Matters, 2018](https://doi.org/10.1609/aaai.v32i1.11694)). Agarwal et al. show that point estimates and a handful of runs are insufficient, recommending stratified bootstrap intervals, performance profiles, interquartile mean, and probability of improvement ([Deep RL at the Edge of the Statistical Precipice, 2021](https://arxiv.org/abs/2108.13264)).

### Implication

KinetiWeave reports raw per-run data, not only aggregate charts. Five seeds is the initial smoke/release minimum; important comparative claims should target 10+ seeds or document a resource/power rationale. Reports include IQM and bootstrap intervals alongside mean ± standard deviation for compatibility.

## 3D reconstruction and representation

Classical structure-from-motion and multi-view stereo remain an interpretable baseline; COLMAP combines general-purpose SfM and MVS pipelines ([Schönberger & Frahm, 2016](https://openaccess.thecvf.com/content_cvpr_2016/html/Schonberger_Structure-From-Motion_Revisited_CVPR_2016_paper.html); [Schönberger et al., 2016](https://openaccess.thecvf.com/content_eccv_2016/html/Johannes_Lutz_Schonberger_Pixelwise_View_Selection_ECCV_2016_paper.html)). Capture overlap, calibration, texture, blur, reflective surfaces, and scale recovery remain practical failure points.

NeRF represents a scene as a neural radiance field optimized from posed images ([Mildenhall et al., 2020](https://arxiv.org/abs/2003.08934)). It excels at novel-view synthesis but does not directly yield collision-ready topology. 3D Gaussian Splatting replaces expensive neural field sampling with explicit anisotropic Gaussians and fast rasterization ([Kerbl et al., 2023](https://doi.org/10.1145/3592433)); it remains a radiance representation, not automatically a watertight mechanical model.

DUSt3R predicts pointmaps from unconstrained image pairs and simplifies camera/geometry estimation ([Wang et al., 2024](https://openaccess.thecvf.com/content/CVPR2024/html/Wang_DUSt3R_Geometric_3D_Vision_Made_Easy_CVPR_2024_paper.html)). Its published code/checkpoint terms restrict commercial use, demonstrating why architecture and license evaluation cannot be separated.

Single-image reconstruction is structurally underdetermined: hidden shape, absolute scale, material, density, internal structure, articulation, and collision behavior cannot be observed from one RGB view. Generative priors can produce plausible visuals, but plausibility is not measurement.

### Implication

The first pipeline requires multi-view capture, a known scale reference or calibrated depth, confidence maps, provenance, and user review. It separates:

1. visual representation;
2. metric surface geometry;
3. simplified collision geometry;
4. articulated/link structure;
5. physical parameters.

No learned stage may silently invent physical properties.

## Digital twins and sim-to-real

Domain randomization trains across variations so reality may appear as another sampled domain ([Tobin et al., 2017](https://arxiv.org/abs/1703.06907)). Dynamics randomization can enable transfer of learned control policies ([Peng et al., 2018](https://arxiv.org/abs/1710.06537)). Both require plausible parameter distributions; randomizing an incorrectly structured model does not make it valid.

The “reality gap” includes geometry, mass/inertia, friction/contact, actuator latency, sensor noise, calibration, control frequency, and unmodeled compliance. A digital twin should therefore be treated as a versioned hypothesis with calibration evidence and uncertainty, not a perfect copy.

### Implication

KinetiWeave will attach origin and confidence to derived physical values, support calibration datasets, and preserve randomization distributions in task manifests. Sim-to-real is planned only after simulation verification and physical safety design.

## Research contribution boundaries

Initially, KinetiWeave contributes engineering integration and measurement:

- a canonical articulated/physical/task representation;
- traceable compilation to multiple simulators;
- a path from visual asset to reviewed simulation asset;
- reproducible RL and performance evaluation.

It does **not** claim a novel physics engine, reconstruction model, RL algorithm, or guaranteed sim-to-real transfer. Potential novelty must be established by future controlled experiments against direct workflows and existing authoring systems.

## Proposed research questions

1. How much time and semantic loss does a canonical schema save when porting the same task between MuJoCo and PyBullet?
2. Which validation checks most strongly predict unstable or non-transferable simulations?
3. What geometry simplification level best trades contact fidelity for simulation throughput?
4. How do classical and learned multi-view pipelines compare on metric geometry used for contact, not only novel-view quality?
5. Does provenance-guided author review reduce environment construction errors and time?

## Limitations of this review

This is a design-stage narrative review, not a systematic review or meta-analysis. Versions, licenses, and model terms can change. Every dependency/checkpoint must be re-audited at integration time and pinned to an immutable revision.

