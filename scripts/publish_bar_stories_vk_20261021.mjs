/* ONE-SHOT Bar -> Berry -> Creatine Stories publisher for exact VK group -48198173.
 * No automatic retries of stories.save; durable reserve + per-story receipts.
 */
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { execFileSync } from "node:child_process";
import { getGroupId, vkCall, uploadStory } from "../src/vk.js";

const ROOT = process.cwd();
const TARGET = "results/campaigns/bar-three-stories-20261021-vk.json";
const SOURCE = "results/verification/bar-three-stories-20261021-stage.json";
const REQUEST = "requests/campaigns/bar-three-stories-20261021-vk.json";
const MEDIA = [
  {id:"bar-intro",media:"media/bar-20261021-intro-original.mp4",sha256:"96a269ddf1e5dc65e8a33bfddbbd1463b7943a22bab92079d149b128540eba3e"},
  {id:"berry-smoothie-v2",media:"media/bar-20261021-berry-v2-original.mp4",sha256:"edc6d12b52992e66b730dc4c925906288855822968f2f500a4a63980d1ee48fb"},
  {id:"creatine",media:"media/bar-20261021-creatine-meta-vk-hq.mp4",sha256:"ecf2ed306a49840b549a44962dd1136a3c67ff126786818bf7457436f227cb97"}
];

function git(...args) {
  execFileSync("git",args,{cwd:ROOT,timeout:90000,stdio:"pipe"});
}

const iso = () => new Date().toISOString();
const delay = ms => new Promise(done=>setTimeout(done,ms));
function sha(file) {
  return crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
}

async function checkpoint(record) {
  record.updatedAtUTC=iso();
  fs.writeFileSync(TARGET,JSON.stringify(record,null,2)+"\n");
  git("add","--",TARGET);
  git("commit","-m","Record one-shot VK Bar Stories "+record.status+" [skip ci]");
  git("pull","--rebase","origin","main");
  git("push","origin","HEAD:main");
  console.log("VK_BAR_STORY_CHECKPOINT",JSON.stringify({status:record.status,publishedCount:record.published.length}));
}

async function liveIds() {
  const response=await vkCall("stories.get",{owner_id:-48198173},process.env.VK_GROUP_TOKEN);
  const items=Array.isArray(response?.items)?response.items:Array.isArray(response)?response:[];
  const stories=items.flatMap(x=>Array.isArray(x?.stories)?x.stories:Array.isArray(x)?x:[x]);
  return stories.filter(s=>Number(s?.owner_id)===-48198173 && Number.isInteger(s.id))
    .map(s=>({id:s.id,type:s.type,date:s.date}));
}

async function main() {
  if(process.env.GITHUB_REPOSITORY!=="lsevmos-gpt/ls-vk" ||
     process.env.GITHUB_REF!=="refs/heads/main" ||
     process.env.GITHUB_ACTOR!=="lsevmos-gpt" ||
     !/^\d+$/.test(process.env.GITHUB_RUN_ID||""))throw Error("Unauthorized GH context");
  if(!process.env.VK_GROUP_TOKEN)throw Error("VK_GROUP_TOKEN missing");
  git("pull","--ff-only","origin","main");
  if(fs.existsSync(TARGET))throw Error("Already attempted; NEVER repeat");
  const manifest=JSON.parse(fs.readFileSync(REQUEST,"utf8"));
  const stage=JSON.parse(fs.readFileSync(SOURCE,"utf8"));
  if(manifest.id!=="bar-three-stories-20261021-vk" ||
     manifest.platform!=="vk" || manifest.communityId!==48198173 ||
     manifest.approved!==true || manifest.publicContent!==true ||
     manifest.submitNow!==true ||stage.ok!==true)throw Error("Unapproved or invalid VK manifest");
  const expected=MEDIA.map(x=>({id:x.id,storyType:"video",media:x.media,addToNews:true}));
  if(JSON.stringify(manifest.stories)!==JSON.stringify(expected))throw Error("Unexpected Stories or order");
  if(JSON.stringify(stage.orderedMedia)!==JSON.stringify(MEDIA.map(x=>x.media)))throw Error("Staging order mismatch");
  for(const m of MEDIA) {
    if(!fs.existsSync(m.media) || !fs.statSync(m.media).isFile() ||
       sha(m.media)!==m.sha256 || stage.files[m.media].sha256!==m.sha256)
        throw Error("Unverified media "+m.id);
  }
  const groupId=await getGroupId();
  if(groupId!==48198173)throw Error("Unexpected VK group");
  const groupData=await vkCall("groups.getById",{group_id:48198173},process.env.VK_GROUP_TOKEN);
  const group=Array.isArray(groupData?.groups)?groupData.groups[0]:Array.isArray(groupData)?groupData[0]:groupData;
  if(Number(group?.id)!==48198173 || group.screen_name!=="liniya__sporta")
    throw Error("VK group identity mismatch");
  // Baseline read-only to avoid blindly posting over potentially already published content.
  const before=await liveIds();
  console.log("VK_BEFORE_CURRENT_STORY_COUNT",before.length);
  const record={
    id:"bar-three-stories-20261021-vk",provider:"vk",
    groupId:48198173,status:"reserved_before_provider_call",
    runId:process.env.GITHUB_RUN_ID,createdAtUTC:iso(),published:[],
    note:"Only the 3 approved video files. No replay after uncertain provider response."
  };
  fs.mkdirSync("results/campaigns",{recursive:true});
  fs.writeFileSync(TARGET,JSON.stringify(record,null,2)+"\n",{flag:"wx"});
  git("config","user.name","ls-vk-story-bot");
  git("config","user.email","41898282+github-actions[bot]@users.noreply.github.com");
  git("add","--",TARGET);
  git("commit","-m","Reserve one approved VK Bar Stories sequence [skip ci]");
  git("push","origin","HEAD:main");
  for(let index=0;index<MEDIA.length;index++){
    const m=MEDIA[index];
    try {
      record.status="submission_started";
      record.attemptingIndex=index+1;
      record.attemptingItem=m.id;
      await checkpoint(record); // saved prior to first provider write.
      const result=await uploadStory({
        path:path.resolve(ROOT,m.media),
        originalname:path.basename(m.media),
        mimetype:"video/mp4"
      },{type:"video",addToNews:true});
      const story=Array.isArray(result?.items)?result.items.find(o=>Number(o?.owner_id)===-48198173&&Number.isInteger(o?.id)):null;
      if(!story)throw Error("VK stories.save response missing precise community Story ID; result uncertain");
      const row={index:index+1,name:m.id,vkStoryId:story.id,ownerId:story.owner_id,publishedAtUTC:iso()};
      record.published.push(row);
      record.status=index+1===MEDIA.length?"submitted_to_vk":"partial_submitted_to_vk";
      delete record.attemptingIndex;
      delete record.attemptingItem;
      await checkpoint(record);
      console.log("VK_STORY_PROVIDER_ACCEPTED",index+1,m.id,story.id);
      if(index+1<MEDIA.length)await delay(2500);
    } catch(error) {
      record.status="manual_review_required";
      record.error=String(error?.message||error).slice(0,280);
      record.note="VK provider result uncertain or rejected; never retry until read-only reconciliation";
      try{await checkpoint(record)}catch(e){console.error("Failed to save final receipt; prior reservation retained")}
      throw error;
    }
  }
  let current=[];
  for(let n=0;n<12;n++){
    try{
      current=await liveIds();
      const ids=new Set(current.map(x=>x.id));
      if(record.published.every(x=>ids.has(x.vkStoryId)))break;
    }catch(error){record.verificationError=String(error?.message||error).slice(0,160)}
    if(n<11)await delay(2500);
  }
  const ids=new Set(current.map(x=>x.id));
  record.liveVerifiedStoryIds=record.published.filter(x=>ids.has(x.vkStoryId)).map(x=>x.vkStoryId);
  record.status=record.liveVerifiedStoryIds.length===3?"published_verified_by_vk":"submitted_to_vk_verify_pending";
  await checkpoint(record);
  console.log("VK_BAR_FINAL",JSON.stringify({status:record.status,published:record.published,verified:record.liveVerifiedStoryIds}));
}

main().catch(e=>{
  console.error("::error::VK_BAR_SEQUENCE",String(e?.message||e).slice(0,350));
  process.exitCode=1;
});
