// Read-only VK user-token diagnostics. Never print tokens or invoke video.save.
import { vkCall } from "../src/vk.js";

const token = (process.env.VK_USER_TOKEN || "").trim();
if (!token) {
  console.error("VK_USER_TOKEN=MISSING; add the newly authorized token as a GitHub Actions secret.");
  process.exit(2);
}

const tokenKind = token.startsWith("vk2.a.") ? "vk2" :
  token.startsWith("vk1.a.") ? "vk1" : "other";
console.log("VK_USER_TOKEN=PRESENT");
console.log("VK_USER_TOKEN_FAMILY=" + tokenKind);

let canReadUser = false;
try {
  const response = await vkCall("users.get", {}, token);
  canReadUser = Array.isArray(response) && response.length > 0;
  console.log("VK_USERS_GET=" + (canReadUser ? "OK" : "UNEXPECTED_RESPONSE"));
} catch (error) {
  const code = Number.isInteger(error?.code) ? error.code : "UNKNOWN";
  console.log("VK_USERS_GET=API_ERROR_" + code);
}

try {
  const response = await vkCall("account.getAppPermissions", {}, token);
  const mask = Number(response);
  if (Number.isSafeInteger(mask) && mask >= 0) {
    // Historical VK API user-permission bitmask. This is NOT proof that video.save is available.
    console.log("VK_LEGACY_APP_PERMISSIONS=AVAILABLE");
    console.log("VK_LEGACY_VIDEO_PERMISSION=" + ((mask & 16) !== 0 ? "YES" : "NO"));
  } else {
    console.log("VK_LEGACY_APP_PERMISSIONS=UNKNOWN_FORMAT");
  }
} catch (error) {
  const code = Number.isInteger(error?.code) ? error.code : "UNKNOWN";
  console.log("VK_LEGACY_APP_PERMISSIONS=API_ERROR_" + code);
}

console.log("VK_VIDEO_SAVE=NOT_CALLED_READ_ONLY");
console.log("VK_CLIP_UPLOAD=NOT_YET_VERIFIED");
if (!canReadUser) process.exitCode = 1;
