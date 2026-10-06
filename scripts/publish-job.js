import fs from "node:fs/promises";
import path from "node:path";
import {
  checkStoryAccess,
  checkVkConnection,
  deleteStory,
  publishWallPost,
  uploadStory,
  uploadWallPhoto,
  uploadWallVideo
} from "../src/vk.js";

const jobPath = process.argv[2];

if (!jobPath) {
  console.error("Usage: node scripts/publish-job.js queue/<job>.json");
  process.exit(2);
}

const root = process.cwd();
const absoluteJobPath = path.resolve(root, jobPath);

function ensureInsideRoot(filePath) {
  const absolute = path.resolve(root, filePath);
  const relative = path.relative(root, absolute);
  if (relative.startsWith("..") || path.isAbsolute(relative)) {
    throw new Error(`Path escapes repository root: ${filePath}`);
  }
  return absolute;
}

function mimeFromPath(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  const map = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".m4v": "video/x-m4v",
    ".webm": "video/webm"
  };
  return map[ext] || "application/octet-stream";
}

async function asUploadFile(filePath) {
  const absolute = ensureInsideRoot(filePath);
  const stat = await fs.stat(absolute);
  if (!stat.isFile()) throw new Error(`Media path is not a file: ${filePath}`);

  return {
    path: absolute,
    originalname: path.basename(absolute),
    mimetype: mimeFromPath(absolute)
  };
}

async function downloadToTemp(url, filename) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Media download failed with HTTP ${response.status}`);
  }
  const buffer = Buffer.from(await response.arrayBuffer());
  const dir = path.join(root, ".tmp-media");
  await fs.mkdir(dir, { recursive: true });
  const safeName = String(filename || "media.bin").replace(/[^a-zA-Z0-9._-]/g, "_");
  const absolute = path.join(dir, safeName);
  await fs.writeFile(absolute, buffer);
  return {
    path: absolute,
    originalname: safeName,
    mimetype: response.headers.get("content-type") || mimeFromPath(safeName)
  };
}

async function mediaFile(job, fallbackName) {
  if (job.mediaUrl) {
    return downloadToTemp(job.mediaUrl, job.fileName || fallbackName);
  }
  if (!job.media) throw new Error("Job requires media or mediaUrl");
  return asUploadFile(job.media);
}

async function publish(job) {
  switch (job.type) {
    case "check":
      return checkVkConnection();

    case "check-story":
      return checkStoryAccess();

    case "delete-story":
      return deleteStory(job.storyId, job.ownerId);

    case "post":
      return publishWallPost({
        text: job.text || "",
        attachments: job.attachments || [],
        publishAt: job.publishAt
      });

    case "photo": {
      const media = Array.isArray(job.media) ? job.media : [job.media].filter(Boolean);
      if (media.length === 0) throw new Error("photo job requires media");

      const uploads = [];
      for (const mediaPath of media) {
        uploads.push(await uploadWallPhoto(await asUploadFile(mediaPath)));
      }

      const post = await publishWallPost({
        text: job.text || "",
        attachments: uploads.map((item) => item.attachment),
        publishAt: job.publishAt
      });

      return { uploads, post };
    }

    case "video": {
      const uploaded = await uploadWallVideo(
        await mediaFile(job, "video.mp4"),
        {
          name: job.name,
          description: job.description || ""
        }
      );

      const post = await publishWallPost({
        text: job.text || "",
        attachments: [uploaded.attachment],
        publishAt: job.publishAt
      });

      return { uploaded, post };
    }

    case "story": {
      const file = await mediaFile(
        job,
        job.storyType === "video" ? "story.mp4" : "story.png"
      );
      const storyType =
        job.storyType ||
        (file.mimetype.startsWith("video/") ? "video" : "photo");

      return uploadStory(file, {
        type: storyType,
        addToNews: job.addToNews !== false,
        linkText: job.linkText,
        linkUrl: job.linkUrl
      });
    }

    case "story-batch": {
      if (!Array.isArray(job.stories) || job.stories.length === 0) {
        throw new Error("story-batch requires a non-empty stories array");
      }

      const results = [];
      for (let i = 0; i < job.stories.length; i++) {
        const story = job.stories[i];
        const file = await mediaFile(
          story,
          story.storyType === "video" ? `story-${i + 1}.mp4` : `story-${i + 1}.png`
        );
        const storyType =
          story.storyType ||
          (file.mimetype.startsWith("video/") ? "video" : "photo");

        const result = await uploadStory(file, {
          type: storyType,
          addToNews: story.addToNews !== false,
          linkText: story.linkText,
          linkUrl: story.linkUrl
        });

        results.push({
          index: i + 1,
          storyType,
          result
        });

        if (i < job.stories.length - 1) {
          await new Promise((resolve) => setTimeout(resolve, 1500));
        }
      }

      return results;
    }

    default:
      throw new Error(
        'Unknown job type. Use "check", "check-story", "delete-story", "post", "photo", "video", "story" or "story-batch".'
      );
  }
}

let job;
let id;

try {
  job = JSON.parse(await fs.readFile(absoluteJobPath, "utf8"));
  id = String(job.id || path.basename(jobPath, path.extname(jobPath)))
    .replace(/[^a-zA-Z0-9._-]/g, "_");

  if (!id) throw new Error("Job id is empty");

  const result = await publish(job);
  const payload = {
    ok: true,
    id,
    type: job.type,
    finishedAt: new Date().toISOString(),
    result
  };

  await fs.mkdir(path.join(root, "results"), { recursive: true });
  await fs.writeFile(
    path.join(root, "results", `${id}.json`),
    JSON.stringify(payload, null, 2) + "\n"
  );

  console.log(JSON.stringify(payload));
} catch (error) {
  id =
    id ||
    path.basename(jobPath, path.extname(jobPath)).replace(/[^a-zA-Z0-9._-]/g, "_") ||
    "unknown";

  const payload = {
    ok: false,
    id,
    type: job?.type ?? null,
    finishedAt: new Date().toISOString(),
    error: error?.message ?? String(error),
    code: error?.code ?? null
  };

  await fs.mkdir(path.join(root, "results"), { recursive: true });
  await fs.writeFile(
    path.join(root, "results", `${id}.json`),
    JSON.stringify(payload, null, 2) + "\n"
  );

  console.error(JSON.stringify(payload));
  process.exitCode = 1;
}
