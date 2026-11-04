/* Exactly one approved VK clip: Sofia Bulatetskaya, no second author. */
import fs from "node:fs";
import crypto from "node:crypto";
import path from "node:path";
import {execFileSync} from "node:child_process";
import {getGroupId, vkCall, uploadWallVideo, publishWallPost} from "../src/vk.js";
const ID="sofiya-bulatetskaya-20261104-vk-clip";
const QA="results/verification/sofiya-bulatetskaya-20261104-reel-qa.json";
const RELEASE="requests/campaigns/sofiya-bulatetskaya-20261104-vk-clip.json";
const RECEIPT="results/campaigns/sofiya-bulatetskaya-20261104-vk-clip.json";
const VIDEO="media/sofiya-bulatetskaya-20261104-reel-meta.mp4";
const COVER="media/sofiya-bulatetskaya-20261104-reel-original-cover.png";
const VIDEO_SHA="eeef216d93c29b4f0ebcbeba8e763466c411adb7b1d0a1c96d06c5b01b30a072";
const COVER_SHA="1ebf16eaca7b8cc7c6de25043bf5d922361ec96087d5eb605c0670b7a3dbfaa1";
const GROUP_ID=48198173;
const wait=(ms)=>new Promise(resolve=>setTimeout(resolve,ms));
const checksum=(p)=>crypto.createHash("sha256").update(fs.readFileSync(p)).digest("hex");
function git(...args){
  try{execFileSync("git",args,{stdio:"pipe",timeout:95000});}
  catch(e){throw Error("git "+args.slice(0,2).join(" ")+" failed: "+String(e.stderr||e).slice(-260));}
}
async function checkpoint(doc,first=false){
  doc.updatedAtUTC=new Date().toISOString();
  fs.mkdirSync(path.dirname(RECEIPT),{recursive:true});
  fs.writeFileSync(RECEIPT,JSON.stringify(doc,null,2)+"\n",first?{flag:"wx"}:undefined);
  git("add","--",RECEIPT);
  git("commit","-m","Record one Sofia Bulatetskaya VK clip "+doc.status+" [skip ci]");
  for(let i=0;i<7;i++){
    try{git("pull","--rebase","origin","main");git("push","origin","HEAD:main");return;}
    catch(e){if(i===6)throw e;await wait((i+1)*1100);}
  }
}
async function readOnlyPreflight(){
  if(process.env.GITHUB_REPOSITORY!=="lsevmos-gpt/ls-vk" ||
    process.env.GITHUB_REF!=="refs/heads/main" ||
    process.env.GITHUB_EVENT_NAME!=="push" ||
    process.env.GITHUB_ACTOR!=="lsevmos-gpt" ||
    !/^\d+$/.test(process.env.GITHUB_RUN_ID||""))
      throw Error("Unauthorized VK publication context");
  git("pull","--ff-only","origin","main");
  if(fs.existsSync(RECEIPT)){console.log("VK_CLIP_PREEXISTING_RECEIPT_NO_DUPLICATE");return null;}
  if(!process.env.VK_USER_TOKEN)throw Error("VK_USER_TOKEN missing: cannot upload VK Clip; no provider mutation");
  if(!process.env.VK_GROUP_TOKEN)throw Error("VK_GROUP_TOKEN missing: cannot verify target");
  const j=JSON.parse(fs.readFileSync(RELEASE,"utf8"));
  const q=JSON.parse(fs.readFileSync(QA,"utf8"));
  const ig=JSON.parse(fs.readFileSync("results/instagram-meta/sofiya-bulatetskaya-20261104-reel.json","utf8"));
  if(j.id!==ID || j.type!=="clip" || !j.approved || !j.publicContent || !j.submitNow ||
     j.groupId!==GROUP_ID || j.groupScreenName!=="liniya__sporta" ||
     !j.nativeCollaborator.approvedToPublishWithoutCollaborator || j.nativeCollaborator.required ||
     !j.instagram.alreadyPublished || !j.instagram.doNotPublishAgain ||
     ig.status!=="published_readback_confirmed" ||
     j.description!==ig.caption || j.wallText!==ig.caption ||
     j.videoPath!==VIDEO || j.coverOriginalPath!==COVER ||
     !q.ok || q.videoPath!==VIDEO || q.videoSHA256!==VIDEO_SHA ||
     q.videoBytes!==58890709 || !q.videoStreamUnchanged ||
     q.videoWidth!==1080 || q.videoHeight!==1920 || q.fps!==25 ||
     q.videoCodec!=="h264" || q.audioCodec!=="aac" ||
     q.coverPngSHA256!==COVER_SHA ||
     !fs.existsSync(VIDEO)||fs.statSync(VIDEO).size!==q.videoBytes||checksum(VIDEO)!==VIDEO_SHA||
     !fs.existsSync(COVER)||checksum(COVER)!==COVER_SHA)
    throw Error("VK approved media, caption, group or no-coauthor release mismatch");
  const target=await getGroupId();
  if(Number(target)!==GROUP_ID)throw Error("Wrong VK group ID");
  const response=await vkCall("groups.getById",{group_id:GROUP_ID},process.env.VK_GROUP_TOKEN);
  const group=Array.isArray(response?.groups)?response.groups[0]:Array.isArray(response)?response[0]:response;
  if(Number(group?.id)!==GROUP_ID||group?.screen_name!=="liniya__sporta")throw Error("Wrong VK target group identity");
  const permission=Number(await vkCall("account.getAppPermissions",{},process.env.VK_USER_TOKEN));
  if((permission&16)!==16)throw Error("VK_USER_TOKEN lacks video permission (bit 16); no provider mutation");
  console.log("SOFIYA_VK_CLIP_PREFLIGHT_CONFIRMED_1080P_ORIGINAL_H264_NO_COAUTHOR",JSON.stringify({groupId:target,bytes:q.videoBytes}));
  return j;
}
async function main(){
  const j=await readOnlyPreflight();
  if(!j)return;
  git("config","user.name","ls-sofiya-vk-clip-one-shot");
  git("config","user.email","41898282+github-actions[bot]@users.noreply.github.com");
  if(fs.existsSync(RECEIPT)){console.log("VK_RESERVED_BY_OTHER_RUN_NO_REPEAT");return;}
  const doc={id:ID,provider:"vk",contentType:"clip",groupId:GROUP_ID,
    status:"reserved_before_vk_video_upload",runId:process.env.GITHUB_RUN_ID,
    videoPath:VIDEO,videoSHA256:VIDEO_SHA,videoResolution:"1080x1920",bitIdenticalH264:true,
    noCollaboratorApproved:true,description:j.description,videoId:null,wallPostId:null,
    createdAtUTC:new Date().toISOString(),note:"Only one upload and one wall post; never retry after uncertain VK mutation"};
  await checkpoint(doc,true);
  try{
    doc.status="vk_video_upload_started";await checkpoint(doc);
    const uploaded=await uploadWallVideo({path:path.resolve(VIDEO),
      originalname:"sofiya-bulatetskaya-reel-1080x1920.mp4",mimetype:"video/mp4"},
      {name:j.name,description:j.description});
    const ownerId=Number(uploaded?.video?.owner_id);
    const videoId=Number(uploaded?.video?.id);
    if(ownerId!==-GROUP_ID || !Number.isInteger(videoId) || videoId<=0)
      throw Error("VK video upload returned no exact target community video ID: reconcile manually, do not retry");
    doc.videoOwnerId=ownerId;doc.videoId=videoId;
    doc.status="vk_video_api_accepted";
    await checkpoint(doc);
    doc.status="vk_wall_post_started";
    await checkpoint(doc);
    const post=await publishWallPost({text:j.wallText,attachments:[uploaded.attachment]});
    const postId=Number(post?.post_id);
    if(!Number.isInteger(postId)||postId<=0)
      throw Error("VK wall.post outcome uncertain: do not retry");
    doc.wallPostId=postId;doc.status="vk_video_and_wall_api_accepted";
    await checkpoint(doc);
    let videoVerified=false,wallVerified=false,videoReadbackError=null,wallReadbackError=null;
    for(let i=0;i<6;i++){
      try{
        const vr=await vkCall("video.get",{videos:String(ownerId)+"_"+String(videoId)},process.env.VK_USER_TOKEN);
        videoVerified=Array.isArray(vr?.items)&&vr.items.some(v=>Number(v.id)===videoId&&Number(v.owner_id)===ownerId);
      }catch(e){videoReadbackError=String(e.message||e).slice(0,140);}
      try{
        const wr=await vkCall("wall.getById",{posts:String(-GROUP_ID)+"_"+String(postId)},process.env.VK_GROUP_TOKEN);
        const list=Array.isArray(wr?.items)?wr.items:Array.isArray(wr)?wr:[];
        wallVerified=list.some(p=>Number(p.id)===postId&&Number(p.owner_id)===-GROUP_ID);
      }catch(e){wallReadbackError=String(e.message||e).slice(0,140);}
      if(videoVerified&&wallVerified)break;
      if(i<5)await wait(4000);
    }
    doc.videoReadbackConfirmed=videoVerified;doc.wallReadbackConfirmed=wallVerified;
    if(videoReadbackError&&!videoVerified)doc.videoReadbackError=videoReadbackError;
    if(wallReadbackError&&!wallVerified)doc.wallReadbackError=wallReadbackError;
    doc.status=videoVerified&&wallVerified?"published_verified_by_vk":"vk_api_accepted_readback_partial";
    doc.videoUrl="https://vk.com/video"+ownerId+"_"+videoId;
    doc.wallUrl="https://vk.com/wall"+(-GROUP_ID)+"_"+postId;
    doc.customCoverApplied=false;
    doc.customCoverNote="No supported native VK clip thumbnail upload established. Original cover preserved; VK may use an auto-generated frame.";
    await checkpoint(doc);
    console.log("SOFIYA_VK_CLIP_FINAL",JSON.stringify({status:doc.status,videoId,wallPostId:postId,videoReadbackConfirmed:videoVerified,wallReadbackConfirmed:wallVerified,videoUrl:doc.videoUrl,wallUrl:doc.wallUrl}));
  }catch(error){
    doc.status="manual_reconciliation_required";
    doc.error=String(error.message||error).slice(0,400);
    doc.note="VK video or wall mutation may have happened. DO NOT REPLAY without read-only reconciliation.";
    try{await checkpoint(doc);}catch(e){console.error("VK_RECEIPT_CHECKPOINT_FAILED",String(e).slice(0,160));}
    throw error;
  }
}
main().catch(error=>{console.error("::error::SOFIYA_VK_CLIP",String(error.message||error).slice(0,450));process.exitCode=1;});
