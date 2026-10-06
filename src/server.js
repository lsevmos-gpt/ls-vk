import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import crypto from "node:crypto";
import express from "express";
import multer from "multer";
import {
  checkVkConnection,
  publishWallPost,
  uploadWallPhoto,
  uploadWallVideo,
  uploadStory
} from "./vk.js";
import { config, requireGatewayAuthConfig } from "./config.js";

const app = express();
const uploadDir = path.join(os.tmpdir(), "ls-vk-uploads");
await fs.mkdir(uploadDir, { recursive: true });

const upload = multer({
  dest: uploadDir,
  limits: {
    fileSize: 1024 * 1024 * 1024
  }
});

app.use(express.json({ limit: "2mb" }));

function timingSafeEqualText(a, b) {
  const left = Buffer.from(String(a ?? ""));
  const right = Buffer.from(String(b ?? ""));
  if (left.length !== right.length) return false;
  return crypto.timingSafeEqual(left, right);
}

function requireInternalAuth(req, res, next) {
  try {
    requireGatewayAuthConfig();
  } catch (error) {
    return res.status(500).json({ ok: false, error: error.message });
  }

  const header = req.get("authorization") ?? "";
  const token = header.startsWith("Bearer ") ? header.slice(7) : "";

  if (!timingSafeEqualText(token, config.internalApiKey)) {
    return res.status(401).json({ ok: false, error: "Unauthorized" });
  }

  next();
}

async function withUploadedFile(req, res, handler) {
  if (!req.file) {
    return res.status(400).json({ ok: false, error: "File is required" });
  }

  try {
    const result = await handler(req.file);
    res.json({ ok: true, result });
  } catch (error) {
    res.status(400).json({
      ok: false,
      error: error.message,
      code: error.code ?? null
    });
  } finally {
    await fs.unlink(req.file.path).catch(() => {});
  }
}

app.get("/health", (_req, res) => {
  res.json({
    ok: true,
    service: "ls-vk",
    vkConfigured: Boolean(config.vk.groupId && config.vk.groupToken),
    mediaUserTokenConfigured: Boolean(config.vk.userToken)
  });
});

app.use("/api", requireInternalAuth);

app.get("/api/vk/check", async (_req, res) => {
  try {
    const result = await checkVkConnection();
    res.json({ ok: true, result });
  } catch (error) {
    res.status(400).json({
      ok: false,
      error: error.message,
      code: error.code ?? null
    });
  }
});

app.post("/api/vk/post", async (req, res) => {
  try {
    const result = await publishWallPost({
      text: req.body?.text ?? "",
      attachments: req.body?.attachments ?? [],
      publishAt: req.body?.publishAt
    });
    res.json({ ok: true, result });
  } catch (error) {
    res.status(400).json({
      ok: false,
      error: error.message,
      code: error.code ?? null
    });
  }
});

app.post("/api/vk/photo", upload.single("file"), async (req, res) => {
  await withUploadedFile(req, res, async (file) => {
    const uploaded = await uploadWallPhoto(file);

    if (String(req.body?.publish ?? "false") === "true") {
      const post = await publishWallPost({
        text: req.body?.text ?? "",
        attachments: [uploaded.attachment],
        publishAt: req.body?.publishAt
      });
      return { uploaded, post };
    }

    return uploaded;
  });
});

app.post("/api/vk/video", upload.single("file"), async (req, res) => {
  await withUploadedFile(req, res, async (file) => {
    const uploaded = await uploadWallVideo(file, {
      name: req.body?.name,
      description: req.body?.description ?? ""
    });

    if (String(req.body?.publish ?? "false") === "true") {
      const post = await publishWallPost({
        text: req.body?.text ?? "",
        attachments: [uploaded.attachment],
        publishAt: req.body?.publishAt
      });
      return { uploaded, post };
    }

    return uploaded;
  });
});

app.post("/api/vk/story", upload.single("file"), async (req, res) => {
  await withUploadedFile(req, res, async (file) => {
    const type = req.body?.type || (file.mimetype?.startsWith("video/") ? "video" : "photo");
    return uploadStory(file, {
      type,
      addToNews: String(req.body?.addToNews ?? "true") !== "false",
      linkText: req.body?.linkText,
      linkUrl: req.body?.linkUrl
    });
  });
});

app.use((error, _req, res, _next) => {
  res.status(500).json({
    ok: false,
    error: error?.message ?? "Internal server error"
  });
});

app.listen(config.port, () => {
  console.log(`ls-vk listening on port ${config.port}`);
});
