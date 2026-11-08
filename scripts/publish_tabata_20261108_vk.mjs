/* One-shot TABATA 18+ VK vertical video and wall post, with approved original cover.
   Mirrors proven same-runner VK ID refresh and safe one-attempt receipt flow. */
import fs from "node:fs";
import https from "node:https";
import { execFileSync, spawnSync } from "node:child_process";
import { createHash, randomBytes } from "node:crypto";
import FormData from "form-data";
import { buildVkRefreshRequest, parseVkRefreshResponse, readOnlyVkTokenCheck } from "./vk-refresh-lib.mjs";

const REPO="lsevmos-gpt/ls-vk", GROUP=48198173, JOB="tabata-20261108";
const REQ="requests/campaigns/tabata-20261108.json";
const QA="results/verification/tabata-20261108-2k.json";
const VIDEO="media/tabata-20261108-2k-ig-vk.mp4";
const COVER="media/tabata-20261108-meta-cover.jpg";
const RECEIPT="results/campaigns/tabata-20261108-vk.json";
const SRC_SHA="9455b7574ca79cc684b9d92d2458b3b09c97e63b79cbf2dcf1ebf04659529f71";
const COVER_SHA="46ba40861605ade03564f3413ccb40ea2a3533f29d5ceaca06453b612a29243b";
const PUBLISH_AT=Date.parse("2026-11-08T15:30:00Z"); // 18:30 MSK
const UPLOAD_FROM=Date.parse("2026-11-08T15:12:00Z"); // 18:12 MSK
const DEADLINE_AT=Date.parse("2026-11-08T15:45:00Z");
const awaitTime=async when=>{while(Date.now()<when)await new Promise(r=>setTimeout(r,Math.min(12000,when-Date.now())));};
const iso=()=>new Date().toISOString();
const pause=ms=>new Promise(r=>setTimeout(r,ms));
function git(...args) {
  try {return execFileSync("git",args,{encoding:"utf8",timeout:100000,stdio:"pipe"}).trim();}
  catch(e) {throw Error("GIT_"+args[0]+"_FAILED "+String(e.stderr||e).slice(-170));}
}
function sha(p){return createHash("sha256").update(fs.readFileSync(p)).digest("hex");}
function required(k){const x=process.env[k];if(!x?.trim())throw Error("MISSING_"+k);return x.trim();}
async function checkpoint(d, initial=false){
  d.updatedAtUTC=iso();
  fs.mkdirSync("results/campaigns",{recursive:true});
  fs.writeFileSync(RECEIPT,JSON.stringify(d,null,2)+"\n",initial?{flag:"wx"}:{});
  git("add","--",RECEIPT);
  git("commit","-m","TABATA VK "+d.status+" [skip ci]");
  for(let i=0;i<8;i++) {
    try{git("pull","--rebase","origin","main");git("push","origin","HEAD:main");return;}
    catch(e){if(i===7)throw e;await pause((i+1)*1000);}
  }
}
function secretSet(args,value,pat){
  const p=spawnSync("gh",args,{input:value,encoding:"utf8",timeout:35000,maxBuffer:65536,
    env:{HOME:process.env.HOME||"",PATH:process.env.PATH||"",GH_TOKEN:pat,GH_HOST:"github.com",CI:"true"}});
  if(p.status!==0||p.error)throw Error("GITHUB_SECRET_WRITE_FAILED");
}
async function refreshVideoToken(){
  const pat=required("VK_SECRETS_WRITE_PAT");
  const probe="VK_TABATA_PROBE_20261108";
  secretSet(["secret","set",probe,"--repo",REPO],randomBytes(24).toString("base64url"),pat);
  try{secretSet(["secret","delete",probe,"--repo",REPO],"",pat);}catch{}
  const state=randomBytes(22).toString("base64url");
  const r=buildVkRefreshRequest({clientId:"54806879",redirectUri:"https://vk.liniyasporta.ru/oauth/callback",
    deviceId:required("VK_DEVICE_ID"),refreshToken:required("VK_REFRESH_TOKEN"),state});
  const res=await fetch(r.url,r.options);
  const payload=await res.json().catch(()=>null);
  if(!res.ok)throw Error("VK_REFRESH_HTTP_"+res.status);
  const tok=parseVkRefreshResponse(payload,state);
  secretSet(["secret","set","VK_REFRESH_TOKEN","--repo",REPO],tok.refreshToken,pat);
  const check=await readOnlyVkTokenCheck(tok.accessToken,"54806879");
  if(check.vkId!=="OK"||check.vkApiUsers!=="OK"||!check.vkApiAllowed)throw Error("VK_VIDEO_PERMISSION_MISSING");
  return tok.accessToken;
}
async function uploadThumb(uploadURL,filename){
  const u=new URL(uploadURL);
  if(u.protocol!=="https:"||!(/(^|\.)vk\.com$/.test(u.hostname)||/(^|\.)vk\.ru$/.test(u.hostname)))
    throw Error("VK_THUMB_UPLOAD_HOST_NOT_TRUSTED");
  const form=new FormData();
  form.append("file",fs.createReadStream(filename),{filename:"tabata18-cover.jpg",contentType:"image/jpeg"});
  return await new Promise((resolve,reject)=>{
    const rq=https.request(u,{method:"POST",headers:form.getHeaders(),timeout:60000},rs=>{
      const chunks=[];let n=0;
      rs.on("data",c=>{n+=c.length;if(n<300000)chunks.push(c);});
      rs.on("end",()=>{if(rs.statusCode<200||rs.statusCode>=300)return reject(Error("VK_THUMB_HTTP_"+rs.statusCode));resolve(Buffer.concat(chunks).toString("utf8"));});
      rs.on("error",reject);
    });
    rq.on("timeout",()=>rq.destroy(Error("VK_THUMB_UPLOAD_TIMEOUT")));
    rq.on("error",reject);form.pipe(rq);
  });
}
async function main(){
  if(process.env.GITHUB_REPOSITORY!==REPO||process.env.GITHUB_REF!=="refs/heads/main"
    ||process.env.GITHUB_EVENT_NAME!=="schedule"||!/^\d+$/.test(process.env.GITHUB_RUN_ID||""))
    throw Error("UNAUTHORIZED_CONTEXT");
  git("pull","--ff-only","origin","main");
  if(fs.existsSync(RECEIPT)){console.log("TABATA_VK_ALREADY_ATTEMPTED_NO_REPEAT");return;}
  const req=JSON.parse(fs.readFileSync(REQ,"utf8"));
  const q=JSON.parse(fs.readFileSync(QA,"utf8"));
  if(!(req.id===JOB&&req.approved===true&&req.publicContent===true&&req.postNow===false&&req.scheduledFor==="2026-11-08T18:30:00+03:00"
    &&req.sourceSHA256===SRC_SHA&&req.coverSHA256===COVER_SHA
    &&req.vk?.groupId===GROUP&&req.vk?.publishWall===true&&req.vk?.noCoauthor===true
    &&q.ok===true&&q.sourceSha256===SRC_SHA&&q.coverOriginalSha256===COVER_SHA
    &&q.videoResolution==="1440x2560"&&q.videoBytes===fs.statSync(VIDEO).size
    &&q.videoSha256===sha(VIDEO)&&fs.statSync(VIDEO).size<95000000&&q.coverMetaSha256===sha(COVER)))
    throw Error("VIDEO_SOURCE_OR_APPROVAL_MISMATCH");
  required("VK_GROUP_TOKEN");required("VK_REFRESH_TOKEN");required("VK_DEVICE_ID");required("VK_SECRETS_WRITE_PAT");
  if(Date.now()>DEADLINE_AT)throw Error("VK_1830_RELEASE_WINDOW_CLOSED");
  await awaitTime(UPLOAD_FROM);
  const token=await refreshVideoToken();
  process.env.VK_USER_TOKEN=token;
  const {getGroupId,vkCall,uploadWallVideo,publishWallPost}=await import("../src/vk.js");
  if(Number(await getGroupId())!==GROUP)throw Error("WRONG_VK_GROUP");
  const g=await vkCall("groups.getById",{group_id:GROUP},required("VK_GROUP_TOKEN"));
  const actual=Array.isArray(g?.groups)?g.groups[0]:Array.isArray(g)?g[0]:g;
  if(Number(actual?.id)!==GROUP||actual?.screen_name!=="liniya__sporta")throw Error("VK_GROUP_MISMATCH");
  git("pull","--ff-only","origin","main");
  if(fs.existsSync(RECEIPT)){console.log("TABATA_VK_ALREADY_RESERVED_NO_REPEAT");return;}
  git("config","user.name","ls-tabata-vk-publisher");
  git("config","user.email","41898282+github-actions[bot]@users.noreply.github.com");
  const d={id:JOB,provider:"vk",account:"liniya__sporta",groupId:GROUP,
    videoSha256:q.videoSha256,videoResolution:q.videoResolution,caption:req.caption,
    runId:process.env.GITHUB_RUN_ID,status:"reserved_before_provider_upload",
    videoId:null,wallPostId:null,coverStatus:"not_attempted",
    noCollaborator:true,noRetries:true,createdAtUTC:iso()};
  await checkpoint(d,true);
  try{
    d.status="video_upload_started";await checkpoint(d);
    const u=await uploadWallVideo({path:VIDEO,originalname:"liniya-sporta-tabata18-2k.mp4",mimetype:"video/mp4"},
      {name:"ТАБАТА 18+ — Линия спорта",description:req.caption});
    const vid=Number(u?.video?.id),owner=Number(u?.video?.owner_id);
    if(!Number.isSafeInteger(vid)||vid<=0||owner!==-GROUP||!u.attachment)throw Error("VK_VIDEO_UPLOAD_NOT_CONFIRMED");
    d.videoId=vid;d.ownerId=owner;d.videoUrl="https://vk.com/video"+owner+"_"+vid;
    d.status="video_uploaded_api_confirmed";await checkpoint(d);
    try{
      const thumb=await vkCall("video.getThumbUploadUrl",{owner_id:owner},token);
      if(!thumb?.upload_url)throw Error("VK_THUMB_URL_MISSING");
      const thumbJson=await uploadThumb(thumb.upload_url,COVER);
      const applied=await vkCall("video.saveUploadedThumb",{owner_id:owner,thumb_json:thumbJson,
        video_id:vid,set_thumb:1},token);
      if(!applied)throw Error("VK_THUMB_SAVE_NOT_CONFIRMED");
      d.coverStatus="api_accepted";
    }catch(e){
      d.coverStatus="unconfirmed";
      d.coverErrorClass=e?.name||"Error";
    }
    d.status="cover_checked_before_wall";await checkpoint(d);
    d.status="video_and_cover_ready_waiting_for_1830";
    await checkpoint(d);
    await awaitTime(PUBLISH_AT);
    if(Date.now()>DEADLINE_AT)throw Error("VK_1830_RELEASE_WINDOW_CLOSED_BEFORE_WALL");
    d.status="wall_post_call_started";await checkpoint(d);
    const post=await publishWallPost({text:req.caption,attachments:[u.attachment]});
    const pid=Number(post?.post_id);
    if(!Number.isSafeInteger(pid)||pid<=0)throw Error("VK_WALL_POST_NOT_CONFIRMED");
    d.wallPostId=pid;d.wallUrl="https://vk.com/wall-"+GROUP+"_"+pid;
    d.status="vk_video_wall_api_accepted";await checkpoint(d);
    let w=false,v=false;
    for(let i=0;i<6;i++){
      try{
        const x=await vkCall("wall.getById",{posts:"-"+GROUP+"_"+pid},token);
        const a=Array.isArray(x?.items)?x.items:Array.isArray(x)?x:[];
        w=a.some(x=>Number(x?.id)===pid&&Number(x?.owner_id)===-GROUP);
      }catch{}
      try{
        const x=await vkCall("video.get",{videos:owner+"_"+vid},token);
        v=Array.isArray(x?.items)&&x.items.some(x=>Number(x?.id)===vid&&Number(x?.owner_id)===owner);
      }catch{}
      if(w&&v)break;
      if(i<5)await pause(3000);
    }
    d.wallReadbackConfirmed=w;d.videoReadbackConfirmed=v;
    d.status=(w&&v)?"published_verified_by_vk":"vk_api_accepted_readback_partial";
    await checkpoint(d);
    console.log("TABATA_VK_RESULT",JSON.stringify({status:d.status,videoUrl:d.videoUrl,wallUrl:d.wallUrl,cover:d.coverStatus}));
  }catch(e){
    d.status="manual_reconciliation_required";
    d.error=String(e?.message||e).slice(0,220);
    try{await checkpoint(d);}catch{}
    throw e;
  }
}
main().catch(e=>{console.error("::error::TABATA_VK "+String(e?.message||e).slice(0,260));process.exitCode=1;});
