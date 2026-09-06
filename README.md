# keyway

A small Docker service for local video transcription and structured training-content review. n8n remains responsible for orchestration and SharePoint write-back.

The worker accepts a mounted local video or a SharePoint item reference, normalizes its audio with ffmpeg, transcribes it locally with faster-whisper, analyzes the transcript with a local Ollama model (or an OpenAI-compatible API), and emits `transcript.txt` plus `result.json`.

**New here?** Read [`AGENTS.md`](AGENTS.md) first, then [`docs/runbook.md`](docs/runbook.md). Current status lives in [`docs/deployment-journal.md`](docs/deployment-journal.md).

## Interfaces

### CLI

Requires Python 3.11+, ffmpeg, and ffprobe.

```console
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"
copy .env.example .env
python -m app.cli process "C:\path\to\video.mp4" --output output
```

Linux/macOS environments use `.venv/bin/pip`. Keep `ANALYSIS_API_KEY` in the environment or an uncommitted `.env`. The command writes:

- `output/transcript.txt`
- `output/result.json`

The default transcription configuration is `small.en`, automatic CUDA detection, GPU `float16`, and CPU `int8`. Override it with `WHISPER_MODEL`, `WHISPER_DEVICE`, and `WHISPER_COMPUTE_TYPE`.

### HTTP API

Run locally:

```console
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Configure `LOCAL_SOURCE_ROOTS` as a JSON array of approved mounted directories. Then request processing:

```console
curl -X POST http://127.0.0.1:8000/v1/process/local \
  -H "Content-Type: application/json" \
  -d '{"source_path":"/media/2021-08-19 training.mp4","job_id":"n8n-123"}'
```

Or request remote processing from SharePoint via Microsoft Graph:

```console
curl -X POST http://127.0.0.1:8000/v1/process/sharepoint \
  -H "Content-Type: application/json" \
  -d '{"job_id":"n8n-124","site_id":"pesengineers.sharepoint.com,root","drive_id":"b!abc","item_id":"01XYZ","filename":"2021-08-19 training.mp4"}'
```

The SharePoint endpoint requires `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`, and `GRAPH_CLIENT_SECRET` in the environment. It streams the file into the temporary directory with strict timeout and size limits, executes the pipeline, and removes the downloaded video in a finally block.

Artifacts are written to `OUTPUT_DIR/<job_id>/`. `GET /health` is liveness; `GET /ready` verifies ffmpeg, ffprobe, analysis configuration, and writable runtime mounts. Run one Uvicorn worker so the configured process-local concurrency limit remains authoritative.

The local endpoint is for mounted development and trusted private-network use. It rejects paths outside `LOCAL_SOURCE_ROOTS`; it does not fetch URLs.

## Docker

Published image: **`ghcr.io/pesengineers/keyway:latest`**, built by GitHub Actions on every push to `main` (tests must pass). Immutable `main-<sha>` tags exist for pinning and rollback.

```console
docker pull ghcr.io/pesengineers/keyway:latest
docker compose -f compose.example.yml up        # CPU by default; see the file for GPU
```

Building locally (`docker build -t keyway .`) is only needed for development.

The same CUDA-runtime image runs without a GPU when `WHISPER_DEVICE=cpu`. For NVIDIA, expose the selected GPU to the container and leave the Whisper device and compute type on `auto`. Models are downloaded at runtime and persist through the `/models` mount.

The compose example binds the API only to loopback. In production, remove the host port and attach this service and n8n to the same private Docker network.

## Result

Successful `result.json` files include filename/date provenance, title, synopsis, sensitivity classification and reason, transcription model/device/compute type, source duration, transcription time, realtime factor, total time, and warnings. Sensitivity is one of `safe`, `internal_only`, or `review_required`.

Filename dates use a leading valid `YYYY-MM-DD` and take precedence over model inference.

## Documentation

- [AGENTS.md](AGENTS.md): rules and orientation for humans and agents working on this repo
- [Runbook](docs/runbook.md): rebuild from nothing, operate, repair, decommission
- [Deployment journal](docs/deployment-journal.md): what has been done, when, and what is next
- [Architecture](docs/architecture.md) and [decision records](docs/decisions/README.md)
- [Security](docs/security.md)
- [Unraid and NVIDIA deployment](docs/unraid-deployment.md): host facts, SSH, GPU UUIDs, Ollama, benchmarks
- [n8n integration](docs/n8n-integration.md): live instance survey, existing workflows, contract, field mapping

## Development checks

```console
.venv/Scripts/python -m pytest
```
