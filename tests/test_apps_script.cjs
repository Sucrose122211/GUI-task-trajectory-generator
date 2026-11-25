const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const test = require('node:test');

function fixture() {
  let held = false;
  let locks = 0;
  class Sheet {
    constructor() { this.rows = []; }
    getLastRow() { return this.rows.length; }
    appendRow(row) { this.rows.push([...row]); }
    setFrozenRows() {}
    getRange(start, col, count, width) {
      return {
        getValues: () => this.rows.slice(start - 1, start - 1 + count).map(r => [...r]),
        setNumberFormat() { return this; },
        setValues: rows => {
          assert.equal(held, true, 'Every allocation/progress mutation must hold the shared lock');
          rows.forEach((r, i) => { this.rows[start - 1 + i] = [...r]; });
        }
      };
    }
  }
  const sheets = {};
  const book = {getId: () => 'sheet', getSheetByName: name => sheets[name],
    insertSheet: name => (sheets[name] = new Sheet())};
  const properties = {SHEET_ID: 'sheet', TEAM_KEY: 'fixture-key'};
  let uuid = 0;
  const context = vm.createContext({
    PropertiesService: {getScriptProperties: () => ({
      getProperty: key => properties[key], setProperty: (key, value) => { properties[key] = value; }
    })},
    SpreadsheetApp: {getActiveSpreadsheet: () => book, openById: () => book, flush() {}},
    Utilities: {getUuid: () => `claim-${String(++uuid).padStart(8, '0')}`},
    LockService: {getScriptLock: () => ({
      waitLock() { assert.equal(held, false); held = true; locks++; },
      releaseLock() { assert.equal(held, true); held = false; }
    })},
    ContentService: {MimeType: {JSON: 'json'}, createTextOutput: text => ({
      text, setMimeType() { return this; }
    })}
  });
  vm.runInContext(fs.readFileSync('apps-script/Code.gs', 'utf8'), context);
  context.setup();
  const base = {key: 'fixture-key', campaign_id: 'demo', fingerprint: 'a'.repeat(64)};
  const call = data => context.handleRequest({...base, ...data});
  const tasks = [
    {batch_id: '0000', provider: 'codex', total: 2},
    {batch_id: '0000', provider: 'claude', total: 2},
    {batch_id: '0001', provider: 'codex', total: 1}
  ];
  call({action: 'register', tasks});
  return {call, context, tasks, sheets, held: () => held, locks: () => locks};
}

test('idempotent register, distinct claims and paired teachers', () => {
  const f = fixture();
  f.call({action: 'register', tasks: f.tasks});
  assert.equal(f.sheets.Tasks.rows.length, 4);
  const a = f.call({action: 'acquire', worker: 'alice', provider: 'codex'}).assignment;
  const retry = f.call({action: 'acquire', worker: 'alice', provider: 'codex'}).assignment;
  assert.equal(a.claim, retry.claim);
  const b = f.call({action: 'acquire', worker: 'bob', provider: 'codex'}).assignment;
  assert.notEqual(a.batch_id, b.batch_id);
  const c = f.call({action: 'acquire', worker: 'carol', provider: 'claude'}).assignment;
  assert.equal(c.batch_id, a.batch_id);
  assert.equal(f.call({action: 'acquire', worker: 'dave', provider: 'codex'}).assignment, null);
  assert.equal(f.held(), false);
  assert.ok(f.locks() >= 6);
});

test('release invalidates old token, progress cannot claim partial completion', () => {
  const f = fixture();
  const a = f.call({action: 'acquire', worker: 'alice', provider: 'codex'}).assignment;
  const owner = {worker: 'alice', provider: 'codex', ...a};
  f.call({...owner, action: 'release'});
  f.call({action: 'acquire', worker: 'bob', provider: 'codex'});
  assert.equal(f.call({...owner, action: 'release'}).released, true);
  assert.throws(() => f.call({...owner, action: 'update', status: 'running', completed: 0, failed: 0, valid: 0}));
  assert.equal(f.held(), false);
  const b = f.call({action: 'acquire', worker: 'bob', provider: 'codex'}).assignment;
  const update = {action: 'update', worker: 'bob', provider: 'codex', ...b, completed: 1, failed: 0, valid: 0};
  f.call({...update, status: 'running'});
  assert.throws(() => f.call({...update, status: 'submitted'}));
  assert.throws(() => f.call({...update, action: 'release'}));
  assert.throws(() => f.call({...update, status: 'submitted', completed: 2}));
  f.call({...update, status: 'submitted', completed: 2, archive: {name: 'batch.zip', sha256: 'b'.repeat(64)}});
  assert.throws(() => f.call({...update, status: 'running'}));
  assert.equal(f.call({action: 'acquire', worker: 'bob', provider: 'codex'}).assignment.batch_id, '0001');
});

test('reject mismatched experiments and keys without exposing request secrets', () => {
  const f = fixture();
  assert.throws(() => f.call({action: 'register', tasks: f.tasks, fingerprint: 'b'.repeat(64)}));
  const response = f.context.doPost({postData: {contents: JSON.stringify({key: 'DO_NOT_ECHO', action: 'status'})}});
  assert.equal(response.text, '{"ok":false}');
  assert.equal(f.held(), false);
});

test('repeated setup and interrupted registration preserve existing work', () => {
  const f = fixture();
  const claim = f.call({action: 'acquire', worker: 'alice', provider: 'codex'}).assignment.claim;
  f.context.setup();
  f.sheets.Tasks.rows.pop();
  f.call({action: 'register', tasks: f.tasks});
  assert.equal(f.sheets.Tasks.rows.length, 4);
  assert.equal(f.call({action: 'acquire', worker: 'alice', provider: 'codex'}).assignment.claim, claim);
});
