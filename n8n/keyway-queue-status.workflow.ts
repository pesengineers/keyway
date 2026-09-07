// Keyway - Queue Status
//
// Operator report. Open the form URL (n8n login required), press Submit, and
// get a page with: counts by status, the most recent completed videos, and every
// row that needs a human (flagged or error) with its reason. Read-only; touches
// nothing. Deployed with the n8n MCP tool (docs/n8n-integration.md section 6).

import { workflow, node, trigger, sticky, expr } from '@n8n/workflow-sdk';

const QUEUE_TABLE = { __rl: true, mode: 'id', value: 'QMOVCsZrJKJuT2Cz', cachedResultName: 'video_metadata_queue' };

const form = trigger({
  type: 'n8n-nodes-base.formTrigger',
  version: 2.6,
  config: {
    name: 'Status Form',
    parameters: {
      authentication: 'n8nUserAuth',
      path: 'keyway-status',
      formTitle: 'Keyway: queue status',
      formDescription: 'Press Submit for a snapshot of the video metadata queue.',
      formFields: { values: [{ fieldName: 'refresh', fieldLabel: 'Refresh', fieldType: 'hiddenField', fieldValue: '1' }] },
      responseMode: 'lastNode',
      options: { appendAttribution: false },
    },
  },
});

const loadAll = node({
  type: 'n8n-nodes-base.dataTable',
  version: 1.1,
  config: {
    name: 'Load All Rows',
    executeOnce: true,
    alwaysOutputData: true,
    parameters: { resource: 'row', operation: 'get', dataTableId: QUEUE_TABLE, matchType: 'allConditions', filters: { conditions: [{ keyName: 'status', condition: 'isNotEmpty' }] }, returnAll: true },
  },
});

const render = node({
  type: 'n8n-nodes-base.code',
  version: 2,
  config: {
    name: 'Render Report',
    parameters: {
      mode: 'runOnceForAllItems',
      jsCode: `const rows = $input.all().map(i => i.json).filter(r => r.status);
const esc = s => String(s ?? '').replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const order = ['done','processing','pending','flagged_internal','flagged_review','unprocessable','error'];
const counts = {}; for (const r of rows) counts[r.status] = (counts[r.status] || 0) + 1;
const total = rows.length; const done = counts.done || 0;
const bytes = rows.reduce((a, r) => a + (Number(r.fileSizeBytes) || 0), 0);
const countRows = order.filter(s => counts[s]).map(s => \`<tr><td>\${s}</td><td style='text-align:right'>\${counts[s]}</td></tr>\`).join('');
const byTime = [...rows].sort((a, b) => String(b.updatedAt || '').localeCompare(String(a.updatedAt || '')));
const recent = byTime.filter(r => r.status === 'done').slice(0, 8).map(r => \`<tr><td>\${r.id}</td><td><a href='\${esc(r.webUrl)}' target='_blank'>\${esc(r.fileName)}</a></td><td>\${esc(r.title)}</td><td>\${esc(r.presentationDate)}</td></tr>\`).join('');
const attention = byTime.filter(r => ['flagged_internal','flagged_review','error','unprocessable'].includes(r.status)).map(r => \`<tr><td>\${r.id}</td><td>\${r.status}</td><td><a href='\${esc(r.webUrl)}' target='_blank'>\${esc(r.fileName)}</a></td><td>\${esc(r.sensitivityReason || r.errorMessage)}</td><td>\${r.attemptCount ?? ''}</td></tr>\`).join('');
const stuck = rows.filter(r => r.status === 'processing' && r.lastAttemptAt && (Date.now() - new Date(r.lastAttemptAt).getTime()) > 3600e3);
const stuckNote = stuck.length ? \`<p style='color:#b00'><b>\${stuck.length} row(s) have been 'processing' for over an hour</b> (ids \${stuck.map(r => r.id).join(', ')}). Keyway may have restarted mid-job; reset them via Keyway - Reset Queue Rows.</p>\` : '';
const pct = total ? Math.round(100 * done / total) : 0;
const html = \`<!doctype html><html><head><meta charset='utf-8'><title>Keyway queue status</title><style>body{font-family:system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#222}table{border-collapse:collapse;width:100%;margin:.5rem 0 1.5rem}td,th{border:1px solid #ddd;padding:.35rem .6rem;text-align:left;vertical-align:top}th{background:#f3f3f3}.bar{background:#eee;height:14px;border-radius:7px;overflow:hidden}.bar div{background:#2a7;height:100%}small{color:#666}</style></head><body>\` +
  \`<h1>Keyway queue status</h1><small>Generated \${new Date().toISOString()} · \${total} videos · \${(bytes/1e9).toFixed(1)} GB</small>\` +
  \`<h2>\${done} of \${total} complete (\${pct}%)</h2><div class='bar'><div style='width:\${pct}%'></div></div>\` + stuckNote +
  \`<h3>By status</h3><table><tr><th>status</th><th>count</th></tr>\${countRows}</table>\` +
  \`<h3>Needs a human (\${attention ? byTime.filter(r => ['flagged_internal','flagged_review','error','unprocessable'].includes(r.status)).length : 0})</h3>\` +
  (attention ? \`<table><tr><th>id</th><th>status</th><th>file</th><th>reason</th><th>attempts</th></tr>\${attention}</table>\` : '<p>None.</p>') +
  \`<h3>Recently completed</h3>\` + (recent ? \`<table><tr><th>id</th><th>file</th><th>title</th><th>date</th></tr>\${recent}</table>\` : '<p>None yet.</p>') +
  \`<p><small>Statuses and what to do about them: docs/operations.md in pesengineers/keyway. Reset rows: the Keyway - Reset Queue Rows form.</small></p></body></html>\`;
return [{ json: { html } }];`,
    },
  },
});

const respond = node({
  type: 'n8n-nodes-base.respondToWebhook',
  version: 1.4,
  config: {
    name: 'Show Report',
    parameters: {
      respondWith: 'text',
      responseBody: expr('{{ $json.html }}'),
      options: { responseHeaders: { entries: [{ name: 'Content-Type', value: 'text/html; charset=utf-8' }] } },
    },
  },
});

const notes = sticky(
  '## Keyway - Queue Status\n\nRead-only report. Open the Status Form URL (n8n login), press Submit. Shows progress, counts by status, rows needing a human, and recent completions with links to the videos.\n\nSource: pesengineers/keyway, n8n/keyway-queue-status.workflow.ts.',
  undefined,
  { name: 'About This Workflow', color: 4 },
);

export default workflow('keyway-queue-status', 'Keyway - Queue Status')
  .add(notes)
  .add(form)
  .to(loadAll)
  .to(render)
  .to(respond);
