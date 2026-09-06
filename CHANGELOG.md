# Changelog

## Unreleased

- Add Ollama analysis backend (`ANALYSIS_BACKEND=ollama`) using structured `format` output; no API key required.
- Add constrained SharePoint source via Microsoft Graph (`POST /v1/process/sharepoint`) with streaming download, size cap, and cleanup.
- Fix CUDA compute-type selection: `auto` now queries device capabilities instead of assuming `float16`; Pascal GPUs (Quadro P2000) resolve to `float32`.
- Fix image defaults so `MODEL_CACHE_DIR`, `TEMP_DIR`, and `OUTPUT_DIR` match the declared volumes; previously a bare `docker run` cached models inside the temp mount.
- Document Unraid SSH setup, P2000 GPU UUIDs, and benchmark results; add n8n integration guide and sensitivity evaluation set.

## 0.1.0 - 2026-09-05

- Add fixed-argument ffmpeg audio normalization and faster-whisper transcription with automatic CUDA selection and CPU INT8 fallback.
- Add strict OpenAI-compatible transcript analysis for title, synopsis, sensitivity, reason, and optional presentation date.
- Add CLI artifact generation and a constrained mounted-file FastAPI endpoint.
- Add CPU/NVIDIA Docker deployment with persistent model, temporary-file, and artifact mounts.
