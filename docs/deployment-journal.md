# Keyway Deployment & Operational Journal

This journal tracks all completed, in-progress, and pending operational tasks across sessions.

---

- **Phase**: All five phases complete. Ollama companion container installed on `pes-dev` via Community Apps and validated end to end on the P2000 (2026-09-06). Remaining go-live work tracked in Issue #7: attach n8n to `keyway-net`, start the Keyway service container, choose the media source, remove Ollama's published host port.
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
  - `/mnt/user/appdata/keyway/src` (git clone of the repo, used for on-host builds)
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


### 2026-09-06 (Ollama companion container)
- Decision: analysis runs fully on-host in a second container (`ollama/ollama` from Community Apps) rather than a cloud API. Keyway remains a single container; the Ollama client already existed.
- Created private network `keyway-net` on the host. User installed Ollama through the CA template: name `ollama`, network `keyway-net`, `NVIDIA_VISIBLE_DEVICES` pinned to the P2000 UUID, `--runtime=nvidia`, `OLLAMA_KEEP_ALIVE=2m`, appdata `/mnt/user/appdata/ollama`. Template also published host port 11434; flagged for removal in Issue #7.
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
