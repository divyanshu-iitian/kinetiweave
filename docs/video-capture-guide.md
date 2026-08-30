# Video capture guide

KinetiWeave estimates geometry and camera motion from overlapping views. Better capture usually
improves the result more than selecting a slower compute profile.

## Recommended capture

- Put the object on a textured, non-reflective surface in bright, soft, constant light.
- Keep the object completely still. Walk the camera around it instead of spinning the object.
- Record 15-40 seconds at 1080p or 4K and move slowly enough to avoid blur.
- Keep the complete object in frame and preserve roughly 70-85% overlap between nearby views.
- Make one level orbit and, when safe, a second partial orbit from a slightly higher angle.
- Avoid plain white objects, glass, chrome, moving people, changing shadows, and digital zoom.

The app examines duration, decodability, sharpness, and inter-frame motion. It samples sharp views
across the full timeline rather than simply taking every Nth frame.

## Laptop profiles

| Profile | Capture views | DA3 budget on this RTX 2050 | Use when |
|---|---:|---:|---|
| Fast laptop | 12 | up to 8 views at 336 px | Default; highest chance of fitting 4 GB VRAM |
| Balanced | 24 | capped to 8 views at 336 px | Better input selection, same safe DA3 budget |
| High detail | 40 | capped to 8 views at 336 px | Best candidates; useful with COLMAP or a larger GPU |

DA3 retries with fewer views after a CUDA out-of-memory error. Only one reconstruction worker runs
at once, preventing simultaneous jobs from exhausting RAM or VRAM.

## Interpreting the result

The default GLB is a colored point cloud with camera-estimated, relative scale. It is useful for
visual review and as a reconstruction artifact, but is not automatically a watertight mesh,
collision shape, metric CAD model, or simulation-ready rigid body. A future measurement/calibration
step must establish metric scale before physics values are trusted.
