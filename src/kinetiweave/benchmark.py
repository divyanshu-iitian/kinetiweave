from __future__ import annotations

import hashlib
import json
import math
import threading
import uuid
from importlib import resources
from pathlib import Path

import numpy as np

from kinetiweave.config import Settings
from kinetiweave.domain import (
    ActuatedLinkContract,
    BenchmarkReport,
    BenchmarkStatus,
    ParameterEvidence,
    TraceComparison,
    TracePoint,
    utc_now,
)


class BenchmarkUnavailableError(RuntimeError):
    pass


class BenchmarkService:
    """Runs and persists the bounded, simulator-neutral reference benchmark."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._run_lock = threading.Lock()

    @property
    def report_path(self) -> Path:
        return self.settings.benchmarks_dir / "actuated-link-latest.json"

    def get_contract(self) -> ActuatedLinkContract:
        return load_actuated_link_contract()

    def latest(self) -> BenchmarkReport:
        if not self.report_path.is_file():
            raise BenchmarkUnavailableError("No benchmark run exists yet.")
        return BenchmarkReport.model_validate_json(self.report_path.read_text(encoding="utf-8"))

    def run(self) -> BenchmarkReport:
        with self._run_lock:
            contract = self.get_contract()
            report = _run_contract(contract)
            self.settings.benchmarks_dir.mkdir(parents=True, exist_ok=True)
            temporary = self.report_path.with_suffix(".tmp")
            temporary.write_text(report.model_dump_json(indent=2), encoding="utf-8")
            temporary.replace(self.report_path)
            return report


def load_actuated_link_contract() -> ActuatedLinkContract:
    contract_file = resources.files("kinetiweave.contracts").joinpath("actuated-link-v1.json")
    return ActuatedLinkContract.model_validate_json(contract_file.read_text(encoding="utf-8"))


def _run_contract(contract: ActuatedLinkContract) -> BenchmarkReport:
    try:
        import mujoco
    except ImportError as exc:
        raise BenchmarkUnavailableError(
            "MuJoCo is required for the actuated-link benchmark. Install the rl extra."
        ) from exc

    model = mujoco.MjModel.from_xml_string(_contract_mjcf(contract))
    first_trace = _run_mujoco_trace(model, contract)
    replay_trace = _run_mujoco_trace(model, contract)
    reference_trace = _run_reference_trace(contract)

    simulator_values = np.array(
        [[point.angle_rad, point.angular_velocity_rad_s] for point in first_trace]
    )
    replay_values = np.array(
        [[point.angle_rad, point.angular_velocity_rad_s] for point in replay_trace]
    )
    reference_values = np.array(
        [[point.angle_rad, point.angular_velocity_rad_s] for point in reference_trace]
    )
    difference = simulator_values - reference_values
    replay_error = float(np.max(np.abs(simulator_values - replay_values)))
    angle_rmse = float(np.sqrt(np.mean(np.square(difference[:, 0]))))
    velocity_rmse = float(np.sqrt(np.mean(np.square(difference[:, 1]))))
    max_angle_error = float(np.max(np.abs(difference[:, 0])))
    max_velocity_error = float(np.max(np.abs(difference[:, 1])))

    parameters = _compiled_parameter_evidence(model, contract)
    parameter_fidelity = all(item.absolute_error <= 1e-12 for item in parameters)
    finite = bool(np.isfinite(simulator_values).all() and np.isfinite(reference_values).all())
    within_tolerance = (
        max_angle_error <= contract.angle_tolerance_rad
        and max_velocity_error <= contract.velocity_tolerance_rad_s
    )
    deterministic = replay_error <= 1e-12
    passed = parameter_fidelity and finite and within_tolerance and deterministic
    checks = [
        (
            "Authored timestep, gravity, mass, inertia, damping, limits, and initial "
            "state match the compiled MuJoCo model."
        )
        if parameter_fidelity
        else "One or more authored parameters changed during MuJoCo compilation.",
        "Independent RK4 dynamics agree with the MuJoCo state trace within the contract tolerances."
        if within_tolerance
        else "MuJoCo and independent RK4 state traces exceed the contract tolerances.",
        "A second run reproduced every sampled state within 1e-12."
        if deterministic
        else "The deterministic replay diverged beyond 1e-12.",
        "Every sampled state is finite." if finite else "A non-finite state was detected.",
    ]
    return BenchmarkReport(
        id=uuid.uuid4().hex,
        run_at=utc_now(),
        status=BenchmarkStatus.PASSED if passed else BenchmarkStatus.FAILED,
        contract=contract,
        simulator="MuJoCo RK4",
        simulator_version=mujoco.__version__,
        oracle="Independent rigid-link RK4",
        parameters=parameters,
        comparison=TraceComparison(
            samples=len(first_trace),
            angle_rmse_rad=angle_rmse,
            velocity_rmse_rad_s=velocity_rmse,
            max_angle_error_rad=max_angle_error,
            max_velocity_error_rad_s=max_velocity_error,
            deterministic_replay_max_error=replay_error,
            reference_trace_sha256=_trace_hash(reference_trace),
            mujoco_trace_sha256=_trace_hash(first_trace),
        ),
        reference_trace=reference_trace,
        simulator_trace=first_trace,
        checks=checks,
    )


def _contract_mjcf(contract: ActuatedLinkContract) -> str:
    inertia_z = max(contract.link_inertia_kg_m2 * 0.05, 1e-6)
    center = contract.link_length_m / 2
    return f'''<mujoco model="{contract.id}">
  <compiler angle="radian" autolimits="true"/>
  <option timestep="{contract.timestep_s:.17g}" gravity="0 0 -{contract.gravity_m_s2:.17g}"
          integrator="RK4"/>
  <worldbody>
    <body name="link" pos="0 0 0">
      <inertial pos="0 0 -{center:.17g}" mass="{contract.link_mass_kg:.17g}"
                diaginertia="{contract.link_inertia_kg_m2:.17g}
                             {contract.link_inertia_kg_m2:.17g} {inertia_z:.17g}"/>
      <joint name="hinge" type="hinge" axis="0 1 0"
             range="{contract.joint_limit_lower_rad:.17g} {contract.joint_limit_upper_rad:.17g}"
             damping="{contract.joint_damping_nms_rad:.17g}"/>
      <geom type="capsule" fromto="0 0 0 0 0 -{contract.link_length_m:.17g}"
            size="0.025" mass="0" contype="0" conaffinity="0" rgba="0.9 0.36 0.08 1"/>
    </body>
  </worldbody>
  <actuator>
    <motor name="hinge_torque" joint="hinge" gear="1"
           ctrlrange="-{contract.torque_limit_nm:.17g} {contract.torque_limit_nm:.17g}"/>
  </actuator>
  <keyframe>
    <key name="initial" qpos="{contract.initial_angle_rad:.17g}"
         qvel="{contract.initial_velocity_rad_s:.17g}" ctrl="0"/>
  </keyframe>
</mujoco>
'''


def _control_torque(time_s: float, limit_nm: float) -> float:
    torque = 0.35 * math.sin(2 * math.pi * 0.75 * time_s) + 0.1 * math.cos(
        2 * math.pi * 0.2 * time_s
    )
    return float(np.clip(torque, -limit_nm, limit_nm))


def _run_mujoco_trace(model, contract: ActuatedLinkContract) -> list[TracePoint]:
    import mujoco

    data = mujoco.MjData(model)
    mujoco.mj_resetDataKeyframe(model, data, 0)
    points = [
        TracePoint(
            time_s=0.0,
            torque_nm=_control_torque(0.0, contract.torque_limit_nm),
            angle_rad=float(data.qpos[0]),
            angular_velocity_rad_s=float(data.qvel[0]),
        )
    ]
    steps = round(contract.duration_s / contract.timestep_s)
    for step in range(steps):
        torque = _control_torque(step * contract.timestep_s, contract.torque_limit_nm)
        data.ctrl[0] = torque
        mujoco.mj_step(model, data)
        points.append(
            TracePoint(
                time_s=(step + 1) * contract.timestep_s,
                torque_nm=torque,
                angle_rad=float(data.qpos[0]),
                angular_velocity_rad_s=float(data.qvel[0]),
            )
        )
    return points


def _run_reference_trace(contract: ActuatedLinkContract) -> list[TracePoint]:
    state = np.array(
        [contract.initial_angle_rad, contract.initial_velocity_rad_s], dtype=np.float64
    )
    points = [
        TracePoint(
            time_s=0.0,
            torque_nm=_control_torque(0.0, contract.torque_limit_nm),
            angle_rad=float(state[0]),
            angular_velocity_rad_s=float(state[1]),
        )
    ]
    steps = round(contract.duration_s / contract.timestep_s)
    for step in range(steps):
        torque = _control_torque(step * contract.timestep_s, contract.torque_limit_nm)
        state = _rk4_step(state, torque, contract)
        points.append(
            TracePoint(
                time_s=(step + 1) * contract.timestep_s,
                torque_nm=torque,
                angle_rad=float(state[0]),
                angular_velocity_rad_s=float(state[1]),
            )
        )
    return points


def _rk4_step(state: np.ndarray, torque_nm: float, contract: ActuatedLinkContract) -> np.ndarray:
    step = contract.timestep_s

    def derivative(value: np.ndarray) -> np.ndarray:
        angle, velocity = value
        pivot_inertia = (
            contract.link_inertia_kg_m2 + contract.link_mass_kg * (contract.link_length_m / 2) ** 2
        )
        gravity_torque = -(
            contract.link_mass_kg
            * contract.gravity_m_s2
            * (contract.link_length_m / 2)
            * math.sin(angle)
        )
        acceleration = (
            torque_nm + gravity_torque - contract.joint_damping_nms_rad * velocity
        ) / pivot_inertia
        return np.array([velocity, acceleration], dtype=np.float64)

    k1 = derivative(state)
    k2 = derivative(state + step * k1 / 2)
    k3 = derivative(state + step * k2 / 2)
    k4 = derivative(state + step * k3)
    return state + step * (k1 + 2 * k2 + 2 * k3 + k4) / 6


def _compiled_parameter_evidence(model, contract: ActuatedLinkContract) -> list[ParameterEvidence]:
    import mujoco

    body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "link")
    joint = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "hinge")
    dof = int(model.jnt_dofadr[joint])
    values = [
        ("timestep", contract.timestep_s, float(model.opt.timestep), "s"),
        ("gravity", contract.gravity_m_s2, float(-model.opt.gravity[2]), "m/s²"),
        ("link mass", contract.link_mass_kg, float(model.body_mass[body]), "kg"),
        (
            "link inertia",
            contract.link_inertia_kg_m2,
            float(model.body_inertia[body, 1]),
            "kg·m²",
        ),
        (
            "joint damping",
            contract.joint_damping_nms_rad,
            float(model.dof_damping[dof]),
            "N·m·s/rad",
        ),
        (
            "lower joint limit",
            contract.joint_limit_lower_rad,
            float(model.jnt_range[joint, 0]),
            "rad",
        ),
        (
            "upper joint limit",
            contract.joint_limit_upper_rad,
            float(model.jnt_range[joint, 1]),
            "rad",
        ),
        (
            "initial angle",
            contract.initial_angle_rad,
            float(model.key_qpos[0, 0]),
            "rad",
        ),
        (
            "initial velocity",
            contract.initial_velocity_rad_s,
            float(model.key_qvel[0, 0]),
            "rad/s",
        ),
    ]
    return [
        ParameterEvidence(
            parameter=name,
            authored=authored,
            compiled=compiled,
            unit=unit,
            absolute_error=abs(authored - compiled),
        )
        for name, authored, compiled, unit in values
    ]


def _trace_hash(trace: list[TracePoint]) -> str:
    payload = [
        [
            round(point.time_s, 12),
            round(point.torque_nm, 12),
            round(point.angle_rad, 12),
            round(point.angular_velocity_rad_s, 12),
        ]
        for point in trace
    ]
    encoded = json.dumps(payload, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
