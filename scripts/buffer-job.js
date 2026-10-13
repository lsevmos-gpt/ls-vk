import fs from "node:fs/promises";
import path from "node:path";
import {
  checkBufferConnection,
  createInstagramPost,
  discoverChannel
} from "../src/buffer.js";

const jobPath = process.argv[2];
if (!jobPath) {
  console.error("Usage: node scripts/buffer-job.js buffer-queue/<job>.json");
  process.exit(2);
}

const root = process.cwd();
const absoluteJobPath = path.resolve(root, jobPath);

function safeId(value) {
  return String(value || "")
    .replace(/[^a-zA-Z0-9._-]/g, "_")
    .slice(0, 180);
}

async function publish(job) {
  switch (job.type) {
    case "check-buffer":
      return checkBufferConnection();

    case "instagram": {
      const resolved =
        job.channelId
          ? { channel: { id: job.channelId } }
          : await discoverChannel({
              service: "instagram",
              handle: job.handle || "liniya__sporta",
              organizationId: job.organizationId
            });

      const post = await createInstagramPost({
        channelId: resolved.channel.id,
        text: job.text || "",
        postType: job.postType || "post",
        media: job.media || [],
        dueAt: job.dueAt,
        publishNow: job.publishNow === true,
        shouldShareToFeed: job.shouldShareToFeed,
        isAiGenerated: job.isAiGenerated === true
      });

      return {
        channel: resolved.channel,
        organization: resolved.organization || null,
        post
      };
    }

    default:
      throw new Error('Unknown Buffer job type. Use "check-buffer" or "instagram".');
  }
}

let job;
let id;

try {
  job = JSON.parse(await fs.readFile(absoluteJobPath, "utf8"));
  id = safeId(job.id || path.basename(jobPath, path.extname(jobPath)));
  if (!id) throw new Error("Job id is empty");

  const result = await publish(job);
  const payload = {
    ok: true,
    id,
    type: job.type,
    finishedAt: new Date().toISOString(),
    result
  };

  await fs.mkdir(path.join(root, "buffer-results"), { recursive: true });
  await fs.writeFile(
    path.join(root, "buffer-results", `${id}.json`),
    JSON.stringify(payload, null, 2) + "\n"
  );

  console.log(JSON.stringify(payload));
} catch (error) {
  id = id || safeId(path.basename(jobPath, path.extname(jobPath))) || "unknown";

  const payload = {
    ok: false,
    id,
    type: job?.type ?? null,
    finishedAt: new Date().toISOString(),
    error: error?.message ?? String(error)
  };

  await fs.mkdir(path.join(root, "buffer-results"), { recursive: true });
  await fs.writeFile(
    path.join(root, "buffer-results", `${id}.json`),
    JSON.stringify(payload, null, 2) + "\n"
  );

  console.error(JSON.stringify(payload));
  process.exitCode = 1;
}
