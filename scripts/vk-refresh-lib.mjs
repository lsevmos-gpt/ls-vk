// VK ID OAuth2.1 refresh helpers. Pure functions and read-only API checks.
// NO video.save, upload, post, token logging or raw provider error output.
export const VK_ID_REFRESH_URL = 'https://id.vk.ru/oauth2/auth';
export const VK_ID_USER_INFO_URL = 'https://id.vk.ru/oauth2/user_info';

function nonempty(value) {
  return typeof value === 'string' && value.trim().length > 0 && value.length <= 8192;
}

export function buildVkRefreshRequest({ clientId, redirectUri, deviceId, refreshToken, state }) {
  if (!/^[0-9]+$/.test(String(clientId || ''))) throw new Error('BAD_CLIENT_ID');
  if (!nonempty(redirectUri) || !redirectUri.startsWith('https://')) {
    throw new Error('BAD_REDIRECT_URI');
  }
  if (!nonempty(deviceId)) throw new Error('MISSING_DEVICE_ID');
  if (!nonempty(refreshToken)) throw new Error('MISSING_REFRESH_TOKEN');
  if (!nonempty(state) || state.length > 200) throw new Error('BAD_STATE');

  // Match VKCOM/vkid-web-sdk Auth.refreshToken(): params in URL, token in POST body.
  const url = new URL(VK_ID_REFRESH_URL);
  url.search = new URLSearchParams({
    grant_type: 'refresh_token',
    redirect_uri: redirectUri,
    client_id: String(clientId),
    device_id: deviceId,
    state
  }).toString();
  return {
    url: url.toString(),
    options: {
      method: 'POST',
      headers: { 'content-type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ refresh_token: refreshToken }),
      signal: AbortSignal.timeout(20000)
    }
  };
}

export function parseVkRefreshResponse(payload, expectedState) {
  // Deliberately ignore error_description and full response to avoid leaking tokens.
  if (!payload || typeof payload !== 'object' || payload.error) {
    throw new Error('VK_ID_REFRESH_REJECTED');
  }
  if (payload.state !== expectedState) throw new Error('REFRESH_STATE_MISMATCH');
  if (!nonempty(payload.access_token) || !nonempty(payload.refresh_token)) {
    throw new Error('REFRESH_TOKEN_FIELDS_MISSING');
  }
  if (!Number.isSafeInteger(Number(payload.expires_in)) || Number(payload.expires_in) <= 0) {
    throw new Error('REFRESH_EXPIRY_INVALID');
  }
  return { accessToken: payload.access_token, refreshToken: payload.refresh_token };
}

export function vkApiStatus(payload) {
  if (payload && payload.error) {
    const e = payload.error;
    const code = Number.isSafeInteger(e.error_code) ? e.error_code : 'UNKNOWN';
    const subcode = Number.isSafeInteger(e.error_subcode) ? e.error_subcode : 'NONE';
    return 'API_ERROR_' + code + ';SUBCODE=' + subcode;
  }
  return 'NO_API_RESPONSE';
}

async function postForm(url, body, fetchFn) {
  try {
    const response = await fetchFn(url, {
      method: 'POST',
      headers: { 'content-type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams(body),
      signal: AbortSignal.timeout(15000)
    });
    const json = await response.json().catch(() => null);
    if (!response.ok && !json?.error) {
      return { error: { error_code: Number(response.status) || 0 } };
    }
    return json;
  } catch {
    return { error: { error_code: 0 } };
  }
}

export async function readOnlyVkTokenCheck(accessToken, clientId, fetchFn = fetch) {
  if (!nonempty(accessToken)) throw new Error('ACCESS_TOKEN_MISSING');
  const info = await postForm(
    VK_ID_USER_INFO_URL + '?client_id=' + encodeURIComponent(String(clientId)),
    { access_token: accessToken },
    fetchFn
  );
  const identityOk = Boolean(info?.user?.user_id || info?.user_id || info?.user?.id) && !info?.error;
  const user = await postForm('https://api.vk.ru/method/users.get', {
    access_token: accessToken, v: '5.199'
  }, fetchFn);
  const userOk = Array.isArray(user?.response) && user.response.length > 0;
  const permissions = await postForm('https://api.vk.ru/method/account.getAppPermissions', {
    access_token: accessToken, v: '5.199'
  }, fetchFn);
  const mask = Number(permissions?.response);
  const maskValid = permissions?.response !== undefined &&
    Number.isSafeInteger(mask) && mask >= 0;
  return {
    vkId: identityOk ? 'OK' : (info?.error ? vkApiStatus(info) : 'UNEXPECTED_RESPONSE'),
    vkApiUsers: userOk ? 'OK' : vkApiStatus(user),
    legacyVideoPermission: maskValid ? ((mask & 16) ? 'YES' : 'NO') : vkApiStatus(permissions),
    vkApiAllowed: userOk && maskValid && (mask & 16) !== 0
  };
}
