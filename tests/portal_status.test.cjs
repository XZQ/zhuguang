const assert = require('node:assert/strict');
const {evaluate} = require('../scripts/assets/portal-status.js');
const now = Date.parse('2026-09-07T00:00:00Z');
const names = ['orchestrator', 'sentry', 'diagnoser', 'executor', 'auditor'];
function snapshot(status, observed_at = '2026-09-07T00:00:00Z', model = 'configured') {
  return {schema_version: 1, workers: names.map(name => ({name, status, observed_at, model}))};
}
assert.equal(evaluate(null, now).state, 'unknown');
assert.equal(evaluate({}, now).state, 'unknown');
assert.equal(evaluate(snapshot('offline'), now).online, 0);
assert.match(evaluate(snapshot('offline'), now).label, /0\/5/);
assert.equal(evaluate(snapshot('online'), now).online, 5);
assert.equal(evaluate(snapshot('online'), now).state, 'healthy');
assert.equal(evaluate(snapshot('online', '2026-09-06T00:00:00Z'), now).state, 'stale');
assert.equal(evaluate(snapshot('online', '2026-09-08T00:00:00Z'), now).state, 'stale');
assert.equal(evaluate(snapshot('online'), now, 'other-model').state, 'degraded');
assert.equal(evaluate({...snapshot('online'), health: 'degraded'}, now).state, 'degraded');
assert.equal(evaluate({schema_version: 1, workers: []}, now).state, 'unknown');
console.log('PORTAL_STATUS_OK');
