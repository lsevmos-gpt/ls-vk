import test from 'node:test';
import assert from 'node:assert/strict';
import {
  VK_ID_REFRESH_URL,
  buildVkRefreshRequest,
  parseVkRefreshResponse,
  readOnlyVkTokenCheck,
  vkApiStatus
} from '../scripts/vk-refresh-lib.mjs';

const params = {
  clientId: '54806879',
  redirectUri: 'https://vk.liniyasporta.ru/oauth/callback',
  deviceId: 'example-device',
  refreshToken: 'mock-refresh-token-not-real',
  state: 'random-test-state'
};

test('refresh request matches VK ID SDK contract and keeps refresh token out of URL', () => {
  const req = buildVkRefreshRequest(params);
  assert.equal(new URL(req.url).origin, new URL(VK_ID_REFRESH_URL).origin);
  const query = new URL(req.url).searchParams;
  assert.deepEqual([...query.keys()].sort(), [
    'client_id', 'device_id', 'grant_type', 'redirect_uri', 'state'
  ].sort());
  assert.equal(query.get('grant_type'), 'refresh_token');
  assert.equal(query.get('client_id'), params.clientId);
  assert.equal(query.get('device_id'), params.deviceId);
  assert.equal(query.get('redirect_uri'), params.redirectUri);
  assert.equal(query.get('state'), params.state);
  assert.equal(req.options.method, 'POST');
  assert.equal(req.options.body.get('refresh_token'), params.refreshToken);
  assert.deepEqual([...req.options.body.keys()], ['refresh_token']);
  assert.ok(!req.url.includes(params.refreshToken));
});

test('missing inputs are blocked before a network call', () => {
  assert.throws(() => buildVkRefreshRequest({ ...params, deviceId: '' }), /MISSING_DEVICE_ID/);
  assert.throws(() => buildVkRefreshRequest({ ...params, refreshToken: '' }), /MISSING_REFRESH_TOKEN/);
  assert.throws(() => buildVkRefreshRequest({ ...params, redirectUri: 'http://bad.example' }), /BAD_REDIRECT_URI/);
});

test('refresh response is parsed without exposing secrets', () => {
  const got = parseVkRefreshResponse({
    state: params.state, access_token: 'mock-access-token',
    refresh_token: 'new-mock-refresh', expires_in: 3600
  }, params.state);
  assert.equal(got.accessToken, 'mock-access-token');
  assert.equal(got.refreshToken, 'new-mock-refresh');
});

test('refresh fails closed for mismatch, rotation failure or provider error', () => {
  const good = {
    state: params.state, access_token: 'mock-access-token',
    refresh_token: 'new-mock-refresh', expires_in: 3600
  };
  assert.throws(() => parseVkRefreshResponse({ ...good, state: 'bad' }, params.state), /REFRESH_STATE_MISMATCH/);
  assert.throws(() => parseVkRefreshResponse({ ...good, refresh_token: undefined }, params.state), /REFRESH_TOKEN_FIELDS_MISSING/);
  assert.throws(() => parseVkRefreshResponse({
    error: 'invalid_grant', error_description: 'secret value from malicious server'
  }, params.state), /VK_ID_REFRESH_REJECTED/);
});

test('successful read-only VK ID and classic VK API checks never call video.save', async () => {
  const called = [];
  const fakeFetch = async (url) => {
    called.push(url);
    if (url.includes('oauth2/user_info')) return { ok: true, json: async () => ({ user: { user_id: '1' } }) };
    if (url.endsWith('users.get')) return { ok: true, json: async () => ({ response: [{ id: 1 }] }) };
    if (url.endsWith('account.getAppPermissions')) return { ok: true, json: async () => ({ response: 16 }) };
    throw new Error('Unexpected route');
  };
  const result = await readOnlyVkTokenCheck('mock-access', params.clientId, fakeFetch);
  assert.equal(result.vkId, 'OK');
  assert.equal(result.vkApiUsers, 'OK');
  assert.equal(result.legacyVideoPermission, 'YES');
  assert.equal(result.vkApiAllowed, true);
  assert.equal(called.length, 3);
  assert.ok(called.every(x => !/video\.save|wall\.post|upload/i.test(x)));
});

test('VK API IP mismatch code 1130 is reported without raw provider text', async () => {
  const fakeFetch = async url => {
    if (url.includes('oauth2/user_info')) return { ok: true, json: async () => ({ user: { user_id: '1' } }) };
    return { ok: true, json: async () => ({
      error: { error_code: 5, error_subcode: 1130, error_msg: 'another ip address - MUST NOT LEAK' }
    }) };
  };
  const result = await readOnlyVkTokenCheck('mock-access', params.clientId, fakeFetch);
  assert.equal(result.vkApiUsers, 'API_ERROR_5;SUBCODE=1130');
  assert.equal(result.legacyVideoPermission, 'API_ERROR_5;SUBCODE=1130');
  assert.equal(result.vkApiAllowed, false);
  assert.ok(!JSON.stringify(result).includes('MUST NOT LEAK'));
  assert.equal(vkApiStatus({ error: { error_code: 5, error_subcode: 1130, error_msg: 'secret' } }),
    'API_ERROR_5;SUBCODE=1130');
});
