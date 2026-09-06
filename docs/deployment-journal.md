# Keyway Deployment & Operational Journal

This journal tracks all completed, in-progress, and pending operational tasks across sessions.

---

- **Phase**: Phase 1 blocked on SSH authentication; proceeding to Phase 2 (Ollama Backend, Issue #1).
- **Target Host**: `pes-dev.pes.local` (`192.168.76.42`)
- **Status**: Host is online and responds to HTTP/HTTPS. SSH port 22 is open, but neither `id_ed25519` nor `id_rsa_wdc-apps` keys are authorized for `root` or `dailen` (password/interactive authentication required or key needs to be loaded to `/root/.ssh/authorized_keys` on Unraid).

---

## 1. Unraid Deployment & Quadro P2000 Benchmark (Issue #3)

- [ ] **Step 1.1**: Test SSH connectivity and authentication to `pes-dev.pes.local`.
- [ ] **Step 1.2**: Run `nvidia-smi -L` to capture Quadro P2000 GPU UUID (distinguish from P620 and ignore GRID K2).
- [ ] **Step 1.3**: Verify driver version (expected 580.159.03) and Docker NVIDIA runtime setup on host.
- [ ] **Step 1.4**: Check and prepare directories:
  - `/mnt/user/appdata/keyway/models`
  - `/mnt/cache/keyway/tmp`
  - `/mnt/user/appdata/keyway/output`
- [ ] **Step 1.5**: Build / pull / transfer container image and compose configuration.
- [ ] **Step 1.6**: Run sample video benchmark on Quadro P2000 with `small.en` and compare with CPU INT8 baseline (294s transcription / 0.0866 RTF).
- [ ] **Step 1.7**: Document benchmark results (duration, transcription time, RTF, peak VRAM, GPU UUID) and close Issue #3 on GitHub.

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

- [ ] **Step 4.1**: Define JSON contract between n8n HTTP Request node and Keyway worker.
- [ ] **Step 4.2**: Document sample n8n workflow definition (SharePoint polling/trigger -> Keyway -> SharePoint write-back).
- [ ] **Step 4.3**: Verify private Docker network routing between n8n container and Keyway.
- [ ] **Step 4.4**: Close Issue #6 on GitHub.

---

## 5. Sensitivity Prompt Evaluation & Hardening (Issues #2 & #4)

- [ ] **Step 5.1**: Curate evaluation set of sample transcripts across safe, internal_only, and review_required categories.
- [ ] **Step 5.2**: Measure classification accuracy and conservative uncertainty handling.
- [ ] **Step 5.3**: Security review: timeout enforcement, disk cleanup guards, rate limiting, and private ingress docs.
- [ ] **Step 5.4**: Close Issues #2 and #4 on GitHub.

---

## Session Activity Log

### 2026-09-05

### Phase 1 Block Reason
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
