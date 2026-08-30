---
title: KinetiWeave Studio
emoji: 🦾
colorFrom: orange
colorTo: gray
sdk: docker
app_port: 7860
fullWidth: true
pinned: false
license: apache-2.0
tags:
  - robotics
  - reinforcement-learning
  - 3d
  - mujoco
  - gymnasium
  - cad
---

# KinetiWeave Studio

Turn real-world captures and engineering geometry into reusable 3D objects and transparent,
runnable reinforcement-learning environments.

The public CPU Space supports a session-scoped Object Library, STEP/mesh import, 3D inspection, and
MuJoCo + Gymnasium package export. Hosted storage may reset when the Space restarts. Video
reconstruction requires DA3 Small or COLMAP plus suitable compute; run the full laptop build from the
[open-source repository](https://github.com/divyanshu-iitian/kinetiweave).

Generated physics is a baseline, not automatically validated ground truth. Confirm scale, mass,
inertia, friction, collision behavior, tasks, and rewards before training or publishing results.
