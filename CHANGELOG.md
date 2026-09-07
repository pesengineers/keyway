# Changelog

## Unreleased

- Production go-live 2026-09-07: `Keyway - Process Queue` active; first row processed and written to SharePoint end to end.

- n8n: add `Keyway - Seed Queue` (daily, paginated Graph listing with de-duplication) and `Keyway - Reset Queue Rows` (login-protected form) alongside `Keyway - Process Queue`; add canvas notes, continue-on-error for the Keyway call, and route failures to the existing Sentry error workflow.
- Add `docs/operations.md`, a non-developer guide to statuses, the weekly review, resets, and troubleshooting.

- Discard model-supplied `presentation_date` unless the model's `presentation_date_evidence` appears verbatim in the transcript; schemas require the new field. Local and hosted models all fabricated dates otherwise.
- Rewrite the analysis system prompt: sensitivity is release risk, default `safe`, technical depth and internal authorship are explicitly not signals, reason must cite the passage.
- Production analysis backend switched to OpenRouter (`openai/gpt-4o-mini`) via the existing OpenAI-compatible client; Ollama retained as offline fallback (ADR 006).

- Add Ollama analysis backend (`ANALYSIS_BACKEND=ollama`) using structured `format` output; no API key required.
- Add constrained SharePoint source via Microsoft Graph (`POST /v1/process/sharepoint`) with streaming download, size cap, and cleanup.
- Fix CUDA compute-type selection: `auto` now queries device capabilities instead of assuming `float16`; Pascal GPUs (Quadro P2000) resolve to `float32`.
- Fix image defaults so `MODEL_CACHE_DIR`, `TEMP_DIR`, and `OUTPUT_DIR` match the declared volumes; previously a bare `docker run` cached models inside the temp mount.
- Document Unraid SSH setup, P2000 GPU UUIDs, and benchmark results; add n8n integration guide and sensitivity evaluation set.
- Publish `ghcr.io/pesengineers/keyway` from GitHub Actions on every push to `main`; Unraid pulls the image instead of building on the host.
- Add `scripts/New-KeywayGraphApp.ps1` to create the least-privilege Entra app (`Sites.Selected`) for SharePoint access, and `scripts/bench.sh` for on-host end-to-end benchmarks.
- Add `AGENTS.md`, `docs/runbook.md`, and `docs/decisions/` for handover.
- Return HTTP 422 with a distinct message when a recording contains no speech (`NoSpeechDetected`), so orchestrators can park silent files instead of retrying; consolidate error-to-status mapping in `_to_http()`.

## 0.1.0 - 2026-09-05

- Add fixed-argument ffmpeg audio normalization and faster-whisper transcription with automatic CUDA selection and CPU INT8 fallback.
- Add strict OpenAI-compatible transcript analysis for title, synopsis, sensitivity, reason, and optional presentation date.
- Add CLI artifact generation and a constrained mounted-file FastAPI endpoint.
- Add CPU/NVIDIA Docker deployment with persistent model, temporary-file, and artifact mounts.
