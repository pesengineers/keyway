# 001: Keyway is one worker container; orchestration stays in n8n

**Date:** 2026-09-05. **Status:** accepted.

## Context

The pre-existing n8n workflow tried to do media work inside n8n: download multi-GB videos, ship them to CloudConvert for compression to fit the 25 MB Whisper API limit, poll, download audio, call two OpenAI APIs. n8n is poor at long-running binary work and the design leaked video content to two third parties.

## Decision

Keyway is a single, small HTTP worker that owns media normalization, transcription, and analysis. It has no scheduler, queue, database, UI, SharePoint write-back, or shell surface. n8n keeps the queue (data table), scheduling, retry, and SharePoint writes.

## Consequences

- One image, one container to reason about; failures are attributable.
- n8n sends ~200 bytes of JSON and receives ~2 KB back; it never touches video bytes.
- Concurrency is a process-local semaphore (`MAX_CONCURRENT_JOBS`, default 1). Run exactly one Uvicorn worker.
- Anything resembling a second queue or scheduler inside Keyway is out of scope by design.
