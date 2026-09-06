# Architecture

## Boundary

`keyway` owns media normalization, local speech-to-text, transcript analysis, and processing telemetry. n8n owns scheduling, orchestration, SharePoint metadata updates, and human-review routing. The worker has no queue, scheduler, database, SharePoint write-back, or general-purpose command surface.

## Processing flow

1. A caller identifies one mounted local video.
2. The worker resolves and validates the file against configured roots for HTTP requests.
3. A per-job directory is created below `TEMP_DIR`.
4. Fixed ffprobe and ffmpeg argument lists read duration and produce mono 16 kHz PCM WAV audio.
5. faster-whisper transcribes the WAV with `small.en` by default. `auto` selects CUDA when CTranslate2 reports an available CUDA device and otherwise selects CPU INT8. A failed auto-selected CUDA run retries once on CPU INT8.
6. An `AnalysisBackend` produces strict structured output. Supported backends include:
   - `openai`: Calls OpenAI or an OpenAI-compatible `/chat/completions` endpoint with `json_schema` response format. Requires `ANALYSIS_API_KEY`.
   - `ollama`: Calls local Ollama `/api/chat` with structured `format` JSON schema. Does not require an API key by default.
7. The worker atomically writes `transcript.txt` and `result.json`.
8. The temporary job directory is removed in a `finally` path.

A leading valid `YYYY-MM-DD` filename date takes precedence over a date inferred by the analysis model. Inference is accepted only when the transcript explicitly supplies a date; otherwise the value is unknown.

## Source adapter seam

The proven processing boundary is a validated local filesystem path. A future SharePoint adapter should download or stream a constrained Graph item into the managed job directory, then call the same processor. It should accept site, drive, and item identifiers—not an arbitrary URL—and must validate expected filename, size, redirect hosts, and timeouts. n8n should not proxy video bytes.

## Concurrency

The FastAPI process uses a semaphore configured by `MAX_CONCURRENT_JOBS`, default 1. Deploy one Uvicorn worker. Multiple application workers each create their own semaphore and would violate the intended host-wide limit.
