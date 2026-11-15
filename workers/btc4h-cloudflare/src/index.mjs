/**
 * Disabled-by-default free-tier scheduling gateway.
 * Only requests GitHub Actions; it does not calculate, score, publish, or trade.
 * Competing GitHub cron must be removed only in a separately approved cutover.
 */
export const CRON = '8,10,12,14,20 0,4,8,12,16,20 * * *';
export const REPO = 'mojtaba2020/Crypto_Intelligence_OS_Core';
export const WORKFLOW = 'btc4h_continuous.yml';
export const RAW_WORKFLOW = `https://raw.githubusercontent.com/${REPO}/main/.github/workflows/${WORKFLOW}`;
export const DISPATCH_URL = `https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`;

function fail(message) {
  throw new Error(`BTC4H_CF_FAIL_CLOSED: ${message}`);
}

export function slotFor(controller, nowMs) {
  if (controller?.cron !== CRON) fail('unknown cron trigger');
  const scheduledMs = Number(controller?.scheduledTime);
  if (!Number.isSafeInteger(scheduledMs)) fail('invalid Cloudflare scheduledTime');
  if (!Number.isSafeInteger(nowMs)) fail('invalid runtime clock');
  const scheduled = new Date(scheduledMs);
  const current = new Date(nowMs);
  if (Number.isNaN(scheduled.getTime()) || Number.isNaN(current.getTime())) fail('invalid clock');
  const hour = scheduled.getUTCHours();
  const minute = scheduled.getUTCMinutes();
  if (scheduled.getUTCSeconds() !== 0 || scheduled.getUTCMilliseconds() !== 0) {
    fail('scheduled UTC time not minute-aligned');
  }
  if (hour % 4 !== 0) fail('not a four-hour UTC origin');
  let phase;
  let maxLagMs;
  if ([8, 10, 12, 14].includes(minute)) {
    phase = 'issue';
    maxLagMs = Math.min(120_000, (15 - minute) * 60_000);
  } else if (minute === 20) {
    phase = 'score';
    maxLagMs = 10 * 60_000;
  } else {
    fail('unexpected trigger minute');
  }
  if (nowMs < scheduledMs || nowMs >= scheduledMs + maxLagMs) fail('late/stale cron dispatch');
  if (current.getUTCHours() !== hour || current.getUTCDate() !== scheduled.getUTCDate() ||
      current.getUTCMonth() !== scheduled.getUTCMonth() || current.getUTCFullYear() !== scheduled.getUTCFullYear()) {
    fail('dispatch crossed origin calendar boundary');
  }
  return { phase, scheduled_utc: scheduled.toISOString(), actual_utc: current.toISOString() };
}

async function checkedResponse(response, label) {
  if (!response || typeof response.status !== 'number') fail(`${label} missing HTTP response`);
  if (!response.ok) fail(`${label} HTTP ${response.status}`);
  return response;
}

export async function dispatchOnce(controller, env, { clock = Date.now, fetcher = fetch } = {}) {
  if (env?.BTC4H_CF_ENABLED !== 'true') return { status: 'disabled', dispatches: 0 };
  if (env.BTC4H_SCHEDULE_CUTOVER_CONFIRMED !== 'true') fail('cutover not confirmed');
  if (!env.BTC4H_GITHUB_ACTIONS_TOKEN || !/^\S+$/.test(env.BTC4H_GITHUB_ACTIONS_TOKEN)) {
    fail('missing or malformed GitHub Actions token');
  }
  const slot = slotFor(controller, clock());
  const workflowResponse = await checkedResponse(await fetcher(RAW_WORKFLOW, {
    method: 'GET', headers: { 'Cache-Control': 'no-cache' },
  }), 'main workflow inspection');
  const workflowText = await workflowResponse.text();
  if (!/^on:\s*$/m.test(workflowText) || !/^\s{2}workflow_dispatch:\s*$/m.test(workflowText)) {
    fail('expected workflow dispatch definition missing');
  }
  if (/^\s{2}schedule:\s*(?:#.*)?$/m.test(workflowText)) {
    fail('main GitHub cron still present: two publishers forbidden');
  }
  slotFor(controller, clock());
  const response = await fetcher(DISPATCH_URL, {
    method: 'POST',
    headers: {
      'Accept': 'application/vnd.github+json',
      'Authorization': `Bearer ${env.BTC4H_GITHUB_ACTIONS_TOKEN}`,
      'Content-Type': 'application/json',
      'User-Agent': 'btc4h-free-cron-gateway',
      'X-GitHub-Api-Version': '2022-11-28',
    },
    body: JSON.stringify({ ref: 'main', inputs: { phase: slot.phase } }),
  });
  if (!response || ![200, 204].includes(response.status)) {
    fail(`GitHub dispatch HTTP ${response?.status ?? 'unknown'}`);
  }
  // A dispatch acceptance is NOT proof of a correctly issued forecast.
  return { status: 'accepted_by_github', dispatches: 1, phase: slot.phase,
    scheduled_utc: slot.scheduled_utc, github_status: response.status };
}

export default {
  async scheduled(controller, env) {
    const outcome = await dispatchOnce(controller, env);
    console.log(JSON.stringify(outcome));
  },
  async fetch() {
    return new Response('Not found', { status: 404 });
  },
};
