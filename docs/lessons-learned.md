# Lessons learned

Things that cost real time during the 2026-09-05/07 build and deployment. Each is stated as the rule we now follow. The journal has the full stories; this is the digest.

## Secrets and Unraid templates

1. **The Unraid GUI Edit form pre-fills from the template XML on flash, not from the running container.** A secret rotated anywhere else gets silently reverted on the next unrelated Apply. After rotating: verify the value in `/boot/config/plugins/dockerMan/templates-user/<name>.xml`, and blank the `Default=` attribute for secret variables so the form has nothing stale to offer.
2. **Unraid prints the full `docker run` line, secrets included, on every Apply.** Treat that output as sensitive; never paste it into chat or tickets. If it leaks, rotate.
3. **Delete the old secret only after the new one is verified working end to end**, from the container itself (runbook 1.7b token test). Deleting first turned a benign revert into an outage.
4. **Template `<Config>` values are stored twice** (`Default=` attribute and element text). Hand-edits with `sed` must fix both.
5. **A leading space in a host path** makes Docker treat it as a named volume. Symptom: `includes invalid characters for a local volume name`.

## Windows workstation

6. **The 1Password SSH agent is not reachable from non-interactive processes** (agents, tools, some terminals). `ssh-add -L` may list keys while `ssh` itself reports `ssh_get_authentication_socket: No such file`. Keep a plain on-disk key authorized for automation, and read `sshd` logs on the server to see which key was actually offered.
7. **`op read` exports ed25519 keys as PKCS#8 (`BEGIN PRIVATE KEY`)**, which Windows OpenSSH rejects. Not a viable way to hand a key to a tool.
8. **PowerShell here-strings emit CRLF and long lines wrap at the console width.** Both corrupted `authorized_keys` on the server. One line per remote command, or use the Unraid web terminal.
9. **Never install the `Microsoft.Graph` meta-module.** Two sub-modules do the job; the meta-module pulls in dozens of modules and gigabytes.
10. **`gh` needs `read:packages` to even see a GHCR package**; with only `write:packages` the API returns 404, indistinguishable from "does not exist".

## GHCR and Docker

11. **New GHCR packages are private regardless of repo visibility**, and the org may forbid public packages entirely. Two settings: org policy (Package creation: Public) then package visibility.
12. **CI `cancel-in-progress` will cancel an image build when a docs-only push lands right after it.** Check which commit's run actually published before assuming the container update is available.
13. **Bake path defaults into the image** (`MODEL_CACHE_DIR`, `TEMP_DIR`, `OUTPUT_DIR`). Relying on `HF_HOME` alone left model weights in the temp mount.

## GPU and transcription

14. **The Quadro P2000 (Pascal) has no float16 in CTranslate2.** `auto` must query `get_supported_compute_types`; hard-coding float16 silently falls back to CPU. Found only by running on the hardware.
15. **The P2000 is GPU index 1 on this host, not 0.** Always pin by UUID.
16. **VAD can remove most of a recording.** 49 of 56 minutes on one sample. Transcription accuracy on this audio is still unmeasured (STATUS item 6).

## LLM analysis

17. **Small local models equate "technical / internal" with "sensitive"** even when told explicitly not to; a bigger local model (8B) did the same in different words. Prompt wording did not fix it. A hosted frontier-class model did.
18. **Every model tested, including gpt-4o-mini, invented a presentation date when none was spoken.** Structured output does not stop hallucination; it formats it. The fix that worked: require verbatim evidence and verify it against the transcript in code.
19. **Ollama compiles JSON Schema into a llama.cpp grammar and rejects string length bounds** (HTTP 400 `failed to parse grammar`). Keep a bound-free schema for Ollama and validate lengths in code.
20. **Structured-output parsing from local models fails intermittently**; treat a parse failure as a retryable 502, not a bug in the schema.

## n8n

21. **The MCP `get_data_table_rows` default page is 100 rows.** A "100 pending rows" survey was actually 281. Page, or check `count`.
22. **There is no MCP tool to update data-table rows.** A small form-triggered workflow (`Keyway - Reset Queue Rows`) fills the gap and doubles as an operator tool; drive it with `execute_workflow` + `formData`.
23. **The n8n Workflow SDK is a restricted subset of TypeScript.** `sticky()` is positional (`sticky(text, nodes?, config?)`), string `+` concatenation is not folded, arrow functions are only allowed inside Code-node strings, and every `splitInBatches` branch must end in `nextBatch(loop)`. Run `validate_workflow` until it returns no warnings; a warning at create time becomes a broken node.
23b. **`.join()` (and every other array/string method) is also forbidden in builder code**, including for assembling a Code node's `jsCode`. Put the whole script in one template literal.
23c. **A Form Trigger cannot be followed by Respond to Webhook** (n8n throws at request time and never registers the route, while the API still reports success). Render pages with a Form node in `completion` mode, `respondWith: showText`.
23d. **Form Trigger v2.6 reads its custom URL from `options.path`; the top-level `path` is ignored** and the form registers only under the webhook ID ("Problem loading form" at the friendly URL). Verify registration from inside the container (`wget http://localhost:5678/form/<id>` should redirect to login, not 404); the MCP `execute_workflow` test bypasses webhooks and proves nothing about the URL.
23e. **RETRACTED (2026-09-07): API publish does re-arm schedules.** An earlier claim that unpublish/publish left no cron registered was wrong; it came from two bad instruments: Keyway's application logs were not being emitted under Uvicorn (see 29), and a copied SQLite database lags the live WAL by many minutes. The `search_workflow_executions` API is the reliable oracle; `docker logs n8n` only ever prints "Deregistered all crons" and is useless for confirming registration. Wait one interval and check executions.
23f. **Scheduled runs overlap when a run takes longer than the interval.** n8n has no per-workflow "skip if already running" setting exposed via the API, and Keyway serializes jobs, so a 5-minute schedule with 2 to 15 minute runs routinely has 3 to 4 executions queued on the HTTP call. Harmless, but two runs can read the same `pending` rows before either claims them. Process Queue re-reads the row immediately before claiming and skips it if it is no longer `pending`.
24. **`rowNotExists` returned 0 items when all inputs were already present, which is correct but indistinguishable from a broken filter.** An explicit load-once + Code filter that logs its counts is easier to trust.
25. **A frozen reference workflow can have credentials attached to nodes without ever having run.** Do not infer that a credential exists or works from a node referencing it; list credentials directly.
26. **Set `onError: continueRegularOutput` on the HTTP call to the worker** even with `neverError` on; `neverError` covers HTTP status codes, not connection failures, and without it a down worker leaves rows stuck in `processing`.

## Process

27. **Verify on the real path before declaring done.** Unit tests were green throughout; the Pascal float16 bug, the model-cache path bug, the Ollama grammar bug, the model misclassification, and the date hallucination were all found only by running real files on the real host.
29. **Configure application logging explicitly when running under Uvicorn.** Uvicorn sets up only its own loggers; `logging.getLogger("app")` lines were silently dropped for the whole first day of production, which led to a false "nothing is running" diagnosis. Fixed in `602ec87`.
30. **Executions in `running` state show no node data via the API until they finish**; four empty `running` executions is normal queueing, not a hang. Look at Keyway's output directory or GPU usage to see what is actually in flight.
28. **Keep STATUS.md current in the same commit as the change.** Twice the doc drifted within a session and had to be repaired; the "last updated" line and the numbered unresolved list are the parts that go stale first.
