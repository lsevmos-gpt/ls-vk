/* One-shot scheduled 26 Oct Bar VK Stories. Never replay a story after stories.save.
 * Provider writes only after 18:30 Moscow; durable receipt committed before any upload.
 */
import fs from "node:fs";
import crypto from "node:crypto";
import path from "node:path";
import {execFileSync} from "node:child_process";
import {getGroupId, vkCall, uploadStory} from "../src/vk.js";

const ROOT=process.cwd();
const VERIFY="results/verification/bar-stories-20261026-stage.json";
const MANIFEST="media-prep/bar-stories-20261026.json";
const RECEIPT="results/campaigns/bar-stories-20261026-vk.json";
const DUE=Date.parse("2026-10-26T18:30:00+03:00");
const LATE_MS=180000;
const MEDIA=[
  {id:"intro-bar",file:"media/bar-20261026-intro-vk.mp4"},
  {id:"bumble-coffee",file:"media/bar-20261026-bumble-vk.mp4"},
  {id:"isotonic-bar",file:"media/bar-20261026-isotonic-vk.mp4"}
];
const stamp=()=>new Date().toISOString();
const pause=ms=>new Promise(done=>setTimeout(done,ms));
function git(...args) {
  try {execFileSync("git",args,{cwd:ROOT,timeout:100000,stdio:"pipe"});}
  catch(e){throw Error("Git sync "+args.slice(0,2).join(" ")+" failed: "+String(e?.stderr||e).slice(-350));}
}
function hash(file) {
  return crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
}
function preflight() {
  if(process.env.GITHUB_REPOSITORY!=="lsevmos-gpt/ls-vk" ||
     process.env.GITHUB_REF!=="refs/heads/main" ||
     process.env.GITHUB_EVENT_NAME!=="schedule" ||
     !/^\d+$/.test(process.env.GITHUB_RUN_ID||""))
       throw Error("Unauthorized scheduled workflow context");
  if(!process.env.VK_GROUP_TOKEN)throw Error("VK_GROUP_TOKEN not configured");
  git("pull","--ff-only","origin","main");
  if(fs.existsSync(RECEIPT))throw Error("VK sequence already attempted; DO NOT duplicate");
  const doc=JSON.parse(fs.readFileSync(MANIFEST,"utf8"));
  const qa=JSON.parse(fs.readFileSync(VERIFY,"utf8"));
  if(doc.id!=="bar-stories-20261026" || doc.approved!==true || doc.publicContent!==true ||
     doc.publishAt!=="2026-10-26T18:30:00+03:00" || doc.vkGroupId!==48198173 ||
     !qa.ok || !qa.sourceOriginalsVerified || !qa.vkIntroOriginalBytes || !qa.bumbleTimeFitForVK || !qa.isotonicDownscaledFrom4K ||
     qa.id!==doc.id || qa.sequence.length!==3 ||
     JSON.stringify(doc.sequence.map(o=>o.id))!==JSON.stringify(MEDIA.map(o=>o.id)) ||
     JSON.stringify(qa.sequence.map(o=>o.id))!==JSON.stringify(MEDIA.map(o=>o.id)))
        throw Error("VK approved source/QA mismatch");
  for(let index=0;index<MEDIA.length;index++) {
    const media=MEDIA[index], staged=qa.sequence[index], original=doc.sequence[index];
    if(staged.vkPath!==media.file || staged.sourceDriveSHA256!==original.sha256)
      throw Error("VK source identity mismatch: "+media.id);
    if(!fs.existsSync(media.file) || !fs.statSync(media.file).isFile() ||
       fs.statSync(media.file).size!==staged.vkBytes || hash(media.file)!==staged.vkSHA256)
      throw Error("Invalid VK media bytes: "+media.id);
    if(staged.dimensions!=="1080x1920" || staged.fps!==24)
      throw Error("Incompatible VK Story format: "+media.id);
  }
}
async function liveIds() {
  const response=await vkCall("stories.get",{owner_id:-48198173},process.env.VK_GROUP_TOKEN);
  const items=Array.isArray(response?.items)?response.items:Array.isArray(response)?response:[];
  const stories=items.flatMap(x=>Array.isArray(x?.stories)?x.stories:Array.isArray(x)?x:[x]);
  return stories.filter(x=>Number(x?.owner_id)===-48198173 && Number.isInteger(x?.id))
    .map(x=>({id:x.id,ownerId:x.owner_id,date:x.date}));
}
async function groupReady() {
  const groupId=await getGroupId();
  if(Number(groupId)!==48198173)throw Error("Unexpected VK group id");
  const response=await vkCall("groups.getById",{group_id:48198173},process.env.VK_GROUP_TOKEN);
  const group=Array.isArray(response?.groups)?response.groups[0]:Array.isArray(response)?response[0]:response;
  if(Number(group?.id)!==48198173 || group?.screen_name!=="liniya__sporta")
    throw Error("VK group identity mismatch");
  const before=await liveIds();
  console.log("VK_STORIES_READ_ONLY_PREFLIGHT",before.length);
}
function checkpoint(rec,first=false) {
  rec.updatedAtUTC=stamp();
  fs.mkdirSync(path.dirname(RECEIPT),{recursive:true});
  fs.writeFileSync(RECEIPT,JSON.stringify(rec,null,2)+"\n",first?{flag:"wx"}:undefined);
  git("add","--",RECEIPT);
  git("commit","-m","Record 26 Oct VK Bar Stories "+rec.status+" [skip ci]");
}
async function pushCheckpoint(rec,first=false) {
  checkpoint(rec,first);
  for(let n=0;n<4;n++) {
    try {
      git("pull","--rebase","origin","main");
      git("push","origin","HEAD:main");
      console.log("VK_CHECKPOINT",rec.status,rec.published.length);
      return;
    } catch(e) {
      if(n===3)throw e;
      await pause(1000*(n+1));
    }
  }
}
async function waitTarget() {
  const seconds=DUE-Date.now();
  if(seconds>0){
    console.log("WAIT_FOR_MSK_1830",Math.round(seconds/1000));
    await pause(seconds);
  }
  if(Date.now()-DUE>LATE_MS)throw Error("Missed VK posting time; do not publish late");
}
async function main() {
  if(fs.existsSync(RECEIPT)){console.log("26 Oct VK attempt already has receipt; no duplicate execution");return;}
  preflight();
  await groupReady();
  await waitTarget();
  git("pull","--ff-only","origin","main");
  if(fs.existsSync(RECEIPT)){console.log("VK already reserved; skipping");return;}
  git("config","user.name","ls-vk-story-bot");
  git("config","user.email","41898282+github-actions[bot]@users.noreply.github.com");
  const rec={id:"bar-stories-20261026-vk",provider:"vk",groupId:48198173,
    scheduledFor:"2026-10-26T18:30:00+03:00",runId:process.env.GITHUB_RUN_ID,
    createdAtUTC:stamp(),status:"reserved_before_provider_call",published:[],
    note:"Exactly three approved stories; never retry provider save after uncertainty."};
  await pushCheckpoint(rec,true);
  for(let index=0;index<MEDIA.length;index++) {
    const m=MEDIA[index];
    try {
      rec.status="submission_started"; rec.attemptingIndex=index+1; rec.attemptingItem=m.id;
      await pushCheckpoint(rec);
      const result=await uploadStory({path:path.resolve(ROOT,m.file),originalname:path.basename(m.file),
        mimetype:"video/mp4"},{type:"video",addToNews:true});
      const story=Array.isArray(result?.items)?result.items.find(x=>Number(x?.owner_id)===-48198173 &&
        Number.isInteger(x?.id)):null;
      if(!story)throw Error("VK stories.save returned no exact community Story ID; status unknown");
      rec.published.push({index:index+1,name:m.id,vkStoryId:story.id,ownerId:story.owner_id,
        publishedAtUTC:stamp()});
      rec.status=index===2?"submitted_to_vk":"partial_submitted_to_vk";
      delete rec.attemptingIndex;delete rec.attemptingItem;
      await pushCheckpoint(rec);
      console.log("VK_STORY_ACCEPTED",index+1,m.id,story.id);
      if(index<2)await pause(2500);
    }catch(e){
      rec.status="manual_review_required";rec.error=String(e?.message||e).slice(0,300);
      rec.note="Uncertain provider result: DO NOT RETRY until direct read-only reconciliation.";
      try{await pushCheckpoint(rec)}catch(err){console.error("Receipt checkpoint failed; prior reservation retained",err);}
      throw e;
    }
  }
  let current=[];
  for(let iteration=0;iteration<12;iteration++) {
    try {
      current=await liveIds();
      const ids=new Set(current.map(x=>x.id));
      if(rec.published.every(x=>ids.has(x.vkStoryId)))break;
    } catch(e){rec.verificationError=String(e?.message||e).slice(0,200);}
    if(iteration<11)await pause(2500);
  }
  const ids=new Set(current.map(x=>x.id));
  rec.liveVerifiedStoryIds=rec.published.filter(x=>ids.has(x.vkStoryId)).map(x=>x.vkStoryId);
  rec.status=rec.liveVerifiedStoryIds.length===3?"published_verified_by_vk":"submitted_to_vk_verify_pending";
  await pushCheckpoint(rec);
  console.log("VK_BAR_THREE_FINAL",JSON.stringify({status:rec.status,published:rec.published}));
}
main().catch(e=>{console.error("::error::VK_BAR_20261026",String(e?.message||e).slice(0,400));process.exitCode=1;});
