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
    groupToken: process.env.VK_GROUP_TOKEN ?? "",
    userToken: process.env.VK_USER_TOKEN ?? ""
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

export function requireVkWallToken() {
  if (!config.vk.groupToken && !config.vk.userToken) {
    throw new Error("VK_GROUP_TOKEN (preferred) or VK_USER_TOKEN is not configured");
  }
}

export function getWallToken() {
  requireVkWallToken();
  return config.vk.groupToken || config.vk.userToken;
}

export function getReadToken() {
  return config.vk.groupToken || config.vk.userToken;
}

export function getMediaToken() {
  if (config.vk.userToken) return config.vk.userToken;
  if (config.vk.groupToken) return config.vk.groupToken;
  throw new Error("No VK token is configured");
}
