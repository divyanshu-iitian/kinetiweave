# Security policy

## Reporting

Do not open a public issue for a vulnerability. Use GitHub's private vulnerability reporting for this repository. If that is unavailable, contact the repository owner privately through their GitHub profile.

Include affected version/commit, impact, prerequisites, minimal reproduction, and suggested mitigation. Do not include real robot credentials, tokens, personal data, or proprietary assets.

## Scope

Security-sensitive areas include untrusted 3D parsers, archive extraction, model/checkpoint loading, subprocess simulator adapters, browser/API boundaries, ROS 2 bridges, and deployment to physical robots.

KinetiWeave is not currently approved to command physical hardware. Future sim-to-real features will require explicit safety interlocks, bounded controls, authentication, audit logs, and human emergency-stop procedures.

## Supported versions

There is no released runtime yet. This policy will be updated before the first executable release.

