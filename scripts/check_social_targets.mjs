// Read-only identity verification. Never publishes or prints tokens.
import { getOrganizations, getChannels } from '../src/buffer.js';
import { getGroupId, vkCall } from '../src/vk.js';
const platform = process.env.SOCIAL_PLATFORM;
if (platform === 'vk') {
  const id = await getGroupId();
  if (id !== 48198173) throw new Error('Unexpected VK group ID');
  const g = await vkCall('groups.getById', { group_id: id }, process.env.VK_GROUP_TOKEN);
  const group = Array.isArray(g?.groups) ? g.groups[0] : Array.isArray(g) ? g[0] : g;
  if (!group || Number(group.id) !== id || group.screen_name !== 'liniya__sporta') {
    throw new Error('VK group response does not match 48198173/liniya__sporta');
  }
  console.log('VK_TARGET=VERIFIED');
} else if (platform === 'buffer') {
  const account = await getOrganizations();
  const hits = [];
  for (const org of account.organizations || []) {
    for (const channel of await getChannels(org.id)) {
      if (String(channel.service).toLowerCase() !== 'instagram') continue;
      const names = [channel.name, channel.displayName].filter(Boolean)
        .map(s => String(s).replace(/^@/, '').trim().toLowerCase());
      if (names.includes('liniya__sporta')) hits.push(channel);
    }
  }
  if (hits.length !== 1) throw new Error('Expected precisely one Buffer Instagram channel liniya__sporta');
  console.log('INSTAGRAM_TARGET=VERIFIED');
} else {
  throw new Error('Unrecognized social platform');
}