# video-review-worker

A small Docker service for local video transcription and structured training-content review. n8n remains responsible for orchestration and SharePoint write-back.

The worker accepts a mounted local video, normalizes its audio with ffmpeg, transcribes it with faster-whisper, analyzes the transcript through an OpenAI-compatible API, and emits `transcript.txt` plus `result.json`.

## Status

Initial implementation. The CLI is the primary processing interface; the HTTP API is intended for private Docker-network use.

## Development

Requires Python 3.11+ and ffmpeg/ffprobe on `PATH`.

```console
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"
copy .env.example .env
python -m app.cli process "C:\path\to\video.mp4" --output output
```

Linux/macOS environments use `.venv/bin/pip` instead. Set `ANALYSIS_API_KEY` through the environment or a local uncommitted `.env` file.

Deployment and API documentation will be added with the Docker milestone.
