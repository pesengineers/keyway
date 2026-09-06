# 002: Local transcription with faster-whisper on the Quadro P2000

**Date:** 2026-09-05, amended 2026-09-06. **Status:** accepted.

## Context

96 of the first 100 queued videos exceed the 24 MB API upload limit; local transcription removes the limit, the CloudConvert dependency, and the data egress. The host has a Quadro P2000 (5 GB, Pascal) and a P620 (2 GB).

## Decision

- faster-whisper (CTranslate2) with `small.en`, selected by `WHISPER_MODEL`.
- `WHISPER_DEVICE=auto` picks CUDA when CTranslate2 reports a device, else CPU; a failed CUDA run retries once on CPU int8 and records a warning.
- `WHISPER_COMPUTE_TYPE=auto` queries `ctranslate2.get_supported_compute_types("cuda")` and prefers `float16 > int8_float16 > float32`. **Amendment 2026-09-06:** the original code assumed `float16`; the P2000 (compute 6.1) has none and would have silently fallen back to CPU. Discovered only by running on the hardware.
- GPU is selected by UUID in deployment config (`--gpus device=GPU-...` or `NVIDIA_VISIBLE_DEVICES`), never in application code. The P2000 is index 1 on this host.

## Evidence

Benchmark 2026-09-06, 56.5 min sample: cuda/float32 40.1 s (RTF 0.012, 1.5 GB VRAM); host CPU int8 93.8 s; dev laptop 294 s. Table in `docs/unraid-deployment.md`.

## Consequences

- ~1 minute end to end per hour of video on this hardware, including analysis.
- `medium.en` would fit in VRAM if accuracy needs increase; not yet evaluated.
- Any future GPU swap requires re-running `scripts/bench.sh`, not just changing the UUID.
