from __future__ import annotations

from pathlib import Path

import numpy as np

from kinetiweave.benchmark import BenchmarkService
from kinetiweave.config import Settings
from kinetiweave.reference_env import ActuatedLinkEnv, register_actuated_link


def test_actuated_link_matches_independent_reference_and_replays(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data")
    report = BenchmarkService(settings).run()

    assert report.status == "passed"
    assert report.comparison.samples == 401
    assert report.comparison.max_angle_error_rad <= report.contract.angle_tolerance_rad
    assert report.comparison.max_velocity_error_rad_s <= report.contract.velocity_tolerance_rad_s
    assert report.comparison.deterministic_replay_max_error == 0
    assert report.comparison.reference_trace_sha256 == report.comparison.mujoco_trace_sha256
    assert all(parameter.absolute_error == 0 for parameter in report.parameters)
    assert BenchmarkService(settings).latest().id == report.id


def test_actuated_link_is_a_deterministic_gymnasium_environment() -> None:
    from gymnasium.utils.env_checker import check_env

    environment = ActuatedLinkEnv()
    check_env(environment, skip_render_check=True)
    first, _ = environment.reset(seed=7)
    second, _ = environment.reset(seed=7)
    assert np.array_equal(first, second)
    assert register_actuated_link() == "KinetiWeave/ActuatedLink-v1"
