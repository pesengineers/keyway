// Keyway - Seed Queue
//
// Discovers video files in the SharePoint "Recordings & Video User Guides" folder
// via Microsoft Graph (paginated) and inserts a pending row into
// video_metadata_queue for every video that is NOT already in the table.
// Safe to run repeatedly: existing rows are never touched or duplicated.
//
// Runs daily on a schedule and can also be run by hand. Uses n8n's existing
// "Sharepoint video process" OAuth credential for the Graph listing; Keyway's
// own Graph app is only used later, at processing time, to download files.
//
// Derived from the frozen "PES Video Metadata - Seed Queue" (same Graph URL and
// field mapping) with de-duplication added. Does not modify that workflow.

import { workflow, node, trigger, sticky, expr } from '@n8n/workflow-sdk';

const QUEUE_TABLE = { __rl: true, mode: 'id', value: 'QMOVCsZrJKJuT2Cz', cachedResultName: 'video_metadata_queue' };

const daily = trigger({
  type: 'n8n-nodes-base.scheduleTrigger',
  version: 1.4,
  config: {
    name: 'Daily At 06:00',
    parameters: { rule: { interval: [{ field: 'days', daysInterval: 1, triggerAtHour: 6 }] } },
  },
});

const listFolder = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {
    name: 'List Recordings Folder (Graph)',
    parameters: {
      method: 'GET',
      url: 'https://graph.microsoft.com/v1.0/drives/b!773El9sQCkqzWQUM7WbdUbJpYjENjIpDlGajofmACopP-K7V4tCJSoc8fJ22tuBZ/items/01R37EIECTVBT5FJKU2VFYJSO4KV4NRZHX/children?$expand=listItem&$top=200',
      authentication: 'genericCredentialType',
      genericAuthType: 'oAuth2Api',
      options: {
        timeout: 60000,
        pagination: {
          pagination: {
            paginationMode: 'responseContainsNextURL',
            nextURL: expr("{{ $response.body['@odata.nextLink'] }}"),
            paginationCompleteWhen: 'other',
            completeExpression: expr("{{ !$response.body['@odata.nextLink'] }}"),
            limitPagesFetched: true,
            maxRequests: 50,
          },
        },
      },
    },
    credentials: { oAuth2Api: { id: 'icIlll1oh3FEHtYl', name: 'Sharepoint video process' } },
  },
});

const splitChildren = node({
  type: 'n8n-nodes-base.splitOut',
  version: 1,
  config: { name: 'One Item Per File', parameters: { fieldToSplitOut: 'value', include: 'noOtherFields' } },
});

const videosOnly = node({
  type: 'n8n-nodes-base.filter',
  version: 2.3,
  config: {
    name: 'Videos Only',
    parameters: {
      conditions: {
        options: { caseSensitive: false, leftValue: '', typeValidation: 'loose', version: 2 },
        conditions: [
          { leftValue: expr('{{ $json.file !== undefined }}'), operator: { type: 'boolean', operation: 'true' }, rightValue: '' },
          { leftValue: expr('{{ /\\.(mp4|m4v|mov|wmv|avi|mkv|webm|mpg|mpeg)$/i.test($json.name) }}'), operator: { type: 'boolean', operation: 'true' }, rightValue: '' },
        ],
        combinator: 'and',
      },
      looseTypeValidation: true,
    },
  },
});

const queuedRows = node({
  type: 'n8n-nodes-base.dataTable',
  version: 1.1,
  config: {
    name: 'Load Queued Drive IDs',
    executeOnce: true,
    alwaysOutputData: true,
    parameters: {
      resource: 'row',
      operation: 'get',
      dataTableId: QUEUE_TABLE,
      matchType: 'allConditions',
      filters: { conditions: [{ keyName: 'driveItemId', condition: 'isNotEmpty' }] },
      returnAll: true,
    },
  },
});

const notQueued = node({
  type: 'n8n-nodes-base.code',
  version: 2,
  config: {
    name: 'Skip Already Queued',
    parameters: {
      mode: 'runOnceForAllItems',
      jsCode:
        "const queued = new Set($input.all().map(i => i.json.driveItemId).filter(Boolean));\nconst videos = $('Videos Only').all();\nconst fresh = videos.filter(v => !queued.has(v.json.id));\nconsole.log(`seed: ${videos.length} videos in folder, ${queued.size} already queued, ${fresh.length} new`);\nreturn fresh;",
    },
  },
});

const insertRow = node({
  type: 'n8n-nodes-base.dataTable',
  version: 1.1,
  config: {
    name: 'Insert Pending Row',
    parameters: {
      resource: 'row',
      operation: 'insert',
      dataTableId: QUEUE_TABLE,
      columns: {
        mappingMode: 'defineBelow',
        value: {
          sourceItemId: expr('{{ $json.listItem.id }}'),
          driveItemId: expr('{{ $json.id }}'),
          fileName: expr('{{ $json.name }}'),
          webUrl: expr('{{ $json.webUrl }}'),
          fileSizeBytes: expr('{{ $json.size }}'),
          status: 'pending',
          attemptCount: 0,
        },
        matchingColumns: [],
        schema: [
          { id: 'sourceItemId', displayName: 'sourceItemId', type: 'string', canBeUsedToMatch: false },
          { id: 'driveItemId', displayName: 'driveItemId', type: 'string', canBeUsedToMatch: false },
          { id: 'fileName', displayName: 'fileName', type: 'string', canBeUsedToMatch: false },
          { id: 'webUrl', displayName: 'webUrl', type: 'string', canBeUsedToMatch: false },
          { id: 'fileSizeBytes', displayName: 'fileSizeBytes', type: 'number', canBeUsedToMatch: false },
          { id: 'status', displayName: 'status', type: 'string', canBeUsedToMatch: false },
          { id: 'attemptCount', displayName: 'attemptCount', type: 'number', canBeUsedToMatch: false },
        ],
      },
    },
  },
});

const notes = sticky(
  '## Keyway - Seed Queue\n\nLists the Recordings & Video User Guides folder via Graph (paginated), keeps video files, drops anything whose driveItemId is already in video_metadata_queue, inserts the rest as status=pending.\n\nSafe to re-run any time. New rows are picked up by Keyway - Process Queue on its next cycle.\n\nSource: pesengineers/keyway, n8n/keyway-seed-queue.workflow.ts. Replaces the frozen "PES Video Metadata - Seed Queue", which is kept for reference and must not be run (it would duplicate rows).',
  undefined,
  { name: 'About This Workflow', color: 4 },
);

export default workflow('keyway-seed-queue', 'Keyway - Seed Queue')
  .add(notes)
  .add(daily)
  .to(listFolder)
  .to(splitChildren)
  .to(videosOnly)
  .to(queuedRows)
  .to(notQueued)
  .to(insertRow);
