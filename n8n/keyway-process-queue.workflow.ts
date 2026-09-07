// Keyway - Process Queue
//
// n8n Workflow SDK source. Deployed with the n8n MCP tool create_workflow_from_code
// (see docs/n8n-integration.md section 6). Kept in the repo so the workflow is
// reviewable and reproducible. The frozen "PES Video Metadata - *" workflows are
// not touched by this file.
//
// Flow: every 5 min take up to TWO pending rows (processed one at a time) from video_metadata_queue, mark it
// processing, POST it to Keyway (/v1/process/sharepoint), then branch on the
// HTTP status and on the sensitivity value:
//   200 + safe             -> PATCH SharePoint fields -> status done
//   200 + internal_only    -> status flagged_internal (no SharePoint write)
//   200 + review_required  -> status flagged_review   (no SharePoint write)
//   422 (silent/undecodable)-> status unprocessable  (terminal, not retried)
//   anything else          -> status error, attemptCount+1 (retried next cycle)
//
// Uses only columns that already exist on the table. Status values are the
// only new thing; see docs/n8n-integration.md for the contract.

import { workflow, node, trigger, sticky, ifElse, switchCase, splitInBatches, nextBatch, expr } from '@n8n/workflow-sdk';

const QUEUE_TABLE = { __rl: true, mode: 'id', value: 'QMOVCsZrJKJuT2Cz', cachedResultName: 'video_metadata_queue' };
const ROW_MATCH = { conditions: [{ keyName: 'id', condition: 'eq', keyValue: expr("{{ $('Process Queue Loop').item.json.id }}") }] };

const every15 = trigger({
  type: 'n8n-nodes-base.scheduleTrigger',
  version: 1.4,
  config: {
    name: 'Every 5 Minutes',
    parameters: { rule: { interval: [{ field: 'minutes', minutesInterval: 5 }] } },
  },
});

const config = node({
  type: 'n8n-nodes-base.set',
  version: 3.4,
  config: {
    name: 'Config',
    parameters: {
      mode: 'manual',
      includeOtherFields: false,
      assignments: {
        assignments: [
          { id: 'c1', name: 'siteId', type: 'string', value: 'pes1852.sharepoint.com,97c4bdef-10db-4a0a-b359-050ced66dd51,316269b2-8c0d-438a-9466-a3a1f9800a8a' },
          { id: 'c2', name: 'listId', type: 'string', value: 'd5aef84f-d0e2-4a89-873c-7c9db6b6e059' },
          { id: 'c3', name: 'driveId', type: 'string', value: 'b!773El9sQCkqzWQUM7WbdUbJpYjENjIpDlGajofmACopP-K7V4tCJSoc8fJ22tuBZ' },
          { id: 'c4', name: 'keywayUrl', type: 'string', value: 'http://keyway:8000' },
        ],
      },
    },
  },
});

const getPending = node({
  type: 'n8n-nodes-base.dataTable',
  version: 1.1,
  config: {
    name: 'Get Pending Rows',
    parameters: {
      resource: 'row',
      operation: 'get',
      dataTableId: QUEUE_TABLE,
      matchType: 'allConditions',
      filters: { conditions: [{ keyName: 'status', condition: 'eq', keyValue: 'pending' }] },
      returnAll: false,
      limit: 2,
      orderBy: true,
      orderByColumn: 'id',
      orderByDirection: 'ASC',
    },
  },
});

const loop = splitInBatches({
  version: 3,
  config: { name: 'Process Queue Loop', parameters: { batchSize: 1 } },
});

// Guard against overlapping runs: with a 5-minute schedule and jobs that can
// take longer, two executions may both read the same pending rows. Re-read the
// row right before claiming it and skip if another run already took it.
const rereadRow = node({
  type: 'n8n-nodes-base.dataTable',
  version: 1.1,
  config: {
    name: 'Re-read Row',
    alwaysOutputData: true,
    parameters: {
      resource: 'row',
      operation: 'get',
      dataTableId: QUEUE_TABLE,
      matchType: 'allConditions',
      filters: { conditions: [{ keyName: 'id', condition: 'eq', keyValue: expr("{{ $('Process Queue Loop').item.json.id }}") }] },
      returnAll: false,
      limit: 1,
    },
  },
});

const stillPending = ifElse({
  version: 2.2,
  config: {
    name: 'Still Pending?',
    parameters: {
      conditions: {
        options: { caseSensitive: true, leftValue: '', typeValidation: 'loose' },
        conditions: [{ leftValue: expr('{{ $json.status }}'), operator: { type: 'string', operation: 'equals' }, rightValue: 'pending' }],
        combinator: 'and',
      },
    },
  },
});

const markProcessing = node({
  type: 'n8n-nodes-base.dataTable',
  version: 1.1,
  config: {
    name: 'Mark Row Processing',
    parameters: {
      resource: 'row',
      operation: 'update',
      dataTableId: QUEUE_TABLE,
      matchType: 'allConditions',
      filters: ROW_MATCH,
      columns: {
        mappingMode: 'defineBelow',
        value: {
          status: 'processing',
          lastAttemptAt: expr('{{ $now.toISO() }}'),
          attemptCount: expr("{{ ($('Process Queue Loop').item.json.attemptCount || 0) + 1 }}"),
        },
        schema: [
          { id: 'status', displayName: 'status', type: 'string', canBeUsedToMatch: false },
          { id: 'lastAttemptAt', displayName: 'lastAttemptAt', type: 'date', canBeUsedToMatch: false },
          { id: 'attemptCount', displayName: 'attemptCount', type: 'number', canBeUsedToMatch: false },
        ],
      },
    },
  },
});

const callKeyway = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {
    name: 'Keyway Process SharePoint Item',
    onError: 'continueRegularOutput',
    parameters: {
      method: 'POST',
      url: expr("{{ $('Config').item.json.keywayUrl }}/v1/process/sharepoint"),
      authentication: 'none',
      sendBody: true,
      specifyBody: 'json',
      jsonBody: expr(
        "{{ JSON.stringify({ job_id: 'queue-' + $('Process Queue Loop').item.json.id, site_id: $('Config').item.json.siteId, drive_id: $('Config').item.json.driveId, item_id: $('Process Queue Loop').item.json.driveItemId, filename: $('Process Queue Loop').item.json.fileName }) }}",
      ),
      options: {
        timeout: 1800000,
        response: { response: { fullResponse: true, neverError: true, responseFormat: 'json' } },
      },
    },
  },
});

const routeStatus = switchCase({
  version: 3.2,
  config: {
    name: 'Route By HTTP Status',
    parameters: {
      rules: {
        values: [
          {
            outputKey: 'ok',
            conditions: {
              options: { caseSensitive: true, leftValue: '', typeValidation: 'loose' },
              conditions: [{ leftValue: expr('{{ $json.statusCode }}'), operator: { type: 'number', operation: 'equals' }, rightValue: 200 }],
              combinator: 'and',
            },
          },
          {
            outputKey: 'unprocessable',
            conditions: {
              options: { caseSensitive: true, leftValue: '', typeValidation: 'loose' },
              conditions: [{ leftValue: expr('{{ $json.statusCode }}'), operator: { type: 'number', operation: 'equals' }, rightValue: 422 }],
              combinator: 'and',
            },
          },
        ],
      },
      options: { fallbackOutput: 'extra', renameFallbackOutput: 'error' },
    },
  },
});

const routeSensitivity = switchCase({
  version: 3.2,
  config: {
    name: 'Route By Sensitivity',
    parameters: {
      rules: {
        values: [
          {
            outputKey: 'safe',
            conditions: {
              options: { caseSensitive: true, leftValue: '', typeValidation: 'strict' },
              conditions: [{ leftValue: expr('{{ $json.body.sensitivity }}'), operator: { type: 'string', operation: 'equals' }, rightValue: 'safe' }],
              combinator: 'and',
            },
          },
          {
            outputKey: 'internal_only',
            conditions: {
              options: { caseSensitive: true, leftValue: '', typeValidation: 'strict' },
              conditions: [{ leftValue: expr('{{ $json.body.sensitivity }}'), operator: { type: 'string', operation: 'equals' }, rightValue: 'internal_only' }],
              combinator: 'and',
            },
          },
        ],
      },
      options: { fallbackOutput: 'extra', renameFallbackOutput: 'review_required' },
    },
  },
});

const writeSharePoint = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {
    name: 'Write Metadata To SharePoint',
    parameters: {
      method: 'PATCH',
      url: expr("{{ $('Config').item.json.siteId ? 'https://graph.microsoft.com/v1.0/sites/' + $('Config').item.json.siteId + '/lists/' + $('Config').item.json.listId + '/items/' + $('Process Queue Loop').item.json.sourceItemId + '/fields' : '' }}"),
      authentication: 'genericCredentialType',
      genericAuthType: 'oAuth2Api',
      sendBody: true,
      specifyBody: 'json',
      jsonBody: expr(
        "{{ (() => { const m = $('Keyway Process SharePoint Item').item.json.body; const b = { Title: m.title, Synopsis: m.synopsis.length > 255 ? m.synopsis.slice(0, 252) + '...' : m.synopsis }; if (m.presentation_date) { b['Presentation_x0020_Date'] = m.presentation_date + 'T00:00:00Z'; } return JSON.stringify(b); })() }}",
      ),
      options: { timeout: 60000 },
    },
    credentials: { oAuth2Api: { id: 'icIlll1oh3FEHtYl', name: 'Sharepoint video process' } },
  },
});

const resultSchema = [
  { id: 'status', displayName: 'status', type: 'string', canBeUsedToMatch: false },
  { id: 'title', displayName: 'title', type: 'string', canBeUsedToMatch: false },
  { id: 'presentationDate', displayName: 'presentationDate', type: 'string', canBeUsedToMatch: false },
  { id: 'synopsis', displayName: 'synopsis', type: 'string', canBeUsedToMatch: false },
  { id: 'isSensitive', displayName: 'isSensitive', type: 'boolean', canBeUsedToMatch: false },
  { id: 'sensitivityReason', displayName: 'sensitivityReason', type: 'string', canBeUsedToMatch: false },
  { id: 'errorMessage', displayName: 'errorMessage', type: 'string', canBeUsedToMatch: false },
];

const markDone = node({
  type: 'n8n-nodes-base.dataTable',
  version: 1.1,
  config: {
    name: 'Mark Row Done',
    parameters: {
      resource: 'row', operation: 'update', dataTableId: QUEUE_TABLE, matchType: 'allConditions', filters: ROW_MATCH,
      columns: {
        mappingMode: 'defineBelow',
        value: {
          status: 'done',
          title: expr("{{ $('Keyway Process SharePoint Item').item.json.body.title }}"),
          presentationDate: expr("{{ $('Keyway Process SharePoint Item').item.json.body.presentation_date || '' }}"),
          synopsis: expr("{{ $('Keyway Process SharePoint Item').item.json.body.synopsis }}"),
          isSensitive: false,
          sensitivityReason: expr("{{ $('Keyway Process SharePoint Item').item.json.body.sensitivity_reason }}"),
          errorMessage: '',
        },
        schema: resultSchema,
      },
    },
  },
});

const markInternal = node({
  type: 'n8n-nodes-base.dataTable',
  version: 1.1,
  config: {
    name: 'Mark Row Flagged Internal',
    parameters: {
      resource: 'row', operation: 'update', dataTableId: QUEUE_TABLE, matchType: 'allConditions', filters: ROW_MATCH,
      columns: {
        mappingMode: 'defineBelow',
        value: {
          status: 'flagged_internal',
          title: expr("{{ $json.body.title }}"),
          presentationDate: expr("{{ $json.body.presentation_date || '' }}"),
          synopsis: expr("{{ $json.body.synopsis }}"),
          isSensitive: true,
          sensitivityReason: expr("{{ $json.body.sensitivity_reason }}"),
          errorMessage: '',
        },
        schema: resultSchema,
      },
    },
  },
});

const markReview = node({
  type: 'n8n-nodes-base.dataTable',
  version: 1.1,
  config: {
    name: 'Mark Row Flagged Review',
    parameters: {
      resource: 'row', operation: 'update', dataTableId: QUEUE_TABLE, matchType: 'allConditions', filters: ROW_MATCH,
      columns: {
        mappingMode: 'defineBelow',
        value: {
          status: 'flagged_review',
          title: expr("{{ $json.body.title }}"),
          presentationDate: expr("{{ $json.body.presentation_date || '' }}"),
          synopsis: expr("{{ $json.body.synopsis }}"),
          isSensitive: true,
          sensitivityReason: expr("{{ $json.body.sensitivity_reason }}"),
          errorMessage: '',
        },
        schema: resultSchema,
      },
    },
  },
});

const markUnprocessable = node({
  type: 'n8n-nodes-base.dataTable',
  version: 1.1,
  config: {
    name: 'Mark Row Unprocessable',
    parameters: {
      resource: 'row', operation: 'update', dataTableId: QUEUE_TABLE, matchType: 'allConditions', filters: ROW_MATCH,
      columns: {
        mappingMode: 'defineBelow',
        value: {
          status: 'unprocessable',
          errorMessage: expr("{{ $json.body.detail || 'Keyway returned 422' }}"),
        },
        schema: [
          { id: 'status', displayName: 'status', type: 'string', canBeUsedToMatch: false },
          { id: 'errorMessage', displayName: 'errorMessage', type: 'string', canBeUsedToMatch: false },
        ],
      },
    },
  },
});

const markError = node({
  type: 'n8n-nodes-base.dataTable',
  version: 1.1,
  config: {
    name: 'Mark Row Error',
    parameters: {
      resource: 'row', operation: 'update', dataTableId: QUEUE_TABLE, matchType: 'allConditions', filters: ROW_MATCH,
      columns: {
        mappingMode: 'defineBelow',
        value: {
          status: 'error',
          errorMessage: expr("{{ $json.statusCode ? ('HTTP ' + $json.statusCode + ': ' + (($json.body && $json.body.detail) ? $json.body.detail : JSON.stringify($json.body || $json))) : ('Request to Keyway failed: ' + ($json.error && $json.error.message ? $json.error.message : JSON.stringify($json))) }}"),
        },
        schema: [
          { id: 'status', displayName: 'status', type: 'string', canBeUsedToMatch: false },
          { id: 'errorMessage', displayName: 'errorMessage', type: 'string', canBeUsedToMatch: false },
        ],
      },
    },
  },
});

const notes = sticky(
  '## Keyway - Process Queue\n\nSource: pesengineers/keyway, n8n/keyway-process-queue.workflow.ts\n\nTakes ONE pending row per run (Keyway processes one job at a time), marks it processing, POSTs to Keyway on keyway-net, then routes on HTTP status and sensitivity.\n\nStatus values written: processing, done, flagged_internal, flagged_review, unprocessable (422, not retried), error (retried next run; attemptCount increments).\n\nOnly status=done writes Title/Synopsis/Presentation Date back to SharePoint. Flagged rows wait for a human.\n\nThe older "PES Video Metadata - *" workflows are frozen reference; do not edit them.',
  undefined,
  { name: 'About This Workflow', color: 4 },
);

const notePickup = sticky(
  '### 1. Pick up one row\nEvery 5 min. Takes the two OLDEST rows with status=pending and processes them one after the other (Keyway runs one job at a time).\n\nThe loop marks it `processing` first so a long job is never picked up twice.\n\nTo reprocess a row: use the **Keyway - Reset Queue Rows** form. Never edit statuses by hand in the table while this is active.',
  [config, getPending, loop],
  { name: 'Note: Pickup', color: 7 },
);

const noteCall = sticky(
  '### 2. Call Keyway\nPOST http://keyway:8000/v1/process/sharepoint on the private keyway-net network. Keyway downloads the video from SharePoint itself, transcribes on the GPU, analyzes, and returns JSON.\n\nTypical time: ~1 min per hour of video + download. Timeout here is 30 min.\n\n`Full response` + `Never error` are ON so the HTTP status reaches the router instead of failing the node.',
  [markProcessing, callKeyway],
  { name: 'Note: Keyway Call', color: 7 },
);

const noteRouting = sticky(
  '### 3. Route on result\n**HTTP status** (Keyway contract, docs/n8n-integration.md §4):\n- 200 → look at sensitivity\n- 422 → `unprocessable` (silent/undecodable; never retried)\n- other → `error` (fix cause, then reset the row)\n\n**Sensitivity** (only for 200):\n- safe → write Title/Synopsis/Date to SharePoint → `done`\n- internal_only → `flagged_internal` (nothing written)\n- review_required → `flagged_review` (nothing written)\n\nFlagged rows wait for a human. Transcript + result JSON for every job: /mnt/user/appdata/keyway/output/queue-<row id>/ on pes-dev.',
  [routeStatus, routeSensitivity, markError],
  { name: 'Note: Routing', color: 7 },
);

export default workflow('keyway-process-queue', 'Keyway - Process Queue')
  .add(notes)
  .add(notePickup)
  .add(noteCall)
  .add(noteRouting)
  .add(every15)
  .to(config)
  .to(getPending)
  .to(
    loop.onEachBatch(
      rereadRow.to(
        stillPending
          .onTrue(
            markProcessing.to(
              callKeyway.to(
                routeStatus
                  .onCase(0,
                    routeSensitivity
                      .onCase(0, writeSharePoint.to(markDone.to(nextBatch(loop))))
                      .onCase(1, markInternal.to(nextBatch(loop)))
                      .onCase(2, markReview.to(nextBatch(loop))),
                  )
                  .onCase(1, markUnprocessable.to(nextBatch(loop)))
                  .onCase(2, markError.to(nextBatch(loop))),
              ),
            ),
          )
          .onFalse(nextBatch(loop)),
      ),
    ),
  );
