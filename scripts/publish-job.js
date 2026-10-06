import fs from "node:fs/promises";
import path from "node:path";
import {
  checkVkConnection,
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

async function publish(job) {
  switch (job.type) {
    case "check":
      return checkVkConnection();

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
      if (!job.media) throw new Error("video job requires media");
      const uploaded = await uploadWallVideo(
        await asUploadFile(job.media),
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
      if (!job.media) throw new Error("story job requires media");
      const file = await asUploadFile(job.media);
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

    default:
      throw new Error(
        'Unknown job type. Use "check", "post", "photo", "video" or "story".'
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
