# Video-to-3D reconstruction decision

**Decision date:** 2026-08-28
**Status:** implemented vertical slice

## Hardware envelope

The target laptop has an Intel Core i5-13420H, 12 logical CPU threads, 15.6 GB RAM, an NVIDIA RTX
2050 with 4 GB VRAM, and approximately 45 GB of free system-disk space during implementation. The
runtime therefore uses a single worker, bounded uploads, bounded video duration, conservative frame
and resolution budgets, lazy model loading, and one controlled OOM retry.

## Selected path

[Depth Anything 3](https://github.com/ByteDance-Seed/depth-anything-3) Small is the default learned
reconstructor. Its official API accepts multiple images, estimates depth and camera poses, and
exports GLB and compact NPZ artifacts. The code and the
[DA3 Small model](https://huggingface.co/depth-anything/DA3-SMALL) are published under Apache-2.0.
KinetiWeave pins source commit `3d835ec1a5802d64a8b8b15f817a1ab54809bfe4` so setup does not
silently change behavior.

[COLMAP](https://colmap.github.io/) remains an optional classical structure-from-motion and
multi-view stereo backend. It is valuable for well-textured captures and produces inspectable
intermediate evidence, but the full Windows executable is a separate installation and dense
reconstruction can be much slower.

## Pipeline

```text
validated local upload
        -> video probe and temporal bins
        -> sharpest view per bin
        -> DA3 Small (depth + camera pose)
        -> filtered colored point cloud GLB + manifest
        -> real Three.js review viewport
```

Files are stored under UUID job directories. SQLite uses WAL mode for durable state. Artifact
downloads are restricted to paths recorded for that job, and the service binds to loopback by
default. The original video never leaves the machine; model-weight download is the only expected
network operation during first use.

## Alternatives considered

| Option | Decision | Reason |
|---|---|---|
| Video Depth Anything | future temporal-depth adapter | Temporal depth but does not by itself recover camera poses |
| DUSt3R / MASt3R | not a default | Upstream code/checkpoint licensing is non-commercial/share-alike |
| Nerfstudio / Gaussian splatting | future high-end plugin | Windows setup and 4 GB VRAM are poor defaults |
| OpenMVS | not in the core | AGPL-3.0 conflicts with the intended permissive core distribution |
| Monocular single-frame depth | rejected | Depth alone is not a multi-view 3D object model |

## Truthfulness and limits

- DA3 output is reported as a **colored point cloud**, not a surface mesh.
- Scale is relative unless a known measurement is provided.
- Repeated texture, reflections, thin structures, motion, and missing viewpoints can create gaps or
  duplicated surfaces.
- A visual reconstruction is not collision-ready or dynamically identified. Physics authoring,
  mesh repair, mass/inertia estimation, and validation remain separate stages.
