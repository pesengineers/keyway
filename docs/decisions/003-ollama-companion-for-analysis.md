# 003: Analysis runs in a separate Ollama container on the same host

**Date:** 2026-09-06. **Status:** accepted.

## Context

The analysis step (title, synopsis, sensitivity, date) needs an LLM. Options: OpenAI-compatible API (transcript text leaves the host), Ollama in a second container (nothing leaves), or Ollama baked into the Keyway image (couples two lifecycles).

## Decision

Ollama runs as its own container installed from Unraid Community Apps, on the private `keyway-net` network, pinned to the P2000, with no published host port. Keyway talks to it with `ANALYSIS_BACKEND=ollama`. The OpenAI-compatible backend remains available as a switch, not a default.

Model: `llama3.2:3b` to start. It produced a correct, grounded classification on the real sample and keeps combined VRAM (Whisper float32 + 3B) at ~4.1 GB of 5 GB.

## Consequences

- Keyway stays a single-purpose container (see 001); Ollama is managed like any other CA app.
- The two containers share the GPU sequentially. `OLLAMA_KEEP_ALIVE=2m` limits how long the LLM holds VRAM after a job. A collision (Whisper loading while the LLM is still resident) is survivable at 3B; for 7B/8B set Whisper to `int8_float32` first.
- Ollama compiles JSON Schema to a llama.cpp grammar and rejects string `minLength`/`maxLength`. Keyway sends a bound-free schema (`_OLLAMA_SCHEMA`) and relies on Pydantic for bounds. Keep the two schemas' `required` lists identical.
- Model quality on real content is a known unknown (see issue #7 and the synthetic eval set in `tests/data/`). Escalation path is a larger model, not a cloud API, unless quality proves insufficient.
