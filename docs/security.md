# Security

## Deployment

Keep the service on a private Docker network shared with n8n. The compose example binds only to `127.0.0.1` for local testing. Do not publish it directly to the internet. Add authenticated ingress before any broader network exposure.

## Implemented controls

- **Input & Model Validation**: Pydantic models forbid extraneous fields and enforce strict regex checks on job IDs (preventing path traversal) and filenames.
- **Path Containment (`LOCAL_SOURCE_ROOTS`)**: `/v1/process/local` strictly verifies that resolved source paths reside within configured local roots. Rejects symlinks escaping allowed trees.
- **Constrained Remote Ingestion**: `/v1/process/sharepoint` accepts only site ID, drive ID, item ID, and sanitized filename. Prevents arbitrary SSRF or external URL downloads.
- **Size & Memory Protections**: Streaming media downloads enforce a hard upper bound (`MAX_SOURCE_BYTES`, default 50 GB) and write directly to disk rather than buffering in memory.
- **Process Isolation**: `ffmpeg` and `ffprobe` are invoked via fixed parameter arrays (`subprocess.run` with `shell=False`, stdin tied to `/dev/null`). Callers cannot supply or inject arbitrary shell arguments.
- **Execution Timeouts**: Every phase carries explicit timeouts: `PROCESS_TIMEOUT_SECONDS` (default 7200s for media/transcription), `ANALYSIS_TIMEOUT_SECONDS` (default 120s for LLM inference), and `GRAPH_TIMEOUT_SECONDS` (default 300s for download).
- **Concurrency Backpressure**: Host-level concurrency semaphore (`MAX_CONCURRENT_JOBS`, default 1) prevents GPU VRAM exhaustion or CPU starvation.
- **Secret Protection**: API keys and OAuth client secrets are injected via environment variables as Pydantic `SecretStr`. They are never logged, formatted, or included in error traces.
- **Deterministic Lifecycle Cleanup**: Temporary audio WAVs and downloaded media binaries are managed with context managers and deleted in `finally` blocks upon success, failure, or timeout.
- **Atomic Artifact Writes**: Results (`transcript.txt`, `result.json`) are written to hidden temporary files before atomic filesystem rename (`os.replace`), preventing partial reads by downstream pollers.
- **Container Hardening**: Container executes as unprivileged user `worker` (UID/GID 10001), drops `ALL` Linux capabilities, blocks privilege escalation (`no-new-privileges`), and mounts root filesystem as read-only.

## Operational requirements

Mount `/media` read-only. Mount writable storage at `/models`, `/output`, and `/tmp/keyway`; do not rely on the container writable layer. Restrict file permissions on transcript and result mounts because processed material may be sensitive. Rotate analysis credentials through Docker secrets or another secret-injection mechanism; never place a populated `.env` in Git.

Review logs before forwarding them centrally. Current logs include filenames and diagnostic errors but not transcript text or authorization headers.

## Production Threat Model & Boundary Constraints

- **Internal Network Boundary**: Keyway is designed specifically as an internal back-end service worker. It must never be exposed directly to the public internet or untrusted tenants. If placed behind a proxy or gateway, implement mTLS, Bearer token header verification, or API gateway authentication.
- **Artifact Access Control**: `OUTPUT_DIR` contains verbatim audio transcripts and sensitivity findings. Ensure host filesystem permissions on Unraid (`/mnt/user/appdata/keyway/output`) restrict access to authorized administrators and the n8n container user.
- **GPU Resource Segregation**: When deploying on multi-GPU hosts, select dedicated GPUs via stable UUIDs (`NVIDIA_VISIBLE_DEVICES="GPU-..."`) to prevent contention with other GPU workloads.
