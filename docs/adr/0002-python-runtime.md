# ADR-0002: Python 3.11+ for alarm-core

## Status
Accepted (confirmed by user; overrides the repo's original Visual
Studio/.NET-flavored `.gitignore`, which was a template default, not an
intentional choice)

## Context

The repo's original `.gitignore` was the stock Visual Studio template,
which hinted at a possible .NET intent. Meanwhile, the technical
requirements point strongly at Python.

## Decision

**Python 3.11+** for `alarm-core` and all services in this repo.

## Reasoning

- The Coral's official inference bindings (`pycoral` / `tflite-runtime`)
  are Python-first; C++/Go bindings exist but are far less ergonomic. (In
  this deployment the Coral itself stays with Frigate — see ADR-0001 — but
  Python remains the best-supported path for local ML tooling generally,
  including CPU/CUDA inference via ONNX Runtime for Tier 1.)
- `paho-mqtt` is the mature, standard MQTT client used by both Frigate and
  most of the HA ecosystem.
- Frigate itself is Python (FastAPI + a detector process) — sharing
  language keeps operational patterns (Docker base images, YAML config
  style, logging conventions) consistent for the user maintaining two
  adjacent services.
- HA's own ecosystem (Supervisor add-on tooling, custom integrations) is
  Python-first, keeping a future custom HA integration cheap if ever
  needed.

## Consequences

- `.gitignore` replaced with a Python + Docker ignore file.
- `services/alarm-core/` uses `pyproject.toml`, not a `.csproj`.
- Tier 1 local inference uses CPU or CUDA/ONNX Runtime on the host's i7 +
  NVIDIA GPU (not `pycoral`, since the Coral is committed to Frigate's
  primary detection).
