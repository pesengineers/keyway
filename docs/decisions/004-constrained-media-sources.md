# 004: Media sources are a validated local mount or constrained Graph item IDs

**Date:** 2026-09-05 (local), 2026-09-06 (SharePoint). **Status:** accepted.

## Context

The worker must obtain video bytes. Accepting arbitrary URLs would create an SSRF surface and a way to exfiltrate through the worker's network position.

## Decision

Sources implement the `MediaSource` protocol in `app/sources.py` and are limited to:

1. `LocalMediaSource`: a path that must resolve (symlinks followed) inside one of `LOCAL_SOURCE_ROOTS`, be a regular file, carry an allow-listed video extension, and be under `MAX_SOURCE_BYTES`.
2. `SharePointMediaSource`: `site_id`, `drive_id`, `item_id`, and a regex-validated `filename`. Keyway builds the Graph URL itself, authenticates with client credentials, streams to the job's temp dir with a byte cap, and deletes the file in `finally`.

`POST /v1/process/local` and `POST /v1/process/sharepoint` are the only entry points; request models forbid unknown fields and constrain `job_id` to a safe charset.

## Consequences

- No URL parameter exists anywhere in the API.
- The SharePoint path uses an Entra app registration ("Keyway Video Worker") with `Sites.Selected` and a `read` grant on the single Continuing Education site, created by `scripts/New-KeywayGraphApp.ps1` (runbook 1.7b). `Files.Read.All` is the documented fallback, not the default. The local-mount path would instead need the library synced or shared onto the host.
- Both sources feed the same `VideoProcessor`; adding a third source is one class, not a pipeline change.
