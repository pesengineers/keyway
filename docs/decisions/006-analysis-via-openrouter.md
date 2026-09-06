# 006: Analysis runs through OpenRouter (gpt-4o-mini); Ollama becomes the offline fallback

**Date:** 2026-09-06. **Status:** accepted. **Supersedes:** 003 as the default; 003's Ollama setup remains installed and supported.

## Context

The first real queue item processed with `llama3.2:3b` was classified `internal_only` because the content was "technical and specialized" and "not suitable for a general audience", the inverse of the prompt's rule. A rewritten, explicit prompt did not fix it; `llama3.1:8b` made the same mistake with different words. Both models also fabricated a `presentation_date` that appears nowhere in the transcript. Structured-output parsing also failed intermittently on both local models. Fixing this locally meant a schema redesign (evidence list, verdict computed in code), a VRAM-constrained model search, and ongoing tuning.

The analysis step's input is only the transcript text (~5 KB per hour of video); the video never leaves the host. Cost through a commercial API is under $0.001 per video.

## Decision

- `ANALYSIS_BACKEND=openai` pointed at **OpenRouter** (`https://openrouter.ai/api/v1`), model **`openai/gpt-4o-mini`**, key from the existing OpenRouter account (1Password; n8n credential `OpenRouter Dailen Personal`; masked variable `ANALYSIS_API_KEY` in the Keyway Docker template).
- Ollama stays installed and pinned to the P2000 as the offline fallback; switching back is three template variables.
- Independently of backend, Keyway now **discards any model-supplied `presentation_date` unless the model also returns verbatim evidence that is found in the transcript** (`_finalize()` in `app/analysis.py`). This protects the 94 of 100 undated files from invented dates regardless of which model is used.

## Evidence

Same SCS transcript, new prompt: `llama3.2:3b` → `safe` but date `2023-03-01` (invented); `llama3.1:8b` → `internal_only` ("company-specific"), date `2024-02-22` (invented); `gpt-4o-mini` via OpenRouter → `safe`, clean two-sentence reason, good title and synopsis in 3.9 s, date `2023-10-01` (invented; now discarded by the evidence gate).

## Consequences

- Transcript text is sent to OpenRouter and onward to OpenAI. Acceptable for CE/training content; recorded in `docs/security.md`. If a class of recordings must never leave the host, route those through Ollama (per-job backend selection is not implemented; it would be a small change).
- No VRAM contention: Whisper is the only GPU user. `medium.en` becomes viable if transcription accuracy needs to improve.
- Analysis latency drops from 15 to 40 s to about 4 s.
- New operational dependency: OpenRouter availability and the key's spend limit. Keyway returns HTTP 502 on analysis failure, which the n8n workflow records as `error` for retry.
- `AnalysisResult` gained `presentation_date_evidence`; both JSON schemas require it.
