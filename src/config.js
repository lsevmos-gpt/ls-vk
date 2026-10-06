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

export function requireVkConfig({ media = false } = {}) {
  if (!config.vk.groupId) throw new Error("VK_GROUP_ID is not configured");
  if (!config.vk.groupToken) throw new Error("VK_GROUP_TOKEN is not configured");

  if (media && !config.vk.userToken && !config.vk.groupToken) {
    throw new Error("No VK token is configured for media upload");
  }
}

export function getMediaToken() {
  requireVkConfig({ media: true });
  return config.vk.userToken || config.vk.groupToken;
}
