# Status: resume here

Last updated 2026-09-07 00:10 UTC (Process Queue activated). This is the single page to read before doing anything. It states the exact state of every system Keyway touches, what is done, what is next, and what is unresolved. The chronological record is `docs/deployment-journal.md`; this page is the snapshot.

## One-paragraph summary

Keyway is deployed and working on the production Unraid host `pes-dev` with a rotated Graph secret. The analysis step now runs through **OpenRouter / `openai/gpt-4o-mini`** after the local Ollama models misclassified the first real queue item (ADR 006); Ollama remains as an offline fallback. Model-supplied dates are now discarded unless backed by verbatim transcript evidence (commit `124e067`; deployed and verified on the host). Real SharePoint videos have been pulled through Microsoft Graph, transcribed on the Quadro P2000, analyzed by a local Ollama model, and returned as structured JSON. All six original GitHub issues are closed. The n8n workflow that feeds Keyway from the existing 281-item queue exists (`Keyway - Process Queue`, inactive, source in `n8n/`). **The pipeline is in production.** All three workflows are active. The first manual run (2507, row 1) and the first unattended scheduled run (2508, row 2) both completed cleanly; row 1 took 57 s: `safe`, title and synopsis written to the SharePoint item, filename date used, model-guessed date correctly discarded. Process Queue now runs every 5 minutes taking 2 rows per run (~24 videos/hour); the 279 remaining should finish in roughly 12 hours.

## State of each system

### GitHub: `pesengineers/keyway`

- `main` at `314281a`. Working tree clean. 39 tests pass.
- CI: `.github/workflows/publish-image.yml` builds and pushes `ghcr.io/pesengineers/keyway:latest` + `main-<sha>` on every push to `main`. Run for `314281a` was in progress at session end; check `gh run list --repo pesengineers/keyway --limit 1`.
- Package `ghcr.io/pesengineers/keyway` is **public** (org policy was changed to allow public packages on 2026-09-06).
- Open issues: **#7 only** (go-live checklist). Issues #1 through #6 closed with evidence.

### Unraid host `pes-dev.pes.local` (192.168.76.42)

| Item | State |
|---|---|
| SSH | `ssh pes-dev` works from this workstation (alias in `~/.ssh/config`, key `~/.ssh/id_ed25519`). 1Password `pes-dev` key also authorized. Details: `docs/unraid-deployment.md` "SSH access". |
| Network `keyway-net` | exists; members: `keyway`, `ollama`, `n8n` |
| Container `keyway` | **running, healthy**, Graph auth verified (200) with the rotated secret `ZFh…`; template `Default=` for the secret deliberately blanked so GUI edits cannot revert it; image `76481f8d` (commit `7db6310`, includes evidence-gated dates and the OpenRouter prompt; verified by A/B on `queue-2`). Template now has `ANALYSIS_BACKEND=openai`, `ANALYSIS_BASE_URL=https://openrouter.ai/api/v1`, `ANALYSIS_MODEL=openai/gpt-4o-mini`, masked `ANALYSIS_API_KEY`. No host port. Template on flash: `/boot/config/plugins/dockerMan/templates-user/my-keyway.xml` (+ a `.bak` from before the path fix). |
| Container `ollama` | running, `ollama/ollama` 0.33.3, models `llama3.2:3b` and `llama3.1:8b` pulled, pinned to P2000, no host port, `OLLAMA_KEEP_ALIVE=2m`. **Fallback only**; not in the production path. |
| Container `n8n` | untouched except for the added `keyway-net` attachment |
| GPUs | P2000 = `GPU-a16c6467-c3d8-cf56-6944-a53de59dcd6b` (index 1, target). P620 = `GPU-588d1004-...` (index 0, not exposed to anything of ours) |
| `/mnt/user/appdata/keyway/models` | 464 MB, `small.en` cached |
| `/mnt/user/appdata/keyway/output` | `queue-1/` (empty; 502 attempt) and `queue-2/` (transcript + result from the misclassified run; useful as an A/B fixture) |
| `/mnt/cache/keyway/tmp` | empty (correct) |
| `/mnt/user/appdata/keyway/src` | removed; no longer used |
| Leftovers | `/root/.ssh/authorized_keys.bak.*` and `.broken` from the SSH setup; harmless |

### Microsoft Entra / Graph

- App **Keyway Video Worker**, tenant `68e4d43b-0bf8-4363-8311-accdd3b62fa1`, client `90f1c65f-3d78-4569-b11d-d2fd6b73ef50`.
- Permission: `Sites.Selected` (application) with `read` granted on the Continuing Education site only. Verified working by a real download.
- Secret: in 1Password and in the `keyway` template as masked variable `GRAPH_CLIENT_SECRET`. **The current secret is compromised** (see Unresolved) and must be rotated.
- Created by `scripts/New-KeywayGraphApp.ps1`; re-run it to verify or rotate.

### n8n (`https://n8n.pesengineers.dev`, container on pes-dev)

- Agent access via built-in MCP server; token in env `N8N_PES_MCP_API_Key` (1Password "n8n PES Dev API Key"); registered in `.omp/mcp.json` as `n8n-pesdev`. Has write tools; use read-only ones unless approved.
- **Frozen, do not touch** (ADR 005): workflows `PES Video Metadata - Seed Queue` (`QuB7hRjGqdnPGRnF`) and `PES Video Metadata - Process Queue` (`84xNMHd9xDyKWgbd`), and the existing rows of data table `video_metadata_queue` (`QMOVCsZrJKJuT2Cz`).
- Queue: **281 rows, 82 GB** (earlier "100 rows" figure was an API page cap). All `pending` after rows 1 and 2 were reset via the new `Keyway - Reset Queue Rows` helper; row 1 has attemptCount 2, row 2 has 1. One is known silent (`Non-Technical-20251022_155731UTC-Meeting Recording.mp4`).
- Credential `OpenRouter Dailen Personal` (`v05xhPoiZRswGKCS`, type `openRouterApi`) exists in n8n; its value is not readable via API, so the same key is entered separately in the Keyway template. No OpenAI credential exists on the instance.
- **`Keyway - Process Queue`** (`mp5gviKuHu9iIfPo`), **active since 2026-09-07 00:08 UTC**, version `33171b76`. Execution 2507 was the first success (row 1 `done`, SharePoint PATCH confirmed). Canvas has section notes; Keyway HTTP node continues on connection errors; error workflow `Send Error to Sentry`.
- **`Keyway - Seed Queue`** (`S2RN9PNHdZFZoZYe`), **active**, daily 06:00. Verified: 281 in folder, 281 queued, 0 inserted.
- **`Keyway - Reset Queue Rows`** (`DOCflW4upDwPt2D4`), **active**. Form: https://n8n.pesengineers.dev/form/keyway-reset-rows (n8n login required; anonymous gets 404).
- **`Keyway - Queue Status`** (`GNv9dZFLTvgjTz9v`), **active**. Read-only HTML progress report at https://n8n.pesengineers.dev/form/keyway-status (login required). Registration verified from inside the container (302 to login) and in `webhook_entity`; **not yet confirmed rendering in a real browser session**, the user's first attempt hit the earlier broken version.
- All four have `errorWorkflow` = `Send Error to Sentry` (`IQ3r3rK0FdZl4E0Q`).

### Workstation

- Repo checkout at `C:\Syncs\Resilio\Code\GitHub\pesengineers\keyway`, venv in `.venv`, ffmpeg via winget.
- `gh` authenticated as DailenG with `read:packages`,`write:packages`.
- Only `Microsoft.Graph.Authentication` and `Microsoft.Graph.Applications` PowerShell modules should be present (never the meta-module).

## Unresolved items, in priority order

1. **Watch the first day.** After ~12 h (most of the backlog), review `done` titles/synopses and every `flagged_*`/`error`/`unprocessable` row per `docs/operations.md`.
2. **Open both form URLs in a signed-in browser once** and confirm the status page renders and the reset form shows its confirmation page; this is the only step not verified end to end.
3. **Spot-check SharePoint.** Open a few `done` items in the library and confirm Title, Synopsis, and Presentation Date look right to a human; Synopsis is truncated to 255 characters by the workflow for the column. Open https://n8n.pesengineers.dev/workflow/mp5gviKuHu9iIfPo, confirm the SharePoint node shows credential `Sharepoint video process`, execute once manually, check that the oldest pending row becomes `done` (or `flagged_*`/`unprocessable`) and that the SharePoint item's Title/Synopsis were written. Then activate. Checklist in `docs/n8n-integration.md` §6. Consider a new seed workflow later that pages Graph and skips items already queued. The frozen workflows stay untouched.
3. **Delete the old Graph secret in Entra** if not already done (App registrations > Keyway Video Worker > Certificates & secrets; keep only `keyway-20260906`). The rotated secret is verified working.
4. **Analysis quality.** gpt-4o-mini was correct on the item the local models got wrong. Still review the first 10 to 20 `result.json` files. The Ollama path is not recommended without the evidence-list schema redesign described in the 2026-09-06 journal entry.
5. **Dates.** Only 6 of 281 filenames carry a leading date and every model tested invented dates when none were spoken; with the evidence gate, expect `presentation_date_source=unknown` for most files and the SharePoint date column left blank (the workflow already omits it when null).
6. **Transcription accuracy is unmeasured.** `small.en` output reads correctly but WER on this audio is unknown; VAD removed 49 of 56 min on one sample. Planned check: listen-and-count on 3 files, compare `medium.en` (now affordable with no LLM on the GPU), add a jargon `initial_prompt`, surface `avg_logprob`. Deferred by user.
7. Minor: Ollama template still declares `OLLAMA_ORIGINS=*` (CORS; irrelevant with no host port). n8n is on both `bridge` and `keyway-net`; that is intended.

## How to verify the system is healthy right now

```sh
ssh pes-dev 'docker ps --filter name=keyway --filter name=ollama --format "{{.Names}} {{.Status}}"; docker exec n8n wget -qO- http://keyway:8000/ready; echo; nvidia-smi --query-gpu=index,memory.used --format=csv,noheader'
```

Expected: both `Up`, `{"status":"ready"}`, both GPUs near 0 MiB when idle.

## How to run one job by hand

From the host, any queued item (IDs come from the `video_metadata_queue` table; site and drive IDs are constant and listed in `docs/n8n-integration.md` §0):

```sh
ssh pes-dev 'printf "%s" "{\"job_id\":\"manual-1\",\"site_id\":\"<site>\",\"drive_id\":\"<drive>\",\"item_id\":\"<driveItemId>\",\"filename\":\"<fileName>\"}" > /tmp/j.json; docker run --rm --network keyway-net -v /tmp/j.json:/p.json:ro curlimages/curl -s -m 1200 -X POST http://keyway:8000/v1/process/sharepoint -H "Content-Type: application/json" -d @/p.json; rm /tmp/j.json'
```

Result lands in `/mnt/user/appdata/keyway/output/manual-1/`.

## Where every other answer lives

| Question | File |
|---|---|
| Rules for working here | `AGENTS.md` |
| Rebuild, deploy, roll back, repair, decommission | `docs/runbook.md` |
| What happened, session by session | `docs/deployment-journal.md` |
| Why it is designed this way | `docs/architecture.md`, `docs/decisions/` |
| Host facts, SSH, GPUs, Ollama template values, benchmarks | `docs/unraid-deployment.md` |
| n8n instance survey, existing workflows, contract, error codes | `docs/n8n-integration.md` |
| Security posture | `docs/security.md` |
| Traps already hit, as rules | `docs/lessons-learned.md` |
| Behavior changes | `CHANGELOG.md` |
