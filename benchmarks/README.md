# Benchmarks

The first executable benchmark is `actuated-link-v1`. Its immutable contract ships inside the Python
package at `src/kinetiweave/contracts/actuated-link-v1.json`; runtime reports are written atomically to
`var/benchmarks/actuated-link-latest.json` and can be exported from Studio or the API.

It compares MuJoCo RK4 against a separately implemented rigid-link RK4 oracle, verifies the compiled
parameters, repeats the simulator trace, and hashes both canonical traces. Local runtime evidence is
deliberately ignored by Git: published benchmark claims must use an immutable result bundle with
hardware/software provenance under the protocol in `docs/research/04-benchmark-plan.md`.
