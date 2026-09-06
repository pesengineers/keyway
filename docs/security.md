# Security

## Deployment

Keep the service on a private Docker network shared with n8n. The compose example binds only to `127.0.0.1` for local testing. Do not publish it directly to the internet. Add authenticated ingress before any broader network exposure.

## Implemented controls

- Request models reject unknown fields and path traversal in job IDs.
- `/v1/process/local` accepts only regular files under `LOCAL_SOURCE_ROOTS`, resolves symlinks before checking roots, enforces a size limit, and allows known video extensions.
- ffmpeg and ffprobe run without a shell and use fixed argument arrays. Requests cannot supply commands or media arguments.
- The analysis API uses an explicit timeout. API keys come from environment injection and are not logged or returned.
- Processing concurrency defaults to one.
- Temporary data stays below `TEMP_DIR` and is removed after success or failure.
- Artifact writes are atomic.
- The container runs as an unprivileged user, drops Linux capabilities, blocks privilege escalation, and uses a read-only root filesystem in Compose.

## Operational requirements

Mount `/media` read-only. Mount writable storage at `/models`, `/output`, and `/tmp/keyway`; do not rely on the container writable layer. Restrict file permissions on transcript and result mounts because processed material may be sensitive. Rotate analysis credentials through Docker secrets or another secret-injection mechanism; never place a populated `.env` in Git.

Review logs before forwarding them centrally. Current logs include filenames and diagnostic errors but not transcript text or authorization headers.

## Deferred hardening

Authentication/authorization, request-rate policy, cancellation of in-flight inference, malware scanning, artifact retention, dependency/image scanning, and constrained SharePoint retrieval require production threat modeling before public or cross-trust-boundary deployment.
