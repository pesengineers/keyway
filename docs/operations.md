# Operating Keyway (day-to-day guide)

For whoever keeps the video-metadata pipeline running. No coding required. If something here is unclear or wrong, fix the doc.

## What the system does, in one paragraph

Training videos live in SharePoint under **PES Documents / Continuing Education / Recordings & Video User Guides**. A queue table in n8n lists every video and its status. Every 15 minutes n8n takes the oldest *pending* video and hands it to **Keyway**, a service on the `pes-dev` server. Keyway downloads the video, transcribes it on the GPU, asks an AI model for a title, synopsis, sensitivity rating and (if spoken) the presentation date, and returns the result. If the video is rated **safe**, n8n writes Title, Synopsis and Presentation Date onto the SharePoint item. If it is rated **internal_only** or **review_required**, nothing is written and the row waits for a person to look at it.

## Checking progress: which videos are done?

Fastest: open **https://n8n.pesengineers.dev/form/keyway-status** (log in to n8n if asked) and press Submit. You get a page with the completion percentage, counts by status, every row that needs a person (with the reason), and the most recent completions with links to the videos. Refresh by submitting again. Bookmark it.

Other views: the `video_metadata_queue` data table in n8n (filter by `status`), the **Executions** tab of *Keyway - Process Queue* (one run per video with timings), or the SharePoint library sorted by Modified (completed items have Title and Synopsis filled).

## The four workflows (n8n at https://n8n.pesengineers.dev)

| Workflow | Runs | Purpose |
|---|---|---|
| **Keyway - Queue Status** | on demand (form) | read-only progress report at `https://n8n.pesengineers.dev/form/keyway-status` |
| **Keyway - Process Queue** | every 15 min | processes one pending row per run |
| **Keyway - Seed Queue** | daily 06:00 | finds new videos in the SharePoint folder and adds them as pending; safe to run any time |
| **Keyway - Reset Queue Rows** | on demand (form) | puts rows back to pending so they get processed again |

The older **PES Video Metadata - Seed Queue / Process Queue** workflows are the previous design, kept for reference. **Do not run or edit them**; the old seeder would create duplicate rows.

## Row statuses (data table `video_metadata_queue`)

Open it in n8n: left sidebar, **Data tables**, `video_metadata_queue`. Filter by `status`.

| status | Meaning | What to do |
|---|---|---|
| `pending` | waiting to be processed | nothing |
| `processing` | Keyway is working on it now | nothing; if it stays this way for over an hour, see Troubleshooting |
| `done` | processed; Title/Synopsis/Date written to SharePoint | spot-check occasionally |
| `flagged_internal` | AI judged the content internal-only (personnel, compensation, finances, client-confidential, commercial terms, strategy, credentials) | **read `sensitivityReason`**, open the video's SharePoint page (`webUrl`), decide. If it is fine to publish, reset the row (below) so it runs again, or fill the SharePoint fields by hand. |
| `flagged_review` | AI could not decide | same as above |
| `unprocessable` | the file has no speech, is silent, or cannot be decoded; will not be retried | check `errorMessage`; usually a dead-mic recording; leave it or delete the video |
| `error` | something failed (network, SharePoint, AI service); not retried automatically | read `errorMessage`; once the cause is fixed, reset the row |

`attemptCount` counts every attempt including resets, so a row that keeps failing is easy to spot.

## Weekly routine (10 minutes)

1. Open the data table, filter `status` = `flagged_internal` and `flagged_review`. Read each `sensitivityReason`. Decide: reset the row (so it is processed and written) or leave it flagged and, if needed, fill SharePoint fields manually.
2. Filter `status` = `error`. Read `errorMessage`. Common causes and fixes are in Troubleshooting. Reset the rows once fixed.
3. Glance at `done` rows added this week. Are titles sensible? If many are poor, tell whoever maintains Keyway (see "Changing the AI model" in `docs/runbook.md`).
4. Check the counts still move: if `pending` has not decreased in a day, see Troubleshooting.

## Resetting rows

Open **Keyway - Reset Queue Rows**, click the **Reset Rows Form** node, open its **Form URL** (you must be logged in to n8n), enter the row `id` values separated by commas, submit. Each row goes back to `pending` with its old result cleared. The next Process Queue cycle picks them up.

## Where the transcripts are

Every processed job leaves `transcript.txt` and `result.json` on the server at `/mnt/user/appdata/keyway/output/queue-<row id>/` (browse it from the Unraid web GUI under Shares > appdata, or via SMB if that share is exported). These may contain sensitive content; treat the folder like the videos themselves.

## Health checks

- n8n: **Executions** tab shows every run. A red execution of Process Queue almost always means the queue table or SharePoint credential is unavailable; the Keyway call itself never makes the run red (its failures become `error` rows).
- Server: Unraid web GUI > Docker tab. `keyway` and `ollama` should show as started with a green healthy indicator on `keyway`.
- From an n8n terminal or the Unraid terminal: `docker exec n8n wget -qO- http://keyway:8000/ready` should print `{"status":"ready"}`.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `error` rows say `OAuth token request failed with HTTP 401` | Keyway's SharePoint app secret is wrong or was deleted | someone with Entra admin runs `scripts/New-KeywayGraphApp.ps1 -RotateSecret` and updates `GRAPH_CLIENT_SECRET` on the `keyway` container (runbook 1.7b/1.8) |
| `error` rows say `Analysis API returned HTTP 401/402` | OpenRouter key invalid or out of credit | check the OpenRouter dashboard; update `ANALYSIS_API_KEY` on the `keyway` container |
| `error` rows say `Analysis request timed out` or `HTTP 5xx` | OpenRouter/provider hiccup | reset the rows; if persistent, switch to the local model (runbook 1.8, Ollama fallback) |
| Many rows `unprocessable` | check a few `errorMessage`s; silent recordings are genuine | if it says ffmpeg failed on files that play fine, escalate |
| A row stuck in `processing` for hours | Keyway restarted mid-job or the n8n execution was cancelled | confirm nothing is running (`docker logs keyway`), then reset the row |
| `pending` count not moving | Process Queue deactivated, or n8n cannot reach Keyway | check the workflow is Active; check `keyway` container is running; run the health check |
| Titles are poor or dates look invented | model quality | dates are only written when the model quotes them from the transcript, so an invented date means a bug; report it. Poor titles: consider a different model (runbook 2.3) |
| New videos never appear in the queue | Seed Queue inactive or its SharePoint credential expired | check the workflow is Active and its last execution is green; re-authorize credential `Sharepoint video process` if it asks |

## Changing how often things run

Process Queue: open the workflow, click **Every 15 Minutes**, change the interval, save. Five minutes is fine once things are stable; Keyway processes one video at a time regardless. Seed Queue: same, on the **Daily At 06:00** node.

## Who to call

Code, server, or Entra changes: see `AGENTS.md` and `docs/runbook.md` in the `pesengineers/keyway` repository; the state of everything is in `docs/STATUS.md`.
