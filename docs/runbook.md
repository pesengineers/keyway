# Runbook

How to rebuild, operate, and repair Keyway. Written so a colleague or agent with no prior context can execute it. Every step was performed on `pes-dev` between 2026-09-05 and 2026-09-06; the journal has the narrative.

Conventions: commands prefixed `host$` run on the Unraid host (`ssh pes-dev`, you are root). Commands prefixed `dev$` run on a workstation checkout. Never run a `host$` command without reading the step's "safe because" note first.

---

## 1. Rebuild from nothing

### 1.1 Prerequisites

- Unraid 7.x with the **Nvidia-Driver** plugin installed and `docker info` listing the `nvidia` runtime.
- SSH as root (see `docs/unraid-deployment.md`, "SSH access to the host").
- GitHub access to `pesengineers/keyway`.
- On the workstation: Python 3.11+, `gh`, `git`, `ssh`.

### 1.2 Identify the GPU

```sh
host$ nvidia-smi --query-gpu=index,name,uuid,memory.total --format=csv
```

Use the **UUID** of the Quadro P2000 everywhere below. On `pes-dev` it is `GPU-a16c6467-c3d8-cf56-6944-a53de59dcd6b`. Do not use the index; it is not stable and the P2000 is currently index 1, not 0.

### 1.3 Host directories

Safe because: `mkdir -p` is a no-op on existing paths and `chown` is applied only to the three directories Keyway owns.

```sh
host$ mkdir -p /mnt/user/appdata/keyway/{models,output,src} /mnt/cache/keyway/tmp
host$ chown 10001:10001 /mnt/user/appdata/keyway/models /mnt/user/appdata/keyway/output /mnt/cache/keyway/tmp
```

| Host path | In container | Purpose |
|---|---|---|
| `/mnt/user/appdata/keyway/models` | `/models` | faster-whisper weights (~464 MB for small.en), persistent |
| `/mnt/user/appdata/keyway/output` | `/output` | `transcript.txt` + `result.json` per job |
| `/mnt/cache/keyway/tmp` | `/tmp/keyway` | scratch WAV per job; on SSD cache; always empty between jobs |

### 1.4 Private network

```sh
host$ docker network inspect keyway-net >/dev/null 2>&1 || docker network create keyway-net
```

Keyway, Ollama, and n8n all attach here. Nothing on this network publishes a host port except n8n (which already had one).

### 1.5 Ollama (Community Apps)

In the Unraid GUI: Apps, search `ollama`, install the official `ollama/ollama` template with these values. Everything else default.

| Field | Value |
|---|---|
| Name | `ollama` |
| Network Type | Custom: `keyway-net` |
| API Interface Port | **remove the row** (no host port) |
| `OLLAMA_HOST` | `0.0.0.0:11434` (keep; `127.0.0.1` would block Keyway) |
| `OLLAMA_KEEP_ALIVE` | `2m` |
| `NVIDIA_VISIBLE_DEVICES` | the P2000 UUID |
| `NVIDIA_DRIVER_CAPABILITIES` | `compute,utility` |
| Extra Parameters (Advanced View) | `--runtime=nvidia` |
| Data path | `/mnt/user/appdata/ollama` |

Then pull the model and verify:

```sh
host$ docker exec ollama ollama pull llama3.2:3b
host$ docker exec ollama nvidia-smi -L                     # exactly one GPU, the P2000
host$ docker run --rm --network keyway-net curlimages/curl -s http://ollama:11434/api/version
```

### 1.6 Get the Keyway image

Images are built by GitHub Actions and published to **`ghcr.io/pesengineers/keyway`** (public). Nothing is built on the host.

| Tag | Meaning |
|---|---|
| `latest` | most recent push to `main` that passed the test suite |
| `main-<sha>` | immutable tag for that commit; use for pinning or rollback |
| `X.Y.Z`, `X.Y` | created when a `vX.Y.Z` git tag is pushed |

```sh
host$ docker pull ghcr.io/pesengineers/keyway:latest
host$ docker run --rm --gpus '"device=GPU-a16c6467-c3d8-cf56-6944-a53de59dcd6b"' ghcr.io/pesengineers/keyway:latest \
        python -c "import ctranslate2 as c; print(c.get_cuda_device_count(), c.get_supported_compute_types('cuda'))"
```

The package must be **public** for anonymous pulls. If a pull returns `unauthorized`, see 3.6.

Expected: `1 {'float32', 'int8', 'int8_float32'}` (Pascal has no float16; the app handles this).

The base image is ~4.5 GB; first build takes 5 to 10 minutes. Rebuilds after `git pull` take under a minute.

### 1.7 Prove it end to end

Copy any sample video to `/mnt/cache/keyway/bench/` and run:

```sh
host$ curl -fsSL https://raw.githubusercontent.com/pesengineers/keyway/main/scripts/bench.sh -o /tmp/bench.sh && bash /tmp/bench.sh gpu-auto "/mnt/cache/keyway/bench/<file>.mp4"
```

Expected on the P2000 for a ~1 h video: `device: cuda`, `compute_type: float32`, transcription ~40 s, total ~60 s, peak VRAM ~4 GB (Whisper + 3B model resident). Then `rm -rf /mnt/cache/keyway/bench`.

### 1.7b Entra app registration for SharePoint access (Graph source only)

Needed for `POST /v1/process/sharepoint`. Skip if using a local mount. Repeatable; safe to re-run.

Prerequisites: Windows PowerShell 5.1 or 7 with exactly two sub-modules installed: `Install-Module Microsoft.Graph.Authentication, Microsoft.Graph.Applications -Scope CurrentUser`. **Do not install the `Microsoft.Graph` meta-module**; it pulls in the entire SDK (dozens of modules, gigabytes) and is never needed here. Sign in as a Global Administrator or Application Administrator who can grant admin consent (the site grant additionally needs SharePoint admin rights, which the delegated `Sites.FullControl.All` scope requires at sign-in).

```powershell
dev> .\scripts\New-KeywayGraphApp.ps1 -SiteId "pes1852.sharepoint.com,97c4bdef-10db-4a0a-b359-050ced66dd51,316269b2-8c0d-438a-9466-a3a1f9800a8a"
```

What it does, in order, each step skipped if already true:

1. Signs in interactively (browser) and creates application **Keyway Video Worker** (single tenant) plus its service principal.
2. Declares Microsoft Graph application permission **`Sites.Selected`** and grants admin consent programmatically (an app-role assignment, so nothing to click in the portal).
3. Grants the app **`read`** on the one SharePoint site (`/sites/{id}/permissions`). With `Sites.Selected` the app can see no other site in the tenant.
4. Creates a client secret (365 days) only if none is live, and writes it to `%USERPROFILE%\.keyway\graph-client-secret.txt` with an owner-only ACL. It is never printed. Put it in 1Password immediately, then delete the file.
5. Prints the `GRAPH_TENANT_ID` / `GRAPH_CLIENT_ID` values for the Keyway container.

Options:

- `-TenantWide`: use `Files.Read.All` instead of `Sites.Selected` (read access to every site; only if the site grant is not possible).
- `-RotateSecret`: add a new secret alongside the existing one. Deploy the new value to Keyway, verify, then remove the old secret in the portal (App registrations > Keyway Video Worker > Certificates & secrets).
- `-WhatIf`: show every step without changing anything.

Verify the grant without Keyway:

```powershell
dev> $t = (Invoke-RestMethod -Method Post -Uri "https://login.microsoftonline.com/<tenant>/oauth2/v2.0/token" -Body @{client_id="<client>";client_secret=(Get-Content "$env:USERPROFILE\.keyway\graph-client-secret.txt");scope="https://graph.microsoft.com/.default";grant_type="client_credentials"}).access_token
dev> Invoke-RestMethod -Headers @{Authorization="Bearer $t"} "https://graph.microsoft.com/v1.0/sites/<siteId>/drives" | % value | select name,id
```

A drive list means the app can read the library. A 403 means the site grant is missing (step 3) or consent has not propagated yet (wait a minute and retry).

Secret expiry is in 365 days from creation; put a calendar reminder at 11 months. Where secrets live is listed in section 4.

### 1.8 Run the service (Unraid Docker template)

Create it in the Unraid GUI so it is managed like every other container (update badge, restart policy, template saved on flash under `/boot/config/plugins/dockerMan/templates-user/`). Docker tab, **Add Container**, switch to **Advanced View**.

| Field | Value |
|---|---|
| Name | `keyway` |
| Repository | `ghcr.io/pesengineers/keyway:latest` |
| Network Type | Custom: `keyway-net` |
| Extra Parameters | `--runtime=nvidia --security-opt no-new-privileges:true --cap-drop ALL --read-only --tmpfs /run:size=16m` |
| Ports | none (n8n reaches it at `http://keyway:8000` on `keyway-net`) |

Paths:

| Container path | Host path | Access |
|---|---|---|
| `/models` | `/mnt/user/appdata/keyway/models` | RW |
| `/output` | `/mnt/user/appdata/keyway/output` | RW |
| `/tmp/keyway` | `/mnt/cache/keyway/tmp` | RW |

Variables. For `GRAPH_CLIENT_SECRET` set Display to Advanced and tick **Password/Mask** so it is hidden in the UI and in `docker inspect` output shown by the GUI.

| Key | Value |
|---|---|
| `NVIDIA_VISIBLE_DEVICES` | `GPU-a16c6467-c3d8-cf56-6944-a53de59dcd6b` |
| `NVIDIA_DRIVER_CAPABILITIES` | `compute,utility` |
| `ANALYSIS_BACKEND` | `ollama` |
| `ANALYSIS_BASE_URL` | `http://ollama:11434` |
| `ANALYSIS_MODEL` | `llama3.2:3b` |
| `ANALYSIS_TIMEOUT_SECONDS` | `600` |
| `MAX_CONCURRENT_JOBS` | `1` |
| `GRAPH_TENANT_ID` | `68e4d43b-0bf8-4363-8311-accdd3b62fa1` |
| `GRAPH_CLIENT_ID` | `90f1c65f-3d78-4569-b11d-d2fd6b73ef50` |
| `GRAPH_CLIENT_SECRET` | from 1Password (masked) |
| `GRAPH_TIMEOUT_SECONDS` | `600` |

Leave `WHISPER_*`, `MODEL_CACHE_DIR`, `TEMP_DIR`, `OUTPUT_DIR` unset; the image defaults are correct. Apply, then verify from inside n8n:

```sh
host$ docker exec n8n wget -qO- http://keyway:8000/ready      # {"status":"ready"}
```

For a local-mount source instead of Graph: add path `/media` -> the video library (read-only), add variable `LOCAL_SOURCE_ROOTS=["/media"]`, and omit the `GRAPH_*` variables.

Secrets go in the template as variables, never in env files on disk and never in the repo. Rotating the Graph secret is: run `New-KeywayGraphApp.ps1 -RotateSecret`, update the variable in the template, Apply, then delete the old secret in Entra.

Two Unraid GUI pitfalls seen on first creation:

- A **leading space in a host path** field makes Docker treat it as a named volume and fail with `includes invalid characters for a local volume name`. Paths must start with `/`. When repairing the template XML by hand, note each `<Config>` stores the value twice: in the `Default=` attribute and as the element text; the GUI reads the element text, so fix both.
- On Apply, Unraid prints the full `docker run` command **including masked variables in plaintext**. Do not copy that output into chat, tickets, or logs. If it leaks, rotate the secret.

### 1.9 Attach n8n

Safe because: `network connect` adds a second interface without restarting the container or touching its existing bridge network.

```sh
host$ docker network connect keyway-net n8n
host$ docker exec n8n wget -qO- http://ollama:11434/api/version
```

Already done on `pes-dev` (2026-09-06).

---

## 2. Making changes

### 2.1 Code

```console
dev$ git pull
dev$ .venv/Scripts/python -m pytest -q          # must be green before and after
# edit, add a test only where a plausible bug would fail it
dev$ git commit -am "..." && git push
```

### 2.2 Deploy a code change to the host

Push to `main`. The **Publish image** workflow (`.github/workflows/publish-image.yml`) runs the tests, builds `linux/amd64`, and pushes `latest` and `main-<sha>` to GHCR; it takes about 5 minutes. Watch it with `gh run watch --repo pesengineers/keyway`. A failing test blocks the publish.

Then on Unraid: Docker tab shows an update badge on `keyway`; click **Check for Updates** then **Apply** (or `docker pull ghcr.io/pesengineers/keyway:latest && docker restart keyway` from a shell; the GUI path is preferred because it re-creates the container from the template).

To roll back: edit the container's **Repository** field to a previous immutable tag, e.g. `ghcr.io/pesengineers/keyway:main-3a665ed`, and Apply. Tags are listed at https://github.com/pesengineers/keyway/pkgs/container/keyway. Return the field to `:latest` once fixed.

To cut a release: `git tag vX.Y.Z && git push --tags`; the same workflow publishes `X.Y.Z` and `X.Y` tags. Update `CHANGELOG.md` first.

### 2.3 Change the analysis model

```sh
host$ docker exec ollama ollama pull <model>
```

then set `ANALYSIS_MODEL` on the Keyway container. VRAM budget: Whisper float32 ~1.5 GB + model. The 5 GB P2000 comfortably fits a 3B model; for 7B/8B set `WHISPER_COMPUTE_TYPE=int8_float32` (Whisper drops to ~0.75 GB) and keep `OLLAMA_KEEP_ALIVE` short. Re-run `scripts/bench.sh` and compare the analysis quality before committing to it.

### 2.4 Change the prompt or schema

`_SYSTEM_PROMPT`, `_ANALYSIS_SCHEMA` (OpenAI) and `_OLLAMA_SCHEMA` (Ollama) live in `app/analysis.py`. Keep the two schemas' `required` lists identical. Never add `minLength`/`maxLength` to `_OLLAMA_SCHEMA`; llama.cpp's grammar compiler rejects them. Validate with `tests/test_analysis.py` and `tests/data/sensitivity_eval_set.json`.

### 2.5 n8n workflows

Use the MCP server (`.omp/mcp.json`, token in `N8N_PES_MCP_API_Key`) or the n8n UI at `https://n8n.pesengineers.dev`. The two `PES Video Metadata - *` workflows are frozen reference; create new workflows for Keyway. See `docs/n8n-integration.md`.

---

## 3. Operations

### 3.1 Health

```sh
host$ docker exec n8n wget -qO- http://keyway:8000/health   # liveness
host$ docker exec n8n wget -qO- http://keyway:8000/ready    # ffmpeg, mounts, analysis config
host$ docker logs --tail 50 keyway
host$ nvidia-smi                                             # both GPUs should be ~0 MiB when idle
```

`/ready` returns 503 with a list of problems; each string names the failing check.

### 3.2 Where things land

- Results: `/mnt/user/appdata/keyway/output/<job_id>/{transcript.txt,result.json}`. These may contain sensitive content; keep permissions tight.
- Failures also write `result.json` with `success: false` and an `error` string.
- Temp: `/mnt/cache/keyway/tmp/keyway/` must be empty when idle. If not, a job was killed mid-run; delete the leftover `job-*` directory.

### 3.3 Common failures

| Symptom | Cause | Fix |
|---|---|---|
| `/ready` 503 "analysis API key is not configured" | `ANALYSIS_BACKEND=openai` without a key | set the key or switch to `ollama` |
| `Analysis API returned HTTP 400` with Ollama | schema contains length bounds or an unsupported keyword | see 2.4; check `docker logs ollama` for `failed to parse grammar` |
| `Analysis request timed out` | model cold-start or CPU fallback in Ollama | raise `ANALYSIS_TIMEOUT_SECONDS`; check `docker exec ollama nvidia-smi` shows the GPU |
| `transcription.device` is `cpu` on the GPU host | container started without `--gpus`, or CUDA init failed and auto fell back | check `warnings` in `result.json`; `docker logs keyway` shows the CUDA error |
| `CUDA out of memory` | Ollama model still resident when Whisper loaded | lower `OLLAMA_KEEP_ALIVE`, or use `int8_float32` for Whisper, or a smaller LLM |
| `Source path is outside the configured local source roots` | `LOCAL_SOURCE_ROOTS` doesn't include the mount, or path uses a symlink outside it | fix the env JSON array; paths are resolved before checking |
| `Unsupported video extension` | extension not in the allowlist in `app/media.py` | add it there if legitimate |
| `ffmpeg failed: ...` | corrupt or audio-less file | error text carries ffmpeg's stderr tail; mark the item for manual review |
| Models re-downloading every run | `/models` not mounted or not writable by uid 10001 | check mounts and `chown` |

### 3.4 Upgrading Ollama or the model

Ollama: update via the Unraid Docker tab like any CA container; model files persist in appdata. After upgrading, re-run one bench job; the grammar behavior for structured output has changed between Ollama versions before.

### 3.5 Upgrading the base image / CUDA

`Dockerfile` pins `nvidia/cuda:12.8.1-cudnn-runtime-ubuntu24.04`. The host driver (580.x) supports CUDA 12.x. If moving to CUDA 13, confirm driver compatibility first and confirm CTranslate2 wheels exist for it.

### 3.6 GHCR visibility and permissions

The image is pulled anonymously, so the package must be public. Two settings control this, both org-level and both needed the first time (done 2026-09-06):

1. **Org policy**: https://github.com/organizations/pesengineers/settings/packages, "Package creation" must allow **Public**. If it does not, the package's visibility dialog shows Public greyed out with "Setting is disabled by organization administrators".
2. **Package visibility**: https://github.com/orgs/pesengineers/packages/container/keyway/settings, Danger Zone, Change visibility, Public. New packages are created private regardless of the repo's visibility.

Via API (needs a token with `read:packages` and `write:packages`; `gh auth refresh -h github.com -s read:packages,write:packages`):

```console
dev$ gh api /orgs/pesengineers/packages/container/keyway --jq .visibility
dev$ gh api -X PATCH /orgs/pesengineers/packages/container/keyway -f visibility=public
```

Note `write:packages` alone cannot read package metadata; the API returns 404 without `read:packages`, which looks like "package does not exist".

If the package must stay private, instead create a fine-grained PAT with read access to the package, run `docker login ghcr.io` once as root on the host (Unraid persists `/root/.docker/config.json` to flash), and pulls will authenticate.

The workflow authenticates with the automatic `GITHUB_TOKEN` (`packages: write`); no secret needs to be configured in the repo.

---

## 4. Credentials and where they live

| Secret | Location | Used by |
|---|---|---|
| Unraid root SSH | 1Password "pes-dev" (agent) + workstation `~/.ssh/id_ed25519` | humans, agents |
| n8n MCP token | 1Password "n8n PES Dev API Key"; env `N8N_PES_MCP_API_Key` | `.omp/mcp.json` |
| OpenAI key (if used) | env `ANALYSIS_API_KEY` on the Keyway container | `app/analysis.py` |
| Graph app secret ("Keyway Video Worker", Sites.Selected) | created by `scripts/New-KeywayGraphApp.ps1`; store in 1Password; env `GRAPH_CLIENT_SECRET` on the Keyway container; expires 365 days after creation | `app/sources.py` |
| SharePoint Graph creds for n8n | n8n credential store | existing workflows |

None of these belong in git. `.env` is ignored; if a secret is ever committed, rotate it, do not just delete the commit.

---

## 5. Decommission

```sh
host$ docker rm -f keyway; docker rmi ghcr.io/pesengineers/keyway:latest
host$ docker network disconnect keyway-net n8n
# Remove ollama via the Unraid Docker tab if no longer needed, then:
host$ docker network rm keyway-net
host$ rm -rf /mnt/user/appdata/keyway /mnt/cache/keyway     # only after copying /output if needed
```
