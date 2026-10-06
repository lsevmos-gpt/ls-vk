import fs from "node:fs";
import FormData from "form-data";
import {
  config,
  getMediaToken,
  getReadToken,
  getWallToken,
  requireVkWallToken
} from "./config.js";

const VK_API_BASE = "https://api.vk.ru/method";
let resolvedGroupId = config.vk.groupId || null;

export class VkApiError extends Error {
  constructor(method, vkError) {
    super(`VK API ${method}: ${vkError?.error_msg ?? "unknown error"}`);
    this.name = "VkApiError";
    this.method = method;
    this.code = vkError?.error_code ?? null;
    this.vkError = vkError ?? null;
  }
}

function encodeValue(value) {
  if (Array.isArray(value)) return value.join(",");
  if (typeof value === "boolean") return value ? "1" : "0";
  if (value && typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export async function vkCall(method, params = {}, token) {
  const effectiveToken = token || getReadToken();
  if (!effectiveToken) throw new Error(`No token configured for VK method ${method}`);

  const body = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    body.set(key, encodeValue(value));
  }
  body.set("access_token", effectiveToken);
  body.set("v", config.vk.apiVersion);

  const response = await fetch(`${VK_API_BASE}/${method}`, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body
  });

  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(`VK HTTP ${response.status} calling ${method}`);
  }
  if (!payload) throw new Error(`Invalid VK response calling ${method}`);
  if (payload.error) throw new VkApiError(method, payload.error);

  return payload.response;
}

export async function getGroupId() {
  if (resolvedGroupId) return resolvedGroupId;

  if (!config.vk.groupScreenName) {
    throw new Error("VK_GROUP_ID or VK_GROUP_SCREEN_NAME is required");
  }

  const token = getReadToken();
  if (!token) throw new Error("VK_GROUP_TOKEN or VK_USER_TOKEN is not configured");

  const resolved = await vkCall(
    "utils.resolveScreenName",
    { screen_name: config.vk.groupScreenName },
    token
  );

  const id = Number.parseInt(resolved?.object_id, 10);
  if (!Number.isFinite(id) || id <= 0) {
    throw new Error(
      `Could not resolve VK community screen name: ${config.vk.groupScreenName}`
    );
  }

  const allowedTypes = new Set(["group", "page", "event"]);
  if (resolved?.type && !allowedTypes.has(resolved.type)) {
    throw new Error(
      `VK screen name ${config.vk.groupScreenName} resolves to ${resolved.type}, not a community`
    );
  }

  resolvedGroupId = id;
  return resolvedGroupId;
}

async function uploadMultipart(uploadUrl, fieldName, filePath, originalName, mimeType) {
  const form = new FormData();
  form.append(fieldName, fs.createReadStream(filePath), {
    filename: originalName || "upload.bin",
    contentType: mimeType || "application/octet-stream"
  });

  const response = await fetch(uploadUrl, {
    method: "POST",
    headers: form.getHeaders(),
    body: form,
    duplex: "half"
  });

  const text = await response.text();
  let payload;
  try {
    payload = JSON.parse(text);
  } catch {
    throw new Error(`VK upload returned non-JSON response (HTTP ${response.status})`);
  }

  if (!response.ok) {
    throw new Error(`VK upload failed with HTTP ${response.status}`);
  }
  if (payload?.error) {
    throw new Error(`VK upload error: ${payload.error.error_msg ?? payload.error.type ?? "unknown"}`);
  }

  return payload;
}

function toUnixTime(value) {
  if (value === undefined || value === null || value === "") return undefined;
  if (typeof value === "number" && Number.isFinite(value)) return Math.floor(value);
  const ms = Date.parse(value);
  if (!Number.isFinite(ms)) throw new Error("publishAt must be an ISO date/time or Unix timestamp");
  return Math.floor(ms / 1000);
}

export async function checkVkConnection() {
  requireVkWallToken();
  const token = getReadToken();
  const groupId = await getGroupId();

  const group = await vkCall(
    "groups.getById",
    { group_id: groupId },
    token
  );

  let user = null;
  let appPermissions = null;

  if (config.vk.userToken) {
    user = await vkCall("users.get", {}, config.vk.userToken);
    appPermissions = await vkCall(
      "account.getAppPermissions",
      {},
      config.vk.userToken
    );
  }

  return {
    groupId,
    groupScreenName: config.vk.groupScreenName,
    group,
    user,
    appPermissions,
    groupTokenConfigured: Boolean(config.vk.groupToken),
    userTokenConfigured: Boolean(config.vk.userToken)
  };
}

export async function publishWallPost({ text = "", attachments = [], publishAt } = {}) {
  requireVkWallToken();
  const groupId = await getGroupId();

  if (!text && (!attachments || attachments.length === 0)) {
    throw new Error("A wall post needs text and/or attachments");
  }

  return vkCall(
    "wall.post",
    {
      owner_id: -groupId,
      from_group: true,
      message: text,
      attachments,
      publish_date: toUnixTime(publishAt)
    },
    getWallToken()
  );
}

export async function uploadWallPhoto(file) {
  const groupId = await getGroupId();
  const token = getMediaToken();

  let uploadServer;
  try {
    uploadServer = await vkCall(
      "photos.getWallUploadServer",
      { group_id: groupId },
      token
    );
  } catch (error) {
    if (error instanceof VkApiError && error.code === 27 && !config.vk.userToken) {
      throw new Error(
        "VK community token can publish wall posts, but VK rejected community authorization for wall photo upload (error 27). A compatible user API token is required for photo upload."
      );
    }
    throw error;
  }

  const uploaded = await uploadMultipart(
    uploadServer.upload_url,
    "photo",
    file.path,
    file.originalname,
    file.mimetype
  );

  const saved = await vkCall(
    "photos.saveWallPhoto",
    {
      group_id: groupId,
      server: uploaded.server,
      photo: uploaded.photo,
      hash: uploaded.hash
    },
    token
  );

  const photo = Array.isArray(saved) ? saved[0] : saved;
  if (!photo?.owner_id || !photo?.id) throw new Error("VK did not return a saved photo ID");

  return {
    attachment: `photo${photo.owner_id}_${photo.id}`,
    photo
  };
}

export async function uploadWallVideo(file, { name, description = "" } = {}) {
  const groupId = await getGroupId();

  if (!config.vk.userToken) {
    throw new Error(
      "VK video.save requires a compatible user API token. A community token is not sufficient."
    );
  }

  const prepared = await vkCall(
    "video.save",
    {
      group_id: groupId,
      name: name || file.originalname || "Видео",
      description,
      wallpost: false
    },
    config.vk.userToken
  );

  if (!prepared?.upload_url) throw new Error("VK did not return a video upload URL");

  const uploaded = await uploadMultipart(
    prepared.upload_url,
    "video_file",
    file.path,
    file.originalname,
    file.mimetype
  );

  const ownerId = uploaded?.owner_id ?? prepared?.owner_id;
  const videoId = uploaded?.video_id ?? prepared?.video_id;
  if (!ownerId || !videoId) throw new Error("VK did not return a saved video ID");

  return {
    attachment: `video${ownerId}_${videoId}`,
    video: { owner_id: ownerId, id: videoId },
    upload: uploaded
  };
}

export async function uploadStory(file, {
  type,
  addToNews = true,
  linkText,
  linkUrl,
  clickableStickers
} = {}) {
  const groupId = await getGroupId();
  requireVkWallToken();

  if (type !== "photo" && type !== "video") {
    throw new Error('Story type must be "photo" or "video"');
  }

  const method = type === "photo"
    ? "stories.getPhotoUploadServer"
    : "stories.getVideoUploadServer";

  const token = getWallToken();
  const uploadServer = await vkCall(
    method,
    {
      add_to_news: addToNews,
      group_id: groupId,
      link_text: linkText,
      link_url: linkUrl,
      clickable_stickers: clickableStickers
    },
    token
  );

  if (!uploadServer?.upload_url) throw new Error("VK did not return a story upload URL");

  const uploaded = await uploadMultipart(
    uploadServer.upload_url,
    "file",
    file.path,
    file.originalname,
    file.mimetype
  );

  const uploadResult =
    uploaded?.response?.upload_result ??
    uploaded?.response?.upload_results ??
    uploaded?.upload_result ??
    uploaded?.upload_results;

  if (!uploadResult) {
    throw new Error("VK story upload did not return upload_result");
  }

  return vkCall(
    "stories.save",
    {
      upload_results: Array.isArray(uploadResult) ? uploadResult : [uploadResult]
    },
    token
  );
}
