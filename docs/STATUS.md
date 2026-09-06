# Status: resume here

Last updated 2026-09-06 (end of session; n8n workflow created). This is the single page to read before doing anything. It states the exact state of every system Keyway touches, what is done, what is next, and what is unresolved. The chronological record is `docs/deployment-journal.md`; this page is the snapshot.

## One-paragraph summary

Keyway is deployed and working on the production Unraid host `pes-dev`. A real SharePoint video was pulled through Microsoft Graph, transcribed on the Quadro P2000, analyzed by a local Ollama model, and returned as structured JSON in 71 seconds. All six original GitHub issues are closed. The n8n workflow that feeds Keyway from the existing 100-item queue exists (`Keyway - Process Queue`, inactive, source in `n8n/`). What remains is operational: rotate one leaked secret, pick up the latest image, run the workflow once by hand, then activate it.

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
| Container `keyway` | **running, healthy**, image `ghcr.io/pesengineers/keyway:latest` pulled at 06:14 UTC (commit `dfbe1ad` era; does **not** yet include the 422/`NoSpeechDetected` change from `314281a`). No host port. Template on flash: `/boot/config/plugins/dockerMan/templates-user/my-keyway.xml` (+ a `.bak` from before the path fix). |
| Container `ollama` | running, `ollama/ollama` 0.33.3, model `llama3.2:3b` pulled, pinned to P2000, no host port, `OLLAMA_KEEP_ALIVE=2m` |
| Container `n8n` | untouched except for the added `keyway-net` attachment |
| GPUs | P2000 = `GPU-a16c6467-c3d8-cf56-6944-a53de59dcd6b` (index 1, target). P620 = `GPU-588d1004-...` (index 0, not exposed to anything of ours) |
| `/mnt/user/appdata/keyway/models` | 464 MB, `small.en` cached |
| `/mnt/user/appdata/keyway/output` | `graph-smoke-1/` (empty, silent file) and `graph-smoke-2/` (transcript + result of the Revit tutorial). Safe to delete; they were tests. |
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
- Queue: 100 rows, all `pending`, 26 GB. One is known silent (`Non-Technical-20251022_155731UTC-Meeting Recording.mp4`).
- **`Keyway - Process Queue`** (`mp5gviKuHu9iIfPo`) exists, **inactive**, deployed from `n8n/keyway-process-queue.workflow.ts`. Not yet test-run. Details and activation checklist: `docs/n8n-integration.md` §6.

### Workstation

- Repo checkout at `C:\Syncs\Resilio\Code\GitHub\pesengineers\keyway`, venv in `.venv`, ffmpeg via winget.
- `gh` authenticated as DailenG with `read:packages`,`write:packages`.
- Only `Microsoft.Graph.Authentication` and `Microsoft.Graph.Applications` PowerShell modules should be present (never the meta-module).

## Unresolved items, in priority order

1. **Rotate the Graph client secret.** Unraid printed the full `docker run` (with the secret) on Apply and it was pasted into a chat transcript. Run `.\scripts\New-KeywayGraphApp.ps1 -RotateSecret`, put the new value in the `keyway` template's `GRAPH_CLIENT_SECRET`, Apply, then delete the old secret in Entra (App registrations > Keyway Video Worker > Certificates & secrets). Runbook 1.7b and 1.8.
2. **Update the running container** to the image from `314281a` (CI is green): Docker tab, Check for Updates, Apply on `keyway`. This brings the 422-for-silence behavior the workflow depends on.
3. **Test and activate the Keyway workflow.** Open https://n8n.pesengineers.dev/workflow/mp5gviKuHu9iIfPo, confirm the SharePoint node shows credential `Sharepoint video process`, execute once manually, check that the oldest pending row becomes `done` (or `flagged_*`/`unprocessable`) and that the SharePoint item's Title/Synopsis were written. Then activate. Checklist in `docs/n8n-integration.md` §6. Consider a new seed workflow later that pages Graph and skips items already queued. The frozen workflows stay untouched.
4. **Delete the smoke-test output** directories under `/mnt/user/appdata/keyway/output/` when convenient.
5. **Analysis quality on real content is a known unknown.** Two real items look good (`safe`, sensible titles). The synthetic eval set is small. After the first 10 to 20 real jobs, review `result.json` files; if titles/sensitivity are weak, try `llama3.1:8b` with `WHISPER_COMPUTE_TYPE=int8_float32` (VRAM budget in ADR 003).
6. **Date inference will dominate.** Only 6 of 100 filenames carry a leading date; expect `presentation_date_source` to be `model` or `unknown` for most. Decide whether SharePoint's `Presentation_x0020_Date` should be left blank when `unknown`.
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
| Behavior changes | `CHANGELOG.md` |
