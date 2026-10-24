// Manual-only VK ID refresh probe for GitHub Actions.
// Provider writes: OAuth refresh ONLY. Never calls video.save, uploads or publishes.
// New rotating refresh token MUST be stored before read-only VK API calls.
import { randomBytes } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import {
  buildVkRefreshRequest, parseVkRefreshResponse, readOnlyVkTokenCheck
} from './vk-refresh-lib.mjs';

const REPO = 'lsevmos-gpt/ls-vk';
const APP_ID = '54806879';
const DEFAULT_REDIRECT = 'https://vk.liniyasporta.ru/oauth/callback';
const CANARY_SECRET = 'VK_REFRESH_WRITE_PROBE';

function requireLiveRunner() {
  const fromOwnerManual =
    process.env.GITHUB_EVENT_NAME === 'workflow_dispatch';
  const fromOwnerOneShot =
    process.env.GITHUB_EVENT_NAME === 'push' &&
    process.env.VK_REFRESH_ONE_SHOT === 'LS_VK_20261024' &&
    process.env.GITHUB_WORKFLOW_REF ===
      'lsevmos-gpt/ls-vk/.github/workflows/vk-refresh-one-shot.yml@refs/heads/main';
  if (process.env.GITHUB_REPOSITORY !== REPO ||
      process.env.GITHUB_REF !== 'refs/heads/main' ||
      process.env.GITHUB_ACTOR !== 'lsevmos-gpt' ||
      !(fromOwnerManual || fromOwnerOneShot) ||
      process.env.VK_REFRESH_CONFIRM !== 'ROTATE_REFRESH_TOKEN') {
    throw new Error('UNAUTHORIZED_RUN_CONTEXT');
  }
}

function requiredSecret(name) {
  const value = process.env[name];
  if (!value || !value.trim()) throw new Error('MISSING_' + name);
  return value.trim();
}

function ghSecretCommand(argv, value, pat) {
  const env = {
    PATH: process.env.PATH || '',
    HOME: process.env.HOME || '',
    GH_TOKEN: pat,
    GH_HOST: 'github.com',
    CI: 'true'
  };
  // Always capture and discard stdout/stderr; never log tokens or provider messages.
  const result = spawnSync('gh', argv, {
    input: value || '',
    encoding: 'utf8',
    env,
    timeout: 30000,
    maxBuffer: 65536
  });
  if (result.error || result.status !== 0) throw new Error('GITHUB_SECRET_OPERATION_FAILED');
}

function storeRepoSecret(name, value, pat) {
  ghSecretCommand(['secret', 'set', name, '--repo', REPO], value, pat);
}

function deleteRepoSecret(name, pat) {
  ghSecretCommand(['secret', 'delete', name, '--repo', REPO], '', pat);
}

function verifyGithubSecretWrite(pat) {
  // This preflight must succeed BEFORE making a potentially rotating VK refresh call.
  storeRepoSecret(CANARY_SECRET, randomBytes(32).toString('base64url'), pat);
  try {
    deleteRepoSecret(CANARY_SECRET, pat);
  } catch {
    // A leftover random canary has no rights; secret-write capability was proven.
    console.log('GITHUB_WRITE_PROBE_CLEANUP=SKIPPED');
  }
  console.log('GITHUB_SECRET_WRITE_PREFLIGHT=OK');
}

async function run() {
  const mode = process.argv[2] || 'dry-run';
  if (mode === 'dry-run') {
    const sample = buildVkRefreshRequest({
      clientId: APP_ID, redirectUri: DEFAULT_REDIRECT,
      deviceId: 'synthetic-device', refreshToken: 'synthetic-refresh',
      state: 'synthetic-state'
    });
    if (new URL(sample.url).searchParams.get('grant_type') !== 'refresh_token') {
      throw new Error('OFFLINE_REQUEST_MISMATCH');
    }
    console.log('VK_REFRESH_OFFLINE=PASS;NETWORK=NONE;NO_SECRETS_USED');
    return;
  }
  if (mode !== 'live') throw new Error('UNKNOWN_MODE');
  requireLiveRunner();

  const refreshToken = requiredSecret('VK_REFRESH_TOKEN');
  const deviceId = requiredSecret('VK_DEVICE_ID');
  const pat = requiredSecret('VK_SECRETS_WRITE_PAT');
  const redirectUri = process.env.VK_REDIRECT_URI || DEFAULT_REDIRECT;

  verifyGithubSecretWrite(pat);
  const state = randomBytes(32).toString('base64url');
  const request = buildVkRefreshRequest({
    clientId: APP_ID, redirectUri, deviceId, refreshToken, state
  });
  let response;
  let payload;
  try {
    response = await fetch(request.url, request.options);
    payload = await response.json().catch(() => null);
  } catch {
    throw new Error('VK_REFRESH_NETWORK_ERROR');
  }
  if (!response.ok) throw new Error('VK_ID_REFRESH_HTTP_REJECTED');
  const refreshed = parseVkRefreshResponse(payload, state);
  console.log('VK_ID_REFRESH=ACCEPTED');

  // Rotate the stored secret immediately; do not use access token before this.
  try {
    storeRepoSecret('VK_REFRESH_TOKEN', refreshed.refreshToken, pat);
  } catch {
    console.log('VK_REFRESH_TOKEN_PERSIST=FAILED;MANUAL_REAUTH_MAY_BE_NEEDED');
    throw new Error('VK_REFRESH_SECRET_ROTATION_FAILED');
  }
  console.log('VK_REFRESH_TOKEN_PERSIST=OK');

  const result = await readOnlyVkTokenCheck(refreshed.accessToken, APP_ID);
  console.log('VK_ID_USER_INFO=' + result.vkId);
  console.log('VK_API_USERS_GET=' + result.vkApiUsers);
  console.log('VK_API_VIDEO_PERMISSION=' + result.legacyVideoPermission);
  console.log('VK_VIDEO_SAVE=NOT_CALLED');
  console.log('VK_UPLOAD=NOT_CALLED');
  console.log('VK_PUBLICATION=NOT_CALLED');

  if (!result.vkApiAllowed || result.vkId !== 'OK') {
    throw new Error('REFRESHED_TOKEN_NOT_COMPATIBLE_WITH_RUNNER_VK_API');
  }
  console.log('VK_GITHUB_SAME_RUNNER_ACCESS=PASS');
}

run().catch((error) => {
  const allowed = new Set([
    'UNAUTHORIZED_RUN_CONTEXT', 'UNKNOWN_MODE', 'OFFLINE_REQUEST_MISMATCH',
    'GITHUB_SECRET_OPERATION_FAILED', 'VK_REFRESH_NETWORK_ERROR',
    'VK_ID_REFRESH_HTTP_REJECTED', 'VK_ID_REFRESH_REJECTED',
    'REFRESH_STATE_MISMATCH', 'REFRESH_TOKEN_FIELDS_MISSING',
    'REFRESH_EXPIRY_INVALID', 'VK_REFRESH_SECRET_ROTATION_FAILED',
    'REFRESHED_TOKEN_NOT_COMPATIBLE_WITH_RUNNER_VK_API',
    'MISSING_VK_REFRESH_TOKEN', 'MISSING_VK_DEVICE_ID',
    'MISSING_VK_SECRETS_WRITE_PAT', 'BAD_REDIRECT_URI', 'BAD_CLIENT_ID',
    'MISSING_DEVICE_ID', 'MISSING_REFRESH_TOKEN', 'BAD_STATE'
  ]);
  const code = allowed.has(error?.message) ? error.message : 'UNCLASSIFIED_ERROR';
  console.error('VK_REFRESH_PROBE=' + code);
  process.exitCode = 1;
});
