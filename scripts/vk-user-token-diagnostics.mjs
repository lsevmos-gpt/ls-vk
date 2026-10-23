// Read-only VK ID vs legacy VK API diagnostic. Never log secrets or profile data.
import { vkCall } from "../src/vk.js";

const token = (process.env.VK_USER_TOKEN || "").trim();
if (!token) {
  console.error("VK_USER_TOKEN=MISSING");
  process.exit(2);
}

const appId = "54806879";
const kind = token.startsWith("vk2.a.") ? "vk2" :
  token.startsWith("vk1.a.") ? "vk1" : "other";
console.log("VK_USER_TOKEN=PRESENT");
console.log("VK_USER_TOKEN_FAMILY=" + kind);

function errorClass(message) {
  const text = String(message || "");
  if (/another ip address|different ip|ip mismatch|другого ip/i.test(text)) return "IP_MISMATCH";
  if (/expired|has expired|истек/i.test(text)) return "EXPIRED";
  if (/invalid access.token|недействительн.*токен/i.test(text)) return "INVALID_TOKEN";
  if (/no access.token|missing access.token/i.test(text)) return "NO_TOKEN";
  if (/permission|not allowed|недостаточно прав/i.test(text)) return "NOT_PERMITTED";
  return "OTHER";
}
function vkApiFailure(err) {
  const raw = err?.vkError || {};
  const code = Number.isInteger(raw.error_code) ? raw.error_code : "UNKNOWN";
  const subcode = Number.isInteger(raw.error_subcode) ? raw.error_subcode : "NONE";
  return `API_ERROR_${code};SUBCODE=${subcode};REASON=${errorClass(raw.error_msg || err?.message)}`;
}
function jsonFailure(payload, httpStatus) {
  const code = typeof payload?.error === "string" ? payload.error :
    payload?.error?.error || payload?.error_code || "OTHER";
  // Do not print remote-supplied strings, personal information, URL or tokens.
  const allowed = new Set(["invalid_token", "invalid_request", "access_denied", "unauthorized_client", "OTHER"]);
  const safeCode = allowed.has(String(code)) ? String(code) : "OTHER";
  return `ERROR_${safeCode};HTTP=${Number(httpStatus) || "UNKNOWN"}`;
}

try {
  // Same endpoint as the official VKCOM/vkid-web-sdk Auth.userInfo method.
  const body = new URLSearchParams({ access_token: token });
  const response = await fetch(`https://id.vk.ru/oauth2/user_info?client_id=${appId}`, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body,
    signal: AbortSignal.timeout(15000)
  });
  const data = await response.json().catch(() => null);
  const ok = response.ok && !!data && !data.error &&
    Boolean(data.user?.user_id || data.user_id || data.user?.id);
  console.log("VK_ID_USER_INFO=" + (ok ? "OK" : jsonFailure(data, response.status)));
} catch {
  console.log("VK_ID_USER_INFO=TRANSPORT_ERROR");
}

let legacyUser = false;
try {
  const result = await vkCall("users.get", {}, token);
  legacyUser = Array.isArray(result) && result.length > 0;
  console.log("VK_API_USERS_GET_FORM=" + (legacyUser ? "OK" : "UNEXPECTED_RESPONSE"));
} catch (error) {
  console.log("VK_API_USERS_GET_FORM=" + vkApiFailure(error));
}
try {
  const response = await fetch("https://api.vk.ru/method/users.get", {
    method: "POST",
    headers: {
      authorization: `Bearer ${token}`,
      "content-type": "application/x-www-form-urlencoded"
    },
    body: new URLSearchParams({v:"5.199"}),
    signal: AbortSignal.timeout(15000)
  });
  const result = await response.json().catch(() => null);
  if (Array.isArray(result?.response) && result.response.length > 0) {
    console.log("VK_API_USERS_GET_BEARER=OK");
    legacyUser = true;
  } else {
    console.log("VK_API_USERS_GET_BEARER=" + vkApiFailure({vkError: result?.error}));
  }
} catch {
  console.log("VK_API_USERS_GET_BEARER=TRANSPORT_ERROR");
}
try {
  const mask = Number(await vkCall("account.getAppPermissions", {}, token));
  if (Number.isSafeInteger(mask) && mask >= 0) {
    console.log("VK_LEGACY_VIDEO_PERMISSION=" + ((mask & 16) !== 0 ? "YES" : "NO"));
  } else {
    console.log("VK_LEGACY_VIDEO_PERMISSION=UNKNOWN_FORMAT");
  }
} catch (error) {
  console.log("VK_LEGACY_VIDEO_PERMISSION=" + vkApiFailure(error));
}
console.log("VK_VIDEO_SAVE=NOT_CALLED_READ_ONLY");
console.log("VK_CLIP_UPLOAD=NOT_VERIFIED");
if (!legacyUser) process.exitCode = 1;
