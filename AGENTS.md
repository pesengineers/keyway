# Working on Keyway

Read this first. It applies to humans and coding agents alike.

## What this is

Keyway is a single-container worker that turns an internal training video into a transcript plus reviewed metadata (title, synopsis, sensitivity, presentation date). n8n orchestrates it and writes results to SharePoint. Keyway deliberately has no scheduler, queue, database, UI, or SharePoint write-back. Keep it that way.

## Where things are

| Need | Go to |
|---|---|
| **Where things stand right now, what to do next, what is unresolved** | **`docs/STATUS.md` (read this first)** |
| What happened in each session, chronologically | `docs/deployment-journal.md` |
| Day-to-day operation without touching code (statuses, resets, weekly review) | `docs/operations.md` |
| Rebuild everything from nothing, repairs, deployments | `docs/runbook.md` |
| Why the code is shaped the way it is | `docs/architecture.md`, `docs/decisions/` |
| Unraid host, GPU UUIDs, SSH, Ollama, benchmarks | `docs/unraid-deployment.md` |
| n8n contract, existing workflows, SharePoint IDs | `docs/n8n-integration.md` |
| Security posture and boundaries | `docs/security.md` |
| Open work | GitHub issues on `pesengineers/keyway` |

## Hard rules

1. **The Unraid host `pes-dev` is production.** Inspect before you create. Never overwrite, delete, or `chown -R` anything you did not create. Back up before editing any existing file. Prefer append-only, idempotent commands. If unsure, stop and ask.
2. **Existing n8n workflows are read-only reference.** `PES Video Metadata - Seed Queue` and `PES Video Metadata - Process Queue` must not be edited, activated, or executed. Build Keyway workflows as new, separately named workflows (duplicate first if you need a starting point).
3. **No secrets in the repo, ever.** API keys, OAuth secrets, and tokens come from environment variables or 1Password. `.env` is gitignored; `.env.example` shows the shape only. Logs must never contain transcript text or authorization headers.
4. **Do not widen scope.** No new queues, schedulers, databases, UIs, or "while we're here" abstractions. Keyway stays small and boring.
5. **Document as you go.** Every session that touches the host, n8n, Entra, or GitHub settings appends to `docs/deployment-journal.md` and updates `docs/STATUS.md` (state table, unresolved list, "last updated"). Every behavior change gets a `CHANGELOG.md` line. If you discover a hardware or platform quirk, write it into the relevant doc immediately. A stale STATUS.md is a bug.
6. **Verify on the real path.** Unit tests are necessary but not sufficient; two production bugs were only found by running the container on the P2000. Use `scripts/bench.sh` or an equivalent end-to-end run before declaring deployment work done.
7. **PowerShell users:** never paste multi-line remote commands; here-strings emit CRLF and wrapped lines corrupt files on the host. One line per command, or use the Unraid web terminal. Never paste Unraid's "docker run" Apply output anywhere; it contains masked secrets in plaintext.
8. **Do not bloat the workstation.** Never install the `Microsoft.Graph` meta-module (or any comparable "install everything" SDK bundle); install only the specific sub-modules a script imports. Do not install any module, package, or tool without saying exactly what will be installed first.

## Local development in 60 seconds

```console
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"      # .venv/bin/pip on Linux/macOS
.venv/Scripts/python -m pytest -q
```

ffmpeg/ffprobe must be on `PATH` for real runs (`winget install Gyan.FFmpeg` on Windows). `WHISPER_DEVICE=cpu WHISPER_COMPUTE_TYPE=int8` works on any machine.

## Tooling available to agents

- `ssh pes-dev` (alias in `~/.ssh/config`) for host access; see `docs/unraid-deployment.md` for key setup.
- n8n MCP server: `.omp/mcp.json` defines `n8n-pesdev`; it needs `N8N_PES_MCP_API_Key` in the environment (stored in 1Password as "n8n PES Dev API Key"). Read-only tools are safe; do not call `publish_workflow`, `archive_workflow`, or any `*_data_table*` mutation against the existing workflows or the `video_metadata_queue` table without explicit approval.
- `gh` CLI is authenticated for `pesengineers`.

## Definition of done for any change

- Tests pass (`pytest`), and new behavior has a test only where a plausible bug would fail it.
- `CHANGELOG.md` updated.
- Relevant doc updated (not a new doc unless a new topic).
- Journal entry written if the host, n8n, or GitHub issues were touched.
- Committed with a descriptive message and pushed to `main`.
