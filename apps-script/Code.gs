/* Shared work allocation. Deploy once as the owner; clients never edit sheet rows. */
const CAMPAIGN_HEADERS = ['campaign_id', 'fingerprint', 'created_at'];
const TASK_HEADERS = [
  'campaign_id', 'batch_id', 'provider', 'total', 'worker', 'claim', 'status',
  'completed', 'failed', 'valid', 'updated_at', 'archive', 'archive_sha256', 'result_url'
];

function setup() {
  const props = PropertiesService.getScriptProperties();
  if (!props.getProperty('SHEET_ID')) {
    props.setProperty('SHEET_ID', SpreadsheetApp.getActiveSpreadsheet().getId());
  }
  if (!props.getProperty('TEAM_KEY')) {
    props.setProperty('TEAM_KEY', Utilities.getUuid() + Utilities.getUuid());
  }
  const book = SpreadsheetApp.openById(props.getProperty('SHEET_ID'));
  [['Campaigns', CAMPAIGN_HEADERS], ['Tasks', TASK_HEADERS]].forEach(([name, headers]) => {
    const sheet = book.getSheetByName(name) || book.insertSheet(name);
    if (sheet.getLastRow() === 0) {
      sheet.appendRow(headers);
      sheet.setFrozenRows(1);
    }
  });
  // TEAM_KEY is available in Project Settings > Script properties. Never log it.
}

function doPost(event) {
  let result;
  try {
    result = handleRequest(JSON.parse(event.postData.contents));
  } catch (_) {
    result = {ok: false};
  }
  return ContentService.createTextOutput(JSON.stringify(result))
    .setMimeType(ContentService.MimeType.JSON);
}

function records(sheet, headers) {
  if (sheet.getLastRow() < 2) return [];
  return sheet.getRange(2, 1, sheet.getLastRow() - 1, headers.length).getValues()
    .map((values, index) => ({row: index + 2, values}));
}

function identifier(value) {
  return typeof value === 'string' && /^[a-zA-Z0-9_-]{1,64}$/.test(value);
}

function handleRequest(p) {
  const props = PropertiesService.getScriptProperties();
  const key = props.getProperty('TEAM_KEY');
  if (!key || p.key !== key || !identifier(p.campaign_id) ||
      typeof p.fingerprint !== 'string' || !/^[0-9a-f]{64}$/.test(p.fingerprint)) {
    throw new Error('Invalid request');
  }
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const book = SpreadsheetApp.openById(props.getProperty('SHEET_ID'));
    const campaigns = book.getSheetByName('Campaigns');
    const tasks = book.getSheetByName('Tasks');
    const campaign = records(campaigns, CAMPAIGN_HEADERS)
      .find(r => r.values[0] === p.campaign_id);
    let all = records(tasks, TASK_HEADERS);
    if (p.action === 'register') {
      if (campaign && campaign.values[1] !== p.fingerprint) throw new Error('Campaign changed');
      if (!Array.isArray(p.tasks) || !p.tasks.length) throw new Error('Empty campaign');
      const seen = new Set();
      p.tasks.forEach(t => {
        const id = t.batch_id + '/' + t.provider;
        if (!/^\d{4,}$/.test(t.batch_id) || !['codex', 'claude'].includes(t.provider) ||
            !Number.isInteger(t.total) || t.total < 1 || seen.has(id)) throw new Error('Invalid task');
        seen.add(id);
      });
      const existing = all.filter(r => r.values[0] === p.campaign_id);
      existing.forEach(r => {
        const t = p.tasks.find(t => t.batch_id === r.values[1] && t.provider === r.values[2]);
        if (!t || t.total !== r.values[3]) throw new Error('Task changed');
      });
      // Register is idempotent and repairs an interrupted first registration.
      if (!campaign) campaigns.appendRow([p.campaign_id, p.fingerprint, new Date().toISOString()]);
      const missing = p.tasks.filter(t => !existing.some(r => r.values[1] === t.batch_id && r.values[2] === t.provider));
      if (missing.length) {
        const rows = missing.map(t => [p.campaign_id, t.batch_id, t.provider, t.total,
          '', '', 'available', 0, 0, 0, new Date().toISOString(), '', '', '']);
        tasks.getRange(tasks.getLastRow() + 1, 1, rows.length, TASK_HEADERS.length)
          .setNumberFormat('@').setValues(rows);
      }
      return {ok: true, tasks: p.tasks.length};
    }
    if (!campaign || campaign.values[1] !== p.fingerprint) throw new Error('Unknown campaign');
    all = all.filter(r => r.values[0] === p.campaign_id);
    if (p.action === 'status') {
      return {ok: true, counts: all.reduce((counts, r) => {
        counts[r.values[6]] = (counts[r.values[6]] || 0) + 1;
        return counts;
      }, {})};
    }
    if (!identifier(p.worker) || !['codex', 'claude'].includes(p.provider)) throw new Error('Invalid worker');
    if (p.action === 'acquire') {
      const own = all.find(r => r.values[2] === p.provider && r.values[4] === p.worker &&
        !['available', 'submitted'].includes(r.values[6]));
      const chosen = own || all.find(r => r.values[2] === p.provider && r.values[6] === 'available');
      if (!chosen) return {ok: true, assignment: null};
      if (!own) {
        chosen.values[4] = p.worker;
        chosen.values[5] = Utilities.getUuid();
        chosen.values[6] = 'reserved';
        chosen.values[10] = new Date().toISOString();
        tasks.getRange(chosen.row, 1, 1, TASK_HEADERS.length).setNumberFormat('@').setValues([chosen.values]);
      }
      return {ok: true, assignment: {batch_id: chosen.values[1], claim: chosen.values[5]}};
    }
    const current = all.find(r => r.values[1] === p.batch_id && r.values[2] === p.provider &&
      r.values[4] === p.worker && r.values[5] === p.claim);
    // A release response may be lost. Retrying must never release another worker's new claim.
    if (!current && p.action === 'release') return {ok: true, released: true};
    if (!current) throw new Error('Stale claim');
    const row = current.values;
    if (p.action === 'release') {
      if (row[7] || row[8] || row[6] === 'submitted') throw new Error('Cannot release results');
      row[4] = ''; row[5] = ''; row[6] = 'available';
    } else if (p.action === 'update') {
      if (!['reserved', 'running', 'paused', 'generated', 'submitted'].includes(p.status) ||
          ![p.completed, p.failed, p.valid].every(n => Number.isInteger(n) && n >= 0) ||
          p.completed + p.failed > row[3] || p.valid > p.completed ||
          (['generated', 'submitted'].includes(p.status) && p.completed !== row[3])) {
        throw new Error('Invalid progress');
      }
      if (row[6] === 'submitted' && p.status !== 'submitted') throw new Error('Already submitted');
      const archive = p.archive || {};
      if (p.status === 'submitted' && (!archive.name || !/^[0-9a-f]{64}$/.test(archive.sha256 || ''))) {
        throw new Error('Archive required');
      }
      row[6] = p.status; row[7] = p.completed; row[8] = p.failed; row[9] = p.valid;
      if (archive.name) {
        row[11] = String(archive.name).replace(/^[=+@-]/, '_');
        row[12] = archive.sha256;
      }
      if (p.result_url) {
        if (!/^https:\/\//.test(p.result_url)) throw new Error('Invalid result URL');
        row[13] = p.result_url;
      }
    } else {
      throw new Error('Unknown action');
    }
    row[10] = new Date().toISOString();
    tasks.getRange(current.row, 1, 1, TASK_HEADERS.length).setNumberFormat('@').setValues([row]);
    return {ok: true, status: row[6]};
  } finally {
    try {
      SpreadsheetApp.flush();
    } finally {
      lock.releaseLock();
    }
  }
}
