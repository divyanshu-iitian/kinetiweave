from __future__ import annotations

import gymnasium as gym
import mujoco
import numpy as np
from gymnasium import spaces

from kinetiweave.benchmark import _contract_mjcf, load_actuated_link_contract
from kinetiweave.domain import ActuatedLinkContract

ENVIRONMENT_ID = "KinetiWeave/ActuatedLink-v1"


class ActuatedLinkEnv(gym.Env):
    """Deterministic MuJoCo control environment backed by the v1 link contract."""

    metadata = {"render_modes": []}

    def __init__(self, contract: ActuatedLinkContract | None = None):
        self.contract = contract or load_actuated_link_contract()
        self.model = mujoco.MjModel.from_xml_string(_contract_mjcf(self.contract))
        self.data = mujoco.MjData(self.model)
        self.action_space = spaces.Box(-1.0, 1.0, shape=(1,), dtype=np.float32)
        self.observation_space = spaces.Box(
            low=np.array([-1.0, -1.0, -1e6]),
            high=np.array([1.0, 1.0, 1e6]),
            dtype=np.float64,
        )

    def _observation(self) -> np.ndarray:
        angle = float(self.data.qpos[0])
        return np.array(
            [np.cos(angle), np.sin(angle), float(self.data.qvel[0])],
            dtype=np.float64,
        )

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        super().reset(seed=seed)
        mujoco.mj_resetDataKeyframe(self.model, self.data, 0)
        mujoco.mj_forward(self.model, self.data)
        return self._observation(), self._info(0.0)

    def step(self, action):
        normalized = float(np.clip(np.asarray(action, dtype=np.float64)[0], -1.0, 1.0))
        torque = normalized * self.contract.torque_limit_nm
        self.data.ctrl[0] = torque
        mujoco.mj_step(self.model, self.data)
        angle = float(self.data.qpos[0])
        velocity = float(self.data.qvel[0])
        reward = -(angle**2 + 0.1 * velocity**2 + 0.001 * torque**2)
        finite = bool(np.isfinite(self.data.qpos).all() and np.isfinite(self.data.qvel).all())
        return self._observation(), reward, not finite, False, self._info(torque)

    def _info(self, torque_nm: float) -> dict[str, float | str]:
        return {
            "contract_id": self.contract.id,
            "time_s": float(self.data.time),
            "torque_nm": torque_nm,
        }

    def close(self) -> None:
        pass


def register_actuated_link() -> str:
    if ENVIRONMENT_ID not in gym.registry:
        contract = load_actuated_link_contract()
        gym.register(
            id=ENVIRONMENT_ID,
            entry_point="kinetiweave.reference_env:ActuatedLinkEnv",
            max_episode_steps=round(contract.duration_s / contract.timestep_s),
        )
    return ENVIRONMENT_ID
