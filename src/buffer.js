const API_URL = "https://api.buffer.com";

function requireApiKey() {
  const key = process.env.BUFFER_API_KEY;
  if (!key) throw new Error("BUFFER_API_KEY is not configured");
  return key;
}

async function graphql(query, variables = {}) {
  const response = await fetch(API_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${requireApiKey()}`
    },
    body: JSON.stringify({ query, variables })
  });

  const text = await response.text();
  let body;
  try {
    body = JSON.parse(text);
  } catch {
    throw new Error(`Buffer API returned non-JSON response (HTTP ${response.status}): ${text.slice(0, 500)}`);
  }

  if (!response.ok) {
    throw new Error(`Buffer API HTTP ${response.status}: ${JSON.stringify(body)}`);
  }

  if (Array.isArray(body.errors) && body.errors.length) {
    const message = body.errors.map((item) => item?.message || JSON.stringify(item)).join("; ");
    throw new Error(`Buffer GraphQL error: ${message}`);
  }

  return body.data;
}

export async function getOrganizations() {
  const data = await graphql(`
    query GetOrganizations {
      account {
        id
        email
        name
        timezone
        organizations {
          id
          name
          ownerEmail
          channelCount
        }
      }
    }
  `);
  return data.account;
}

export async function getChannels(organizationId) {
  const data = await graphql(
    `
      query GetChannels($organizationId: OrganizationId!) {
        channels(input: { organizationId: $organizationId }) {
          id
          name
          displayName
          service
          avatar
          isQueuePaused
        }
      }
    `,
    { organizationId }
  );
  return data.channels;
}

export async function checkBufferConnection() {
  const account = await getOrganizations();
  const organizations = [];

  for (const organization of account.organizations || []) {
    const channels = await getChannels(organization.id);
    organizations.push({ ...organization, channels });
  }

  return {
    account: {
      id: account.id,
      email: account.email,
      name: account.name,
      timezone: account.timezone
    },
    organizations
  };
}

export async function discoverChannel({
  service = "instagram",
  handle,
  organizationId
} = {}) {
  const account = await getOrganizations();
  const organizations = organizationId
    ? (account.organizations || []).filter((item) => item.id === organizationId)
    : account.organizations || [];

  const normalizedHandle = handle
    ? String(handle).replace(/^@/, "").trim().toLowerCase()
    : null;

  const candidates = [];

  for (const organization of organizations) {
    const channels = await getChannels(organization.id);
    for (const channel of channels) {
      if (String(channel.service).toLowerCase() !== String(service).toLowerCase()) continue;
      candidates.push({ organization, channel });

      if (!normalizedHandle) continue;
      const names = [channel.name, channel.displayName]
        .filter(Boolean)
        .map((value) => String(value).replace(/^@/, "").trim().toLowerCase());

      if (names.includes(normalizedHandle)) {
        return { organization, channel };
      }
    }
  }

  if (!normalizedHandle && candidates.length === 1) return candidates[0];

  if (candidates.length === 0) {
    throw new Error(`No Buffer channel found for service "${service}"`);
  }

  throw new Error(
    `Could not uniquely resolve Buffer channel for ${service}${normalizedHandle ? ` @${normalizedHandle}` : ""}. Candidates: ${candidates
      .map(({ channel }) => `${channel.displayName || channel.name} (${channel.id})`)
      .join(", ")}`
  );
}

function normalizeMedia(media = []) {
  if (!Array.isArray(media)) throw new Error("media must be an array");

  return media.map((item, index) => {
    if (!item?.url) throw new Error(`media[${index}].url is required`);
    const type = item.type || (/\.(mp4|mov|m4v|webm)(\?|$)/i.test(item.url) ? "video" : "image");

    if (type === "image") {
      const image = { url: item.url };
      if (item.altText) image.metadata = { altText: item.altText };
      return { image };
    }

    if (type === "video") {
      const video = { url: item.url };
      const metadata = {};
      if (Number.isInteger(item.thumbnailOffset) && item.thumbnailOffset >= 0) {
        metadata.thumbnailOffset = item.thumbnailOffset;
      }
      if (item.title) metadata.title = item.title;
      if (Object.keys(metadata).length) video.metadata = metadata;
      return { video };
    }

    throw new Error(`Unsupported media type "${type}" at media[${index}]`);
  });
}

export async function createInstagramPost({
  channelId,
  text = "",
  postType = "post",
  media = [],
  dueAt,
  publishNow = false,
  shouldShareToFeed,
  isAiGenerated = false
} = {}) {
  if (!channelId) throw new Error("channelId is required");
  if (!["post", "story", "reel", "carousel"].includes(postType)) {
    throw new Error('postType must be "post", "story", "reel", or "carousel"');
  }

  const assets = normalizeMedia(media);

  if (assets.length === 0 && postType !== "post") {
    throw new Error(`${postType} requires at least one media asset`);
  }

  const mode = publishNow ? "shareNow" : dueAt ? "customScheduled" : "addToQueue";
  const resolvedShareToFeed =
    typeof shouldShareToFeed === "boolean"
      ? shouldShareToFeed
      : postType === "story"
        ? false
        : true;

  const input = {
    text,
    channelId,
    schedulingType: "automatic",
    mode,
    assets,
    metadata: {
      instagram: {
        type: postType,
        shouldShareToFeed: resolvedShareToFeed,
        isAiGenerated: Boolean(isAiGenerated)
      }
    },
    aiAssisted: false
  };

  if (dueAt) input.dueAt = dueAt;

  const data = await graphql(
    `
      mutation CreateInstagramPost($input: CreatePostInput!) {
        createPost(input: $input) {
          ... on PostActionSuccess {
            post {
              id
              text
              dueAt
              status
              channelId
              assets {
                id
                mimeType
                source
                thumbnail
              }
              metadata {
                ... on InstagramPostMetadata {
                  type
                  shouldShareToFeed
                  isAiGenerated
                }
              }
            }
          }
          ... on MutationError {
            message
          }
        }
      }
    `,
    { input }
  );

  const result = data.createPost;
  if (!result) throw new Error("Buffer returned no createPost result");
  if (result.message && !result.post) throw new Error(`Buffer rejected post: ${result.message}`);
  if (!result.post?.id) throw new Error(`Unexpected Buffer createPost result: ${JSON.stringify(result)}`);

  return result.post;
}
