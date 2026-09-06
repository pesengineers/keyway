# Decision records

Short records of choices that shape the system. Add a new numbered file when a decision is made or reversed; do not rewrite history in an existing one, append a "Superseded by" line instead.

| # | Decision | Status |
|---|---|---|
| [001](001-single-worker-container.md) | Keyway is one worker container; orchestration stays in n8n | accepted |
| [002](002-local-transcription-on-p2000.md) | Transcribe locally with faster-whisper on the Quadro P2000, select compute type from device capabilities | accepted |
| [003](003-ollama-companion-for-analysis.md) | Analysis runs in a separate Ollama container on the same host | superseded as default by 006; retained as offline fallback |
| [004](004-constrained-media-sources.md) | Media sources are a validated local mount or constrained Graph item IDs; never arbitrary URLs | accepted |
| [005](005-existing-workflows-frozen.md) | Existing n8n workflows are read-only reference; Keyway gets new workflows | accepted |
| [006](006-analysis-via-openrouter.md) | Analysis via OpenRouter (gpt-4o-mini); evidence-gated dates; Ollama as fallback | accepted |
