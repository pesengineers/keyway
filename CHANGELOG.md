# Changelog

## 0.1.0 - 2026-09-05

- Add fixed-argument ffmpeg audio normalization and faster-whisper transcription with automatic CUDA selection and CPU INT8 fallback.
- Add strict OpenAI-compatible transcript analysis for title, synopsis, sensitivity, reason, and optional presentation date.
- Add CLI artifact generation and a constrained mounted-file FastAPI endpoint.
- Add CPU/NVIDIA Docker deployment with persistent model, temporary-file, and artifact mounts.
