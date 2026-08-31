# Actuated-link reproducibility decision

**Date:** 2026-08-31  
**Status:** implemented bounded reference milestone

## Decision

KinetiWeave ships one small experiment whose complete meaning fits in a versioned JSON contract. It
authors timestep, duration, gravity, link length, mass, center-of-mass inertia, joint damping and
limits, initial angle and velocity, torque limit, and numerical tolerances. The same contract drives:

- an MJCF compiler and MuJoCo RK4 state trace;
- an independent rigid-link equation and RK4 integrator;
- a deterministic MuJoCo replay;
- compiled-model parameter introspection; and
- a registered Gymnasium environment.

The result is a portable report containing every sample, numerical errors, checks, simulator version,
and canonical SHA-256 trace identities. Runtime reports remain local by default so a machine-specific
result cannot silently become a published benchmark claim.

## Research basis

- [MuJoCo's computation documentation](https://mujoco.readthedocs.io/en/stable/computation/index.html)
  defines the simulator state and numerical pipeline. KinetiWeave records position and velocity rather
  than inferring motion from rendering.
- [MuJoCo's XML reference](https://mujoco.readthedocs.io/en/stable/XMLreference.html) documents joint
  damping, inertial properties, actuators, integrators, keyframes, timestep, and gravity. The benchmark
  reads these values back from the compiled `MjModel`; loading XML alone is not counted as fidelity.
- [Gymnasium's environment guidance](https://gymnasium.farama.org/tutorials/gymnasium_basics/environment_creation/)
  requires declared spaces, the five-value step contract, and seeded reset behavior. The reference
  environment is exercised with Gymnasium's official environment checker and same-seed reset test.
- OmniSim's public [contribution guidance](https://github.com/omnilink-tech/omnisim/blob/main/CONTRIBUTING.md)
  correctly emphasizes that a simulator can load and step while being physically wrong. KinetiWeave
  adopts the principle but implements its own contract, MuJoCo compiler, independent oracle, report
  schema, and product UI; no OmniSim code or branding is incorporated.

## Why an independent oracle

Running the same MuJoCo model twice proves replay stability, not correctness. Wrapping the same engine
behind two APIs would have the same weakness. The oracle evaluates the rigid-link equation directly:

`I_pivot q̈ = torque - damping q̇ - mass × gravity × COM_distance × sin(q)`

where `I_pivot` is calculated from the authored center-of-mass inertia using the parallel-axis term.
Both paths use the same bounded, piecewise-constant torque schedule and timestep, but they do not share
simulation state or MuJoCo dynamics calls.

## Acceptance gate

A run passes only when:

- all nine authored parameters match their compiled values within `1e-12`;
- all simulator and reference states are finite;
- maximum angle and angular-velocity errors remain within contract tolerances; and
- a second MuJoCo run reproduces every sampled state within `1e-12`.

The current local verification produced 401 samples, zero compiled-parameter drift, zero deterministic
replay error, and errors at floating-point roundoff. These numbers are development evidence, not a
cross-machine published result; the exported report carries the exact simulator version and run time.

## Limits and next comparisons

This benchmark is intentionally one rigid link. It does not validate contacts, constraints with
multiple degrees of freedom, sensors, rendering, RL convergence, or sim-to-real transfer. A future
OmniSim comparison would require an independently authored adapter for this exact contract and must
report parameter mismatches before comparing traces. Results are not comparable if either system
changes timestep, gravity, inertia convention, limits, initial state, actuation schedule, or sampling
semantics.
