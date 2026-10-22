/* Publish exactly one approved second-floor VK vertical clip and community wall post after 18:30 MSK. */
import fs from "node:fs";
import crypto from "node:crypto";
import {execFileSync, spawnSync} from "node:child_process";
import {getGroupId, vkCall, uploadWallVideo, publishWallPost} from "../src/vk.js";

const ROOT=process.cwd();
const REQUEST="requests/vk/second-floor-20261022-1830-vk-clip.json";
const QA="results/verification/second-floor-reel-20261022-prepared.json";
const RECEIPT="results/manual/vk/second-floor-20261022-1830-vk-clip.json";
const VIDEO="media/second-floor-20261022-reel-meta-vk.mp4";
const TARGET_MS=Date.parse("2026-10-22T18:30:00+03:00");
const LAST_MS=Date.parse("2026-10-22T18:50:00+03:00");

const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const iso=()=>new Date().toISOString();
function git(...args) {return execFileSync("git",args,{cwd:ROOT,timeout:90000,encoding:"utf8"});}
async function waitUntil(ms) {
  while(Date.now()<ms)await sleep(Math.max(100,Math.min(30000,ms-Date.now())));
}
async function checkpoint(r,{first=false}={}) {
  r.updatedAtUTC=iso();
  fs.mkdirSync("results/manual/vk",{recursive:true});
  fs.writeFileSync(RECEIPT,JSON.stringify(r,null,2)+"\n",first?{flag:"wx"}:undefined);
  git("add","--",RECEIPT);
  git("commit","-m","Record 18:30 approved Second Floor VK clip attempt [skip ci]");
  for(let i=0;i<8;i++){
    git("pull","--rebase","origin","main");
    const p=spawnSync("git",["push","origin","HEAD:main"],{cwd:ROOT,encoding:"utf8",timeout:90000});
    if(p.status===0){console.log("VK_RECEIPT_COMMITTED",r.status);return;}
    await sleep(1000+1000*i);
  }
  throw Error("VK receipt GitHub persistence failed. Do not retry publishing");
}

async function main(){
  if(process.env.GITHUB_REPOSITORY!=="lsevmos-gpt/ls-vk" ||
    process.env.GITHUB_REF!=="refs/heads/main" ||
    !["schedule","workflow_dispatch"].includes(process.env.GITHUB_EVENT_NAME) ||
    !/^\d+$/.test(process.env.GITHUB_RUN_ID||""))
    throw Error("Not authorized scheduled execution");
  if(!process.env.VK_GROUP_TOKEN || !process.env.VK_USER_TOKEN)
    throw Error("VK_GROUP_TOKEN or VK_USER_TOKEN missing");
  git("pull","--ff-only","origin","main");
  if(fs.existsSync(RECEIPT))throw Error("Already reserved or published, NEVER retry");
  const req=JSON.parse(fs.readFileSync(REQUEST,"utf8"));
  const qa=JSON.parse(fs.readFileSync(QA,"utf8"));
  if(req.id!=="second-floor-20261022-1830-vk-clip" || req.type!=="clip" ||
    req.approved!==true || req.publicContent!==true ||
    req.notBefore!=="2026-10-22T18:30:00+03:00" ||
    req.media!==VIDEO ||
    req.postToWall!==true ||
    req.name!=="ВТОРОЙ ЭТАЖ | Линия Спорта" ||
    !req.wallText.startsWith("🔥 Мы создаём возможности для вас!") ||
    req.description!==req.wallText ||
    qa.ok!==true || qa.id!=="second-floor-reel-20261022" ||
    qa.originalSizeBytes!==535389636 ||
    qa.sourceGoogleDriveFileId!=="1G7CvPTEmxeRNhyCXCj_Jv1ZhHYnlYHBg")
       throw Error("Unexpected VK request or source verification");
  const file=fs.readFileSync(VIDEO);
  const sha=crypto.createHash("sha256").update(file).digest("hex");
  if(sha!==qa.videoSHA256)throw Error("Source video bytes mismatch");
  if(Date.now()>LAST_MS)throw Error("Approved 18:30 window already passed");
  const groupId=await getGroupId();
  if(groupId!==48198173)throw Error("Wrong VK group");
  const response=await vkCall("groups.getById",{group_id:48198173},process.env.VK_GROUP_TOKEN);
  const group=Array.isArray(response?.groups)?response.groups[0]:Array.isArray(response)?response[0]:response;
  if(Number(group?.id)!==48198173)throw Error("VK community not verified");
  // Verify user token validity before reserving.
  const users=await vkCall("users.get",{},process.env.VK_USER_TOKEN);
  if(!Array.isArray(users)||users.length===0)throw Error("VK user token invalid");
  git("config","user.name","ls-vk-clip-bot");
  git("config","user.email","41898282+github-actions[bot]@users.noreply.github.com");
  const record={id:req.id,provider:"vk",type:"clip",groupId:48198173,
    scheduledFor:req.notBefore,runId:process.env.GITHUB_RUN_ID,
    status:"reserved",publishedAt:null,createdAtUTC:iso(),
    note:"One attempt only; no replay following uncertain provider mutation"};
  await checkpoint(record,{first:true});
  await waitUntil(TARGET_MS);
  if(Date.now()>LAST_MS)throw Error("Release window exceeded, no late post");
  try{
    record.status="video_upload_call_started";
    await checkpoint(record);
    const uploaded=await uploadWallVideo({
      path:ROOT+"/"+VIDEO,originalname:"second-floor-20261022-reel-meta-vk.mp4",mimetype:"video/mp4"
    },{name:req.name,description:req.description});
    if(!uploaded?.attachment || !uploaded?.video?.id)throw Error("VK video.save outcome unclear");
    record.status="video_uploaded";
    record.videoId=uploaded.video.id;
    record.ownerId=uploaded.video.owner_id;
    record.attachment=uploaded.attachment;
    await checkpoint(record);
    record.status="wall_post_call_started";
    await checkpoint(record);
    const posted=await publishWallPost({text:req.wallText,attachments:[uploaded.attachment]});
    const postId=posted?.post_id;
    if(!Number.isInteger(postId))throw Error("VK wall.post did not return post_id");
    record.status="published";
    record.postId=postId;
    record.publishedAt=iso();
    try {
      const read=await vkCall("wall.getById",{posts:"-48198173_"+postId},process.env.VK_GROUP_TOKEN);
      const list=Array.isArray(read?.items)?read.items:Array.isArray(read)?read:[];
      record.readbackConfirmed=list.some(x=>Number(x?.id)===postId && Number(x?.owner_id)===-48198173);
    } catch (error){record.readbackConfirmed=false;}
    await checkpoint(record);
    console.log("SECOND_FLOOR_VK_CLIP_PUBLISHED",JSON.stringify({postId:record.postId,videoId:record.videoId,readbackConfirmed:record.readbackConfirmed}),flush=true);
  } catch(error) {
    if(record.status!=="published"){
      record.status="manual_review_required";
      record.error=String(error?.message||error).slice(0,300);
      try{await checkpoint(record)}catch(e){console.error("Persistence error, original marker remains");}
    }
    throw error;
  }
}
main().catch(e=>{console.error("::error::SECOND_FLOOR_VK_CLIP",String(e?.message||e).slice(0,400));process.exitCode=1;});
