import "dotenv/config";

function positiveInt(value) {
  const parsed = Number.parseInt(value ?? "", 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

export const config = Object.freeze({
  port: positiveInt(process.env.PORT) ?? 3000,
  nodeEnv: process.env.NODE_ENV ?? "development",
  internalApiKey: process.env.INTERNAL_API_KEY ?? "",
  vk: Object.freeze({
    appId: positiveInt(process.env.VK_APP_ID),
    redirectUri: process.env.VK_REDIRECT_URI ?? "https://vk.liniyasporta.ru/oauth/callback",
    apiVersion: process.env.VK_API_VERSION ?? "5.199",
    groupId: positiveInt(process.env.VK_GROUP_ID),
    userToken: process.env.VK_USER_TOKEN ?? "",
    groupToken: process.env.VK_GROUP_TOKEN ?? ""
  })
});

export function requireGatewayAuthConfig() {
  if (!config.internalApiKey || config.internalApiKey === "change-me") {
    throw new Error("INTERNAL_API_KEY is not configured");
  }
}

export function requireVkGroupId() {
  if (!config.vk.groupId) throw new Error("VK_GROUP_ID is not configured");
}

export function requireVkUserToken() {
  if (!config.vk.userToken) {
    throw new Error(
      "VK_USER_TOKEN is not configured. VK API 5.199 requires a user token for wall/photo/video publishing."
    );
  }
}

export function requireVkPublishingConfig() {
  requireVkGroupId();
  requireVkUserToken();
}

export function getReadToken() {
  return config.vk.userToken || config.vk.groupToken;
}
