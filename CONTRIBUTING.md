# Contributing to KinetiWeave

KinetiWeave values small, evidence-backed changes that are reproducible by someone outside the original team.

## Before proposing a change

1. Search existing issues and architecture decisions.
2. For a new subsystem, document the problem, alternatives, selected approach, limitations, and license impact.
3. Open an issue before work that changes a public schema or backend contract.
4. Do not include credentials, proprietary CAD, restricted datasets, or model weights.

## Development rules

- Treat SI units and coordinate frames as API, not convention-by-memory.
- Keep core schemas independent of simulator, renderer, GUI, and RL library.
- Add deterministic unit tests and contract tests with each implementation.
- Record seed, configuration, dependency versions, commit, hardware, and timing for experiments.
- Use at least five seeds for reported RL comparisons unless a written power/resource analysis justifies otherwise.
- Never silently drop unsupported fields during format conversion.
- Mark incomplete functionality **Experimental** or **Planned**.
- Do not add a UI action unless it performs a real, tested operation.

## Dependency and asset intake

Every new dependency, model, dataset, or asset must record:

- canonical source and immutable version or digest;
- license and required attribution;
- whether commercial use and redistribution are allowed;
- transitive or checkpoint/data license constraints;
- reason it is needed and rejected alternatives.

Strong copyleft components may be used as separate user-installed tools after review, but are not vendored into Apache-2.0 packages. Non-commercial artifacts cannot be part of the default redistributable distribution.

## Pull requests

- Use conventional commit subjects such as `feat:`, `fix:`, `docs:`, `test:`, `bench:`, or `chore:`.
- Explain user-visible behavior, design tradeoffs, verification, and license impact.
- Include benchmark deltas for performance claims.
- Run `python scripts/check_repository.py` before requesting review.

By contributing, you agree that your contribution is licensed under Apache-2.0.
