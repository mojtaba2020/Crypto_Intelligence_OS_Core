import test from 'node:test';
import assert from 'node:assert/strict';
import worker, { CRON, RAW_WORKFLOW, DISPATCH_URL, TOKEN_CHECK_URL, dispatchOnce, slotFor } from '../src/index.mjs';

const t = (iso, cron = CRON) => ({ cron, scheduledTime: Date.parse(iso) });
const env = {
  BTC4H_CF_ENABLED: 'true',
  BTC4H_SCHEDULE_CUTOVER_CONFIRMED: 'true',
  BTC4H_GITHUB_ACTIONS_TOKEN: 'fake-token-not-a-secret',
};
const safeWorkflow = 'name: BTC4h\non:\n  workflow_dispatch:\n    inputs:\n      phase:\n        type: choice\n';
const unsafeWorkflow = safeWorkflow + '  schedule:\n    - cron: "8 0 * * *"\n';
const response = (status, text) => ({ status, ok: status >= 200 && status < 300, text: async () => text });
function networkStub(calls, text = safeWorkflow, dispatchStatus = 204) {
  return async (url, options) => {
    calls.push({ url, options });
    if (url === RAW_WORKFLOW) return response(200, text);
    if (url === DISPATCH_URL) return response(dispatchStatus, '');
    throw Error('unexpected network path');
  };
}

test('disabled by default never touches the network', async () => {
  const result = await dispatchOnce(t('2026-11-16T08:08:00Z'), {}, {
    clock: () => Date.parse('2026-11-16T08:08:10Z'), fetcher: () => { throw Error('network forbidden'); },
  });
  assert.deepEqual(result, { status: 'disabled', dispatches: 0 });
});

test('opt-in read-only token preflight only GETs the workflow and never dispatches', async () => {
  const calls = [];
  const safe = { ...env, BTC4H_CF_ENABLED: 'false', BTC4H_SCHEDULE_CUTOVER_CONFIRMED: 'false',
    BTC4H_TOKEN_PREFLIGHT: 'true' };
  const result = await dispatchOnce(t('2026-11-16T08:08:00Z'), safe, {
    fetcher: async (url, opts) => {
      calls.push({url,opts});
      return response(200, '{}');
    },
  });
  assert.deepEqual(result, { status: 'token_read_accepted', github_status: 200, dispatches: 0 });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, TOKEN_CHECK_URL);
  assert.equal(calls[0].opts.method, 'GET');
  assert.equal(calls[0].opts.headers.Authorization, 'Bearer fake-token-not-a-secret');
});

test('token preflight refuses incorrect credentials or either live cutover gate', async () => {
  const preflight = { ...env, BTC4H_CF_ENABLED: 'false',
    BTC4H_SCHEDULE_CUTOVER_CONFIRMED: 'false', BTC4H_TOKEN_PREFLIGHT: 'true' };
  const t0 = t('2026-11-16T08:08:00Z');
  await assert.rejects(dispatchOnce(t0, { ...preflight, BTC4H_GITHUB_ACTIONS_TOKEN: '' }, {
    fetcher: () => { throw Error('network forbidden'); },
  }), /missing or malformed/);
  await assert.rejects(dispatchOnce(t0, preflight, {
    fetcher: async () => response(401, ''),
  }), /token preflight HTTP 401/);
  await assert.rejects(dispatchOnce(t0, { ...preflight, BTC4H_CF_ENABLED: 'true' }, {
    fetcher: () => { throw Error('network forbidden'); },
  }), /read-only preflight forbidden/);
  await assert.rejects(dispatchOnce(t0, { ...preflight, BTC4H_SCHEDULE_CUTOVER_CONFIRMED: 'true' }, {
    fetcher: () => { throw Error('network forbidden'); },
  }), /read-only preflight forbidden/);
});

test('requires independent cutover acknowledgement and a secret token', async () => {
  const controller = t('2026-11-16T08:08:00Z');
  const noNetwork = () => { throw Error('network forbidden'); };
  await assert.rejects(dispatchOnce(controller, { ...env, BTC4H_SCHEDULE_CUTOVER_CONFIRMED: 'false' },
    { fetcher: noNetwork }), /cutover not confirmed/);
  await assert.rejects(dispatchOnce(controller, { ...env, BTC4H_GITHUB_ACTIONS_TOKEN: '' },
    { fetcher: noNetwork }), /missing or malformed/);
});

test('all 5 intended UTC phase slots are valid, other slots fail closed', () => {
  for (const [minute, phase] of [[8,'issue'],[10,'issue'],[12,'issue'],[14,'issue'],[20,'score']]) {
    const iso = `2026-11-16T08:${String(minute).padStart(2, '0')}:00Z`;
    assert.equal(slotFor(t(iso), Date.parse(iso) + 15_000).phase, phase);
  }
  assert.throws(() => slotFor(t('2026-11-16T07:08:00Z'), Date.parse('2026-11-16T07:08:10Z')),
    /not a four-hour/);
  assert.throws(() => slotFor(t('2026-11-16T08:09:00Z'), Date.parse('2026-11-16T08:09:10Z')),
    /unexpected trigger minute/);
  assert.throws(() => slotFor(t('2026-11-16T08:08:00Z','* * * * *'), Date.parse('2026-11-16T08:08:10Z')),
    /unknown cron/);
});

test('late issue attempts cannot masquerade as four-hour forecasts', () => {
  assert.throws(() => slotFor(t('2026-11-16T08:14:00Z'), Date.parse('2026-11-16T08:15:00Z')),
    /late\/stale/);
  assert.throws(() => slotFor(t('2026-11-16T08:08:00Z'), Date.parse('2026-11-16T08:11:00Z')),
    /late\/stale/);
  assert.throws(() => slotFor(t('2026-11-16T08:20:00Z'), Date.parse('2026-11-16T08:31:00Z')),
    /late\/stale/);
});

test('current live main schedule blocks any production dispatch', async () => {
  const calls = [];
  await assert.rejects(dispatchOnce(t('2026-11-16T08:10:00Z'), env, {
    clock: () => Date.parse('2026-11-16T08:10:10Z'),
    fetcher: networkStub(calls, unsafeWorkflow),
  }), /main GitHub cron still present/);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, RAW_WORKFLOW);
});

test('valid issue request emits exactly one narrow GitHub Actions dispatch (mock only)', async () => {
  const calls = [];
  const result = await dispatchOnce(t('2026-11-16T08:08:00Z'), env, {
    clock: () => Date.parse('2026-11-16T08:08:10Z'),
    fetcher: networkStub(calls),
  });
  assert.equal(result.status, 'accepted_by_github');
  assert.equal(result.phase, 'issue');
  assert.equal(calls.length, 2);
  assert.equal(calls[1].url, DISPATCH_URL);
  assert.deepEqual(JSON.parse(calls[1].options.body), { ref: 'main', inputs: { phase: 'issue' } });
  assert.equal(calls[1].options.headers.Authorization, 'Bearer fake-token-not-a-secret');
});

test('valid score-only request dispatches score, never creates a forecast (mock only)', async () => {
  const calls = [];
  const result = await dispatchOnce(t('2026-11-16T12:20:00Z'), env, {
    clock: () => Date.parse('2026-11-16T12:20:20Z'), fetcher: networkStub(calls, safeWorkflow, 200),
  });
  assert.equal(result.phase, 'score');
  assert.deepEqual(JSON.parse(calls[1].options.body).inputs, { phase: 'score' });
});

test('remote inspection failure and dispatch failures do not claim success', async () => {
  await assert.rejects(dispatchOnce(t('2026-11-16T08:08:00Z'), env, {
    clock: () => Date.parse('2026-11-16T08:08:10Z'),
    fetcher: async () => response(503, ''),
  }), /inspection HTTP 503/);
  const calls = [];
  await assert.rejects(dispatchOnce(t('2026-11-16T08:08:00Z'), env, {
    clock: () => Date.parse('2026-11-16T08:08:10Z'),
    fetcher: networkStub(calls, safeWorkflow, 401),
  }), /dispatch HTTP 401/);
});

test('public HTTP endpoints cannot manually trigger dispatch', async () => {
  const result = await worker.fetch({url:'https://example.workers.dev/dispatch',method:'GET'}, env);
  assert.equal(result.status, 404);
  assert.equal((await worker.fetch({url:'https://example.workers.dev/__health',method:'POST'}, env)).status, 404);
});

test('health attestation exposes only gate readiness, without contacting GitHub', async () => {
  const url = 'https://example.workers.dev/__health';
  const response = await worker.fetch({url,method:'GET'}, env);
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), {
    service: 'btc4h-free-scheduler-preflight',
    version: 'cutover-health-v1',
    armed: true, dispatches: 0,
  });
  const disabled = await worker.fetch({url,method:'GET'},
    {...env,BTC4H_CF_ENABLED:'false'});
  assert.equal((await disabled.json()).armed, false);
  assert.equal(response.headers.get('Cache-Control'), 'no-store');
});
