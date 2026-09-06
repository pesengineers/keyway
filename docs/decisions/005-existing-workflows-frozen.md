# 005: Existing n8n workflows are read-only reference

**Date:** 2026-09-06. **Status:** accepted.

## Context

`PES Video Metadata - Seed Queue` and `PES Video Metadata - Process Queue` on `n8n.pesengineers.dev` embody the prior design and a populated 100-row queue. They are inactive. Agents now have write-capable MCP access to this n8n instance.

## Decision

Those two workflows, and the `video_metadata_queue` data table's existing rows, are not to be edited, activated, executed, archived, or published by Keyway work. New behavior goes into new, distinctly named workflows. If an existing workflow is a useful starting point, duplicate it under a new name first.

## Consequences

- The reference implementation remains available for comparison and rollback.
- The MCP tools `publish_workflow`, `unpublish_workflow`, `archive_workflow`, `execute_workflow`, `test_workflow`, and all data-table mutations require explicit human approval when the target is one of the frozen assets.
- New Keyway workflows may read the queue table and may write a new table or new columns; changing semantics of existing columns is a decision to record here first.
