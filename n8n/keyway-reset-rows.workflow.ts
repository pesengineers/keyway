// Keyway - Reset Queue Rows
//
// Operator helper. A login-protected n8n form takes a comma-separated list of
// video_metadata_queue row ids and puts them back to status=pending, clearing
// any earlier result/error fields so "Keyway - Process Queue" will pick them up
// on its next cycle. Use it after fixing whatever caused an error or after a
// human has reviewed a flagged item and decided it should be reprocessed.
//
// Deployed with the n8n MCP tool (docs/n8n-integration.md section 6). Does not
// touch the frozen "PES Video Metadata - *" workflows.

import { workflow, node, trigger, sticky, expr } from '@n8n/workflow-sdk';

const QUEUE_TABLE = { __rl: true, mode: 'id', value: 'QMOVCsZrJKJuT2Cz', cachedResultName: 'video_metadata_queue' };

const form = trigger({
  type: 'n8n-nodes-base.formTrigger',
  version: 2.6,
  config: {
    name: 'Reset Rows Form',
    parameters: {
      authentication: 'n8nUserAuth',
      formTitle: 'Keyway: reset queue rows',
      formDescription:
        'Puts the listed video_metadata_queue rows back to status=pending and clears prior results so Keyway - Process Queue reprocesses them on its next run.',
      formFields: {
        values: [
          {
            fieldName: 'rowIds',
            fieldLabel: 'Row IDs (comma-separated, e.g. 1, 2, 17)',
            fieldType: 'text',
            requiredField: true,
          },
        ],
      },
      // Form Trigger v2.6 reads the custom URL path from options.path; the top-level `path` is ignored.
      options: { appendAttribution: false, path: 'keyway-reset-rows' },
    },
  },
});

const splitIds = node({
  type: 'n8n-nodes-base.code',
  version: 2,
  config: {
    name: 'One Item Per Row ID',
    parameters: {
      mode: 'runOnceForAllItems',
      jsCode:
        "const raw = String($input.first().json.rowIds || '');\nconst ids = raw.split(/[\\s,;]+/).map(s => s.trim()).filter(s => /^\\d+$/.test(s));\nif (ids.length === 0) { throw new Error('No numeric row ids supplied'); }\nreturn ids.map(id => ({ json: { rowId: Number(id) } }));",
    },
  },
});

const resetRow = node({
  type: 'n8n-nodes-base.dataTable',
  version: 1.1,
  config: {
    name: 'Set Row Pending',
    parameters: {
      resource: 'row',
      operation: 'update',
      dataTableId: QUEUE_TABLE,
      matchType: 'allConditions',
      filters: { conditions: [{ keyName: 'id', condition: 'eq', keyValue: expr('{{ $json.rowId }}') }] },
      columns: {
        mappingMode: 'defineBelow',
        value: {
          status: 'pending',
          title: '',
          presentationDate: '',
          synopsis: '',
          isSensitive: false,
          sensitivityReason: '',
          errorMessage: '',
        },
        schema: [
          { id: 'status', displayName: 'status', type: 'string', canBeUsedToMatch: false },
          { id: 'title', displayName: 'title', type: 'string', canBeUsedToMatch: false },
          { id: 'presentationDate', displayName: 'presentationDate', type: 'string', canBeUsedToMatch: false },
          { id: 'synopsis', displayName: 'synopsis', type: 'string', canBeUsedToMatch: false },
          { id: 'isSensitive', displayName: 'isSensitive', type: 'boolean', canBeUsedToMatch: false },
          { id: 'sensitivityReason', displayName: 'sensitivityReason', type: 'string', canBeUsedToMatch: false },
          { id: 'errorMessage', displayName: 'errorMessage', type: 'string', canBeUsedToMatch: false },
        ],
      },
    },
  },
});

const confirm = node({
  type: 'n8n-nodes-base.form',
  version: 2.5,
  config: {
    name: 'Confirm Reset',
    executeOnce: true,
    parameters: {
      operation: 'completion',
      respondWith: 'text',
      completionTitle: 'Rows reset',
      completionMessage: expr("{{ $('Set Row Pending').all().length }} row(s) set back to pending. Keyway - Process Queue will pick them up on its next 15-minute cycle."),
    },
  },
});

const notes = sticky(
  '## Keyway - Reset Queue Rows\n\nOperator tool. Open the form (Reset Rows Form node > Form URL; requires n8n login), enter row ids, submit.\n\nEach id is set back to status=pending with title/synopsis/date/sensitivity/error cleared. attemptCount is kept on purpose so repeated failures stay visible.\n\nSource: pesengineers/keyway, n8n/keyway-reset-rows.workflow.ts. Does not touch the frozen "PES Video Metadata - *" workflows.',
  undefined,
  { name: 'About This Workflow', color: 4 },
);

export default workflow('keyway-reset-rows', 'Keyway - Reset Queue Rows')
  .add(notes)
  .add(form)
  .to(splitIds)
  .to(resetRow)
  .to(confirm);
