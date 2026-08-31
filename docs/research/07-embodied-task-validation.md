# Embodied task and validation decision

**Date:** 2026-08-30  
**Status:** implemented baseline

## Decision

KinetiWeave's first manipulation environment uses a visible 2-DoF planar pusher. The policy controls
pusher velocity; the captured object moves only through simulator contact. Push-to-target exports use
a Gymnasium goal dictionary with `observation`, `achieved_goal`, and `desired_goal`, plus a dense
object-to-goal distance reward and a small control cost.

This replaces the earlier direct-force placeholder. Directly applying force to an unactuated object
was useful as a file-generation smoke test, but it did not define a credible robotics embodiment or
action interface.

## Evidence behind the shape

- [Gymnasium Robotics Fetch Push](https://robotics.farama.org/envs/fetch/push/) establishes a useful
  manipulation reference: Cartesian control, goal-aware dictionary observations, distance-based
  rewards, and an explicit success threshold. KinetiWeave follows those interface ideas without
  claiming Fetch-equivalent dynamics or copying its robot model.
- [MuJoCo modeling documentation](https://mujoco.readthedocs.io/en/stable/modeling.html) separates
  model elements, actuators, contacts, and simulation state. The generated MJCF therefore contains a
  real actuator transmission and contact geometry rather than an action-to-object-force shortcut.
- [MuJoCo mesh documentation](https://mujoco.readthedocs.io/en/stable/XMLreference.html#asset-mesh)
  explains that mesh collision uses a convex hull. KinetiWeave records `convex-hull` explicitly in
  the package manifest instead of presenting a reconstruction mesh as contact-faithful geometry.
- [MuJoCo Menagerie](https://github.com/google-deepmind/mujoco_menagerie) demonstrates curated,
  license-aware robot assets and a useful model/scene separation. Future arms should arrive through
  versioned, attributed asset adapters rather than being embedded as anonymous geometry.
- [Isaac Lab's environment design](https://isaac-sim.github.io/IsaacLab/main/source/overview/core-concepts/task_workflows.html)
  reinforces the distinction between reusable assets and task logic. KinetiWeave keeps imported
  objects in the Object Library and generates task-specific packages from them.

## Validation gate

Each generated package is compiled by MuJoCo, then executed through a deterministic 4.5-second
rollout. The report persists:

- finite generalized positions, velocities, and accelerations;
- minimum object height and maximum generalized speed;
- pusher/object contact count when the task requires contact;
- final object-to-target error; and
- compiled `nq`, `nv`, and `nu` dimensions.

A failed stability or contact check blocks the package. Users can re-run the same validation from the
Studio or API, and `validation.json` travels inside the ZIP.

## Limits

This is computational verification, not real-world system identification and not proof that an RL
policy learns the task. A convex hull can erase concavities, estimated inertia and friction can be
wrong, and a finite rollout cannot establish sim-to-real fidelity. The final target error is evidence,
not a benchmark result. Future releases need calibrated physical parameters, controlled learning
curves across multiple seeds, and robot-specific controller/asset adapters before making stronger
claims.
