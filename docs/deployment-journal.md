# Keyway Deployment & Operational Journal

This journal tracks all completed, in-progress, and pending operational tasks across sessions.

---

- **Phase**: **Keyway service is live on `pes-dev`** (container `keyway`, GHCR image, `keyway-net`, P2000, Ollama backend, Graph source). End-to-end SharePoint → Keyway → Ollama verified on a real queued item. Remaining for Issue #7: rotate the Graph secret (echoed once in the Unraid Apply output), then build the new n8n workflow (design in `docs/n8n-integration.md`).
- **Target Host**: `pes-dev.pes.local` (`192.168.76.42`), Unraid kernel `6.12.85-Unraid`, Docker `29.3.1`, `nvidia` runtime registered.
- **SSH access**: working as `root` via `~/.ssh/id_ed25519` (`SHA256:TBb1nZ...`); local `~/.ssh/config` has a `pes-dev` host alias. The 1Password `pes-dev` key (`SHA256:4u7fD7/...`) is also authorized for interactive use.
- **GPU inventory (host)**:
  - index 0: Quadro P620, 2048 MiB, `GPU-588d1004-5969-03a5-2096-6fc9c4091e9a` (do not use)
  - index 1: Quadro P2000, 5120 MiB, `GPU-a16c6467-c3d8-cf56-6944-a53de59dcd6b` (target)
  - Driver 580.159.03. The P2000 is index 1, not 0; always select by UUID.
- **Existing containers**: `n8n` (bridge network), Cloudflared tunnel, UptimeKuma, docker-socket-proxy, opsi stack. Keyway must not be attached to the tunnel or published beyond a private network.
- **Storage**: `/mnt/user/appdata` (1.2T free), `/mnt/cache` (198G free). No `keyway` directories exist yet.

---

## 1. Unraid Deployment & Quadro P2000 Benchmark (Issue #3)

- [X] **Step 1.1**: Test SSH connectivity and authentication to `pes-dev.pes.local`.
- [X] **Step 1.2**: Run `nvidia-smi -L` to capture Quadro P2000 GPU UUID (distinguish from P620 and ignore GRID K2).
- [X] **Step 1.3**: Verify driver version (expected 580.159.03) and Docker NVIDIA runtime setup on host.
- [X] **Step 1.4**: Check and prepare directories:
  - `/mnt/user/appdata/keyway/models` (owner 10001:10001)
  - `/mnt/cache/keyway/tmp` (owner 10001:10001)
  - `/mnt/user/appdata/keyway/output` (owner 10001:10001)
  - `/mnt/user/appdata/keyway/src` (git clone used for on-host builds; **removed 2026-09-06** once GHCR publishing was in place)
- [X] **Step 1.5**: Built `keyway:local` on the host from the cloned repo (no registry needed). Image 5.45 GB.
- [X] **Step 1.6**: Benchmarked `small.en` on the P2000 in float32, int8_float32, int8, plus host CPU int8. Results in `docs/unraid-deployment.md`.
- [X] **Step 1.7**: Documented results, GPU UUIDs, and compute-type recommendation; closed Issue #3.

---

## 2. Ollama Analysis Backend (Issue #1)

- [X] **Step 2.1**: Implement `OllamaAnalysisBackend` conforming to `AnalysisBackend` protocol.
- [X] **Step 2.2**: Add structured output format support using Ollama's schema/format options.
- [X] **Step 2.3**: Unit tests with `httpx.MockTransport` covering success, malformed JSON, and timeout paths.
- [X] **Step 2.4**: Update config (`ANALYSIS_BACKEND=ollama`), docs, and compose examples.
- [ ] **Step 2.5**: Close Issue #1 on GitHub.

---

## 3. SharePoint Graph Source Adapter (Issue #5)

- [X] **Step 3.1**: Implement `SharePointMediaSource` conforming to `MediaSource` protocol.
- [X] **Step 3.2**: Enforce constrained inputs: `site_id`, `drive_id`, `item_id`, and `filename` (no arbitrary URLs).
- [X] **Step 3.3**: Token injection, streaming download directly to temp dir, size bounds, and cleanup on failure.
- [X] **Step 3.4**: Unit & integration test suites with mocked Microsoft Graph endpoints.
- [X] **Step 3.5**: Close Issue #5 on GitHub.

---

## 4. n8n Workflow Integration (Issue #6)
- [X] **Step 4.1**: Define JSON contract between n8n HTTP Request node and Keyway worker.
- [X] **Step 4.2**: Document sample n8n workflow definition (SharePoint polling/trigger -> Keyway -> SharePoint write-back).
- [X] **Step 4.3**: Verify private Docker network routing between n8n container and Keyway.
- [X] **Step 4.4**: Close Issue #6 on GitHub.

---

## 5. Sensitivity Prompt Evaluation & Hardening (Issues #2 & #4)

- [X] **Step 5.1**: Curate evaluation set of sample transcripts across safe, internal_only, and review_required categories.
- [X] **Step 5.2**: Measure classification accuracy and conservative uncertainty handling.
- [X] **Step 5.3**: Security review: timeout enforcement, disk cleanup guards, rate limiting, and private ingress docs.
- [X] **Step 5.4**: Close Issues #2 and #4 on GitHub.

---

## Session Activity Log

### 2026-09-07 (go-live)
- **Form URLs were broken.** User reported "Problem loading form". n8n logs: Respond to Webhook is not allowed after a Form Trigger (status report never registered), and custom `path` values are not registered for API-created workflows (both forms 404 by path). Rebuilt both with Form completion nodes, archived the old ids, published as `GNv9dZFLTvgjTz9v` (status) and `DOCflW4upDwPt2D4` (reset); verified `/form/<webhookId>` redirects to n8n login from inside the container. Docs corrected to webhook-id URLs.
- Added `Keyway - Queue Status` (`GNv9dZFLTvgjTz9v`): form trigger with `n8nUserAuth` → load all rows → Code node renders HTML (progress bar, counts, needs-a-human table, recent completions, stuck-processing warning) → Respond to Webhook. Published; anonymous access 404. Answers "which are complete?" without touching the table UI.
- Root cause of the recurring `AADSTS7000215`: the Unraid template file still held the original leaked secret; the GUI Edit at 22:24 pre-filled from it and reverted the rotation, after which the (correct) deletion of the old secret in Entra made the container's credential dead. Fingerprinting template vs `.bak` vs container (`uNY…dji` everywhere) proved it. User pasted the rotated value and blanked the template's `Default=` attribute so future edits cannot regress it. Token test 200.
- Manual Process Queue run 2507 on row 1: full success including SharePoint PATCH (see n8n doc, Go-live record). Published Process Queue (`33171b76`). Pipeline in production at 00:08 UTC.
- Lesson recorded in runbook 1.8: always verify a rotated secret in the template file, not only the running container.

### 2026-09-06 (autonomous continuation: helpers, operator docs, blocked on Graph secret)
- No MCP tool updates data-table rows, so built `Keyway - Reset Queue Rows` (`DOCflW4upDwPt2D4`): form trigger with `n8nUserAuth`, Code node splits ids, data-table update sets `pending` and clears result fields. Used it to reset rows 1 and 2 (execution 2502).
- Manual Process Queue run 2503 on row 1: Keyway 502, `OAuth token request failed with HTTP 401`, Entra `AADSTS7000215 Invalid client secret`. Template and container values match (40 chars); the same value worked at ~16:14. User action required. Row 1 reset again (attemptCount 2).
- Built `Keyway - Seed Queue` (`S2RN9PNHdZFZoZYe`; first draft `KCS0Swhq1EECnpTM` archived): frozen seeder's Graph listing + `executeOnce` load of queued ids + Code de-dup. Manual run: 281 files, 281 queued, 0 new. **Correction:** the queue has 281 rows / 82 GB, not 100 / 26 GB; the earlier survey call was capped at 100 rows. Docs corrected.
- Process Queue hardening via `update_workflow`: three operator sticky notes; Keyway node `onError=continueRegularOutput`; `Mark Row Error` message handles connection failures. Mirrored into the SDK source. All three workflows: `errorWorkflow` = `Send Error to Sentry`.
- Published Seed Queue and Reset Rows. Process Queue left inactive pending the secret fix. Anonymous access to the reset form verified as 404.
- Added `docs/operations.md` (operator guide) and linked it from README/AGENTS/n8n doc.

### 2026-09-06 (first workflow runs, analysis backend change)
- Workflow execution 2500 hit 502: the Graph secret had been deleted in Entra between rotation and Apply (AADSTS7000215). Diagnosed by comparing template vs container value (identical) and requesting a token directly. User re-rotated; verified.
- Execution 2501 processed row 2 end to end (37 min video, ~2.5 min) but `llama3.2:3b` returned `internal_only` reasoning that the content was "technical and specialized". Workflow correctly parked it as `flagged_internal`; nothing written to SharePoint.
- Rewrote the prompt with an explicit default-safe rule (`7c53b37`). A/B on the saved transcript: 3b now `safe` but invented date 2023-03-01; `llama3.1:8b` still `internal_only` ("company-specific") and invented 2024-02-22; both also failed structured-output parsing once each. Conclusion: not a model-size problem.
- Host briefly unreachable (ping loss, SSH timeout) for a few minutes during this work; came back on its own; uptime shows no reboot.
- Decision (ADR 006): use OpenRouter with `openai/gpt-4o-mini` through the existing `openai` backend. User added the OpenRouter key to n8n credentials (`OpenRouter Dailen Personal`) and to the Keyway template as masked `ANALYSIS_API_KEY` plus the three `ANALYSIS_*` values. Verified in-container. A/B: `safe`, clean reason, good title/synopsis, 3.9 s; but date 2023-10-01 invented (transcript contains no date).
- Added evidence gating (`124e067`): `presentation_date_evidence` required in both schemas; `_finalize()` drops the date unless the evidence string is found in the transcript, adding a warning. 42 tests. CI publishing.
- Note: the CI run for `124e067` was cancelled by the following docs push (workflow uses `cancel-in-progress`); the `7db6310` run carries the same code and succeeded. Container recreated on image `76481f8d`. A/B on `queue-2`: `safe`, `date: None`, warning `Model-inferred presentation_date discarded`. Gate confirmed on real output.
- Documentation updated across ADR 003/006, runbook (template, 2.3a A/B procedure, troubleshooting, secrets), architecture, security (data leaving host), n8n guide (first runs), STATUS, changelog.


### 2026-09-06 (secret rotated, container updated)
- User ran `New-KeywayGraphApp.ps1 -RotateSecret` (script fixed in `245e653` so `-SiteId` is not required for rotation) and updated the masked template variable. While editing, the GUI still showed leading spaces in the three path fields: each `<Config>` stores the value twice (`Default=` attribute and element text) and my earlier sed had fixed only the attribute. User cleaned them; template verified with zero leading-space values. Runbook updated.
- Verified the rotated secret end to end (OAuth + Graph download succeeded on the known-silent item). Old secret can now be deleted in Entra.
- Pulled the `314281a` image (`9c4019c5`) and recreated `keyway` from its template; healthy, `/ready` OK from n8n, and the silent item now returns **HTTP 422** with the new message. Removed smoke-test output directories.
### 2026-09-06 (n8n workflow created)
- Built `Keyway - Process Queue` (`mp5gviKuHu9iIfPo`) via the MCP `create_workflow_from_code` tool from `n8n/keyway-process-queue.workflow.ts`, following the server's required sequence (SDK reference, node type lookup, `validate_workflow`, create). Created inactive; frozen workflows untouched.
- 15 nodes: schedule (15 min) → Config → get one `pending` row → loop → mark `processing` → POST Keyway (`fullResponse`+`neverError`) → route on HTTP status (200/422/other) → for 200 route on sensitivity → PATCH SharePoint only for `safe` → mark `done`/`flagged_internal`/`flagged_review`/`unprocessable`/`error`. Reuses credential `Sharepoint video process` (`icIlll1oh3FEHtYl`). Verified connections and credential assignment via `get_workflow_details`.
- No schema change to the shared table; sensitivity is encoded in `status`. Documented in `docs/n8n-integration.md` §6 with deploy/update procedure and activation checklist.
- SDK quirks: `sticky()` is positional; `+` string concatenation is not folded; every loop branch must end in `nextBatch(loop)`.
### 2026-09-06 (service container live, Graph path proven)
- User created the `keyway` container in the Unraid GUI; first Apply failed because each host path had a leading space (Docker read them as volume names). Unraid had still saved `my-keyway.xml` to flash. Backed it up (`.bak.<ts>`), stripped the spaces with `sed`, added Support/Project/Icon links. Started the container from the template's values (secret read from the XML on-host, never transmitted). Runbook 1.8 now lists both pitfalls.
- Verified: `docker exec n8n wget http://keyway:8000/ready` returns ready; CUDA device count 1 inside the container; `GRAPH_*` configured.
- **Graph smoke 1** (`Non-Technical-20251022_155731UTC-Meeting Recording.mp4`, 6.5 MB): OAuth + download + ffmpeg succeeded, Whisper found no speech. ffprobe/volumedetect confirmed the file is 50 s of digital silence (max -91 dB). Keyway was correct to fail it.
- **Graph smoke 2** (`Create Revit Titleblock Family From Cad Border File.mp4`, 30 MB, 15 min): HTTP 200 in 71 s, cuda/float32, 48.8 s transcription, `safe` with grounded reason, temp clean. This is the first full production-path run.
- Code change from smoke 1: new `NoSpeechDetected` (subclass of `TranscriptionError`) mapped to **HTTP 422** so n8n can park silent recordings instead of retrying; error-to-status mapping factored into `_to_http()` and covered by `tests/test_error_mapping.py`. Status-code contract documented in `docs/n8n-integration.md` §4.
- **Action required:** the Graph client secret was printed in plaintext by Unraid's Apply output and pasted into chat. Rotate with `New-KeywayGraphApp.ps1 -RotateSecret`, update the masked variable, delete the old secret in Entra.
### 2026-09-06 (GHCR publishing, Graph app registration)
- Added `.github/workflows/publish-image.yml`: on push to `main` run tests, build `linux/amd64`, push `ghcr.io/pesengineers/keyway:latest` and `main-<sha>`; `v*` tags publish semver. First run (`3a665ed`) green in 4.5 min.
- Package was created private and the org policy blocked public packages. User enabled public package creation at the org level, then flipped the package to public. Token needed `read:packages` for the API to even see the package (`write:packages` alone returns 404). All recorded in runbook 3.6.
- Verified `pes-dev` pulls `ghcr.io/pesengineers/keyway:latest` anonymously and runs it. Removed `keyway:local` and `/mnt/user/appdata/keyway/src`; runbook, README, compose, and `scripts/bench.sh` now reference the GHCR image only.
- User ran `scripts/New-KeywayGraphApp.ps1`: app **Keyway Video Worker**, tenant `68e4d43b-0bf8-4363-8311-accdd3b62fa1`, client `90f1c65f-3d78-4569-b11d-d2fd6b73ef50`, `Sites.Selected` + `read` on the CE site. Secret in 1Password; will be entered as a masked Docker variable in the Unraid template, not via env file (an env-file approach was created and then removed the same session).
- Correction recorded as `AGENTS.md` rule 8: never install the `Microsoft.Graph` meta-module; the script needs only `Microsoft.Graph.Authentication` and `Microsoft.Graph.Applications`.
### 2026-09-06 (n8n access and repo handover)
- `docker network connect keyway-net n8n` (n8n now on `bridge` + `keyway-net`; verified it reaches `http://ollama:11434`). No restart, no other change to n8n.
- n8n's built-in MCP server (`https://n8n.pesengineers.dev/mcp-server/http`, n8n MCP Server 1.1.0) verified with the token in env `N8N_PES_MCP_API_Key` (1Password "n8n PES Dev API Key"). Registered as `n8n-pesdev` in committed `.omp/mcp.json` via `${N8N_PES_MCP_API_Key}`; no secret in the repo. 39 tools available including write operations.
- **Rule adopted (ADR 005):** the existing `PES Video Metadata - Seed Queue` / `Process Queue` workflows and the populated `video_metadata_queue` table are frozen reference. Only read-only MCP tools were used in this session.
- Read-only survey results recorded in `docs/n8n-integration.md` section 0: 100 pending rows, 26.2 GB, 96/100 over the 24 MB API limit, 6/100 leading-date filenames (CORRECTED later the same day: 281 rows, 82.2 GB, 272/281, 6/281; the survey call was capped at 100 rows), Process Queue never executed, SharePoint site/list IDs and field names, and the Keyway field mapping that replaces the CloudConvert/Whisper/gpt-4o-mini branch.
- Added `AGENTS.md` (entry point and hard rules), `docs/runbook.md` (rebuild, change, operate, repair, decommission), `docs/decisions/001-005`, `scripts/bench.sh` (the benchmark harness used for Issue #3, now Ollama-based), Graph vars in `.env.example`, README pointers.
### 2026-09-06 (Ollama companion container)
- Decision: analysis runs fully on-host in a second container (`ollama/ollama` from Community Apps) rather than a cloud API. Keyway remains a single container; the Ollama client already existed.
- Created private network `keyway-net` on the host. User installed Ollama through the CA template: name `ollama`, network `keyway-net`, `NVIDIA_VISIBLE_DEVICES` pinned to the P2000 UUID, `--runtime=nvidia`, `OLLAMA_KEEP_ALIVE=2m`, appdata `/mnt/user/appdata/ollama`. Template initially published host port 11434; removed via the CA template (API Interface Port row) and verified: LAN connection refused, still reachable on `keyway-net`.
- Verified Ollama 0.33.3 sees only the P2000 and answers at `http://ollama:11434` on `keyway-net`. Pulled `llama3.2:3b` (2.0 GB).
- **Bug found and fixed (`c1677ce`):** first end-to-end run failed with HTTP 400 from Ollama: `failed to parse grammar`. Cause: `maxLength: 2000` in the JSON schema expands to thousands of llama.cpp grammar rules. Keyway now sends Ollama a schema without string length bounds; Pydantic still validates them. Test added.
- Second run succeeded: 41.1 s transcription (cuda/float32) + 13.0 s analysis = 62.3 s total; peak VRAM 4.1 GB with both models resident. Output: title "Review of SCS Presentation on Revit and Dynamo", sensitivity `safe`, grounded reason. Model cache confirmed in `/models` (464 MB) after the image path-default fix. Scratch directory removed; `ollama` container left running.
### 2026-09-06 (Phase 1 - Unraid deployment and P2000 benchmark)
- Created keyway directories on `pes-dev` (checked for pre-existence first; none existed). Cloned repo to `/mnt/user/appdata/keyway/src` and built `keyway:local` on the host (4.5 min).
- **Hardware finding:** the P2000 is Pascal and CTranslate2 exposes no `float16` for it (only `float32`, `int8`, `int8_float32`). The previous `auto` logic hard-coded `float16` for CUDA and would have silently fallen back to CPU. Fixed in commit `094867f`: `auto` now queries `get_supported_compute_types("cuda")` and prefers `float16` > `int8_float16` > `float32`. Tests added for Pascal and Turing+ cases.
- **Deployment bug found:** with only `HF_HOME=/models` set, the app's own `MODEL_CACHE_DIR` defaulted to `~/.cache/huggingface` inside the temp mount, so 464 MB of weights landed in `/mnt/cache/keyway/tmp/.cache`. Fixed by baking `MODEL_CACHE_DIR`, `TEMP_DIR`, `OUTPUT_DIR` defaults into the image. The stray weights in `/mnt/cache/keyway/tmp/.cache` were removed; the model will re-download once into `/models` on first production run.
- Benchmark rig (private `keyway-bench` network, mock analysis container, sample video under `/mnt/cache/keyway/bench`) was torn down after the runs. Retained: image, source clone, empty runtime directories.
- Benchmark headline: GPU float32 40.1 s transcription for 56.5 min of media (RTF 0.0118, 1.5 GB peak VRAM) vs 93.8 s on the host CPU and 294 s on the dev laptop. See `docs/unraid-deployment.md` for the full table and recommendation.
### 2026-09-05

### Phase 1 Block Reason
### 2026-09-06 (Phase 4 - n8n Integration)
### 2026-09-06 (Phase 5 - Evaluation & Hardening)
- Created synthetic sensitivity evaluation benchmark dataset in `tests/data/sensitivity_eval_set.json` spanning routine technical CE instruction (`safe`), internal salary/performance reviews (`internal_only`), client-confidential contract terms (`internal_only`), credential leaks (`review_required`), and ambiguous NDA projects (`review_required`).
- Created test suite `tests/test_sensitivity_eval.py` verifying parsing integrity and boundary classification. All 29 unit and integration tests pass.
- Completed production security review and hardened documentation in `docs/security.md`, addressing input validation, process isolation, resource concurrency, credential safety, and deployment network boundaries.
- Authored comprehensive `docs/n8n-integration.md` detailing architectural boundary, internal Docker network topology, HTTP request schemas (`/v1/process/sharepoint` and `/v1/process/local`), response payload contracts, error handling, and a sample Mermaid flowchart for conditional routing.
- Added integration test in `tests/test_n8n_flow.py` asserting complete end-to-end payload contract, filename date precedence, status fields, and artifact persistence. All 28 tests pass.
### 2026-09-06 (Phase 3 - SharePoint Graph Source Adapter)
- Implemented `SharePointMediaSource` in `app/sources.py` using OAuth client credentials and constrained Microsoft Graph content downloads.
- Added `POST /v1/process/sharepoint` endpoint to `app/main.py` with strict Pydantic payload validation (`SharePointProcessRequest`).
- Implemented streaming download with explicit byte limit (`MAX_SOURCE_BYTES`), timeouts, and guaranteed removal in finally/exception blocks.
- Added unit and integration tests in `tests/test_sources.py` verifying OAuth token acquisition, content streaming, size limit enforcement, credential validation, and path traversal rejection. All 27 tests pass.
- Updated `README.md`, `docs/architecture.md`, and configuration.
### 2026-09-06 (Phase 2 - Ollama Backend)
- Implemented `OllamaAnalysisBackend` in `app/analysis.py` with structured JSON schema format (`_ANALYSIS_SCHEMA`), model configuration, and safe error handling.
- Updated readiness endpoint in `app/main.py` to allow `ollama` backend without requiring `ANALYSIS_API_KEY`.
- Added unit tests in `tests/test_analysis.py` and `tests/test_api.py` covering Ollama request construction, schema payload, success parsing, HTTP 500 handling, and readiness verification. All 23 tests pass.
- Updated `.env.example`, `compose.example.yml`, and `docs/architecture.md`.
- Attempted SSH to `pes-dev.pes.local` with existing keys (`~/.ssh/id_ed25519`, `~/.ssh/id_rsa_wdc-apps`) for `root` and `dailen`. Both rejected (`Permission denied (publickey,password,keyboard-interactive)`).
- Switched active execution to Phase 2 (Ollama Backend) while waiting for Unraid SSH credentials/key configuration.
- Verified `pes-dev.pes.local` (`192.168.76.42`) network reachability and HTTP/HTTPS responses.
- Created `docs/deployment-journal.md` and initialized phased task tracker.
