// One-time, fail-closed release of the public first-visit Reel and VK Clip.
// Uses original video bytes by public URL; never transcodes or uploads secrets.
// A durable Git marker is pushed BEFORE any provider-side submission.
import fs from "node:fs/promises";
import { spawnSync } from "node:child_process";
import path from "node:path";
const ROOT=process.cwd();
const DUE=Date.parse("2026-10-18T08:30:00Z");
const REPO="lsevmos-gpt/ls-vk";
const JOBS=[
  {provider:"buffer",id:"first-visit-20261018-1130-ig",
   manifest:"requests/buffer/first-visit-20261018-1130-ig.json",
   script:"scripts/buffer-job.js",receipt:"buffer-results/first-visit-20261018-1130-ig.json"},
  {provider:"vk",id:"first-visit-20261018-1130-vk",
   manifest:"requests/vk/first-visit-20261018-1130-vk.json",
   script:"scripts/publish-job.js",receipt:"results/first-visit-20261018-1130-vk.json"}
];
if(process.env.GITHUB_REPOSITORY!==REPO || process.env.GITHUB_REF!=="refs/heads/main"){
  throw new Error("Repository or branch mismatch");
}
function command(cmd,args,opts={}){
  const r=spawnSync(cmd,args,{cwd:ROOT,encoding:"utf8",maxBuffer:1024*1024*8,timeout:9*60*1000,...opts});
  if(r.error || r.status!==0) {
    const detail=(r.stderr||r.stdout||String(r.error)||"").slice(-2200);
    throw new Error(cmd+" "+args[0]+" failed: "+detail);
  }
  return r.stdout||"";
}
const git=(...args)=>command("git",args);
const relative=(p)=>path.join(ROOT,p);
async function exists(p){try{await fs.access(relative(p));return true}catch{return false}}
async function saveMarker(provider, content, message) {
  const rel="results/first-visit-20261018/"+provider+".json";
  await fs.mkdir(path.dirname(relative(rel)),{recursive:true});
  await fs.writeFile(relative(rel),JSON.stringify(content,null,2)+"\n");
  git("add","--",rel);
  git("commit","-m",message+" [skip ci]");
  git("pull","--rebase","origin","main");
  git("push","origin","HEAD:main");
}
async function submit(job){
  git("pull","--ff-only","origin","main");
  const target="results/first-visit-20261018/"+job.provider+".json";
  if(await exists(target)) {
    console.log(job.provider+": existing durable receipt; not submitting again");
    return;
  }
  const req=JSON.parse(await fs.readFile(relative(job.manifest),"utf8"));
  if(req.id!==job.id || req.approved!==true || req.publicContent!==true) throw new Error(job.provider+": manifest not approved");
  if(Date.now()>=DUE-10*1000) {console.log(job.provider+": too late for target time; NOT publishing late");return}
  if(job.provider==="buffer"){
    if(!process.env.BUFFER_API_KEY) {console.log("INSTAGRAM_BLOCKED: Buffer key absent");return}
    if(req.postType!=="reel" || req.publishNow!==false || Date.parse(req.dueAt)!==DUE || req.handle!=="liniya__sporta") throw new Error("Invalid Instagram scheduling request");
  } else {
    if(!process.env.VK_USER_TOKEN) {console.log("VK_BLOCKED: compatible VK_USER_TOKEN missing; VK video upload cannot work");return}
    if(!process.env.VK_GROUP_TOKEN) {console.log("VK_BLOCKED: community token missing");return}
    if(req.type!=="clip" || Date.parse(req.publishAt)!==DUE) throw new Error("Invalid VK clip request");
  }
  const env={...process.env,SOCIAL_PLATFORM:job.provider};
  command("node",["scripts/check_social_targets.mjs"],{env});
  const at=new Date().toISOString();
  const reservation={id:job.id,provider:job.provider,status:"reserved_before_provider_call",
    scheduledAt:"2026-10-18T11:30:00+03:00",originalVideoSha256:"cda8649d129f60150d051c3e12fa07a210305966316cb45cb3c3d2cb6f3ca307",
    reservedAt:at,runId:process.env.GITHUB_RUN_ID||"",note:"Do not blindly retry any uncertain provider result."};
  await saveMarker(job.provider,reservation,"Reserve one-time first-visit "+job.provider+" submission");
  let result={...reservation,status:"provider_status_unknown",finishedAt:new Date().toISOString()};
  try {
    const run=spawnSync("node",[job.script,job.manifest],{cwd:ROOT,env,encoding:"utf8",maxBuffer:4*1024*1024,timeout:9*60*1000});
    const raw=await fs.readFile(relative(job.receipt),"utf8").catch(()=>null);
    const got=raw?JSON.parse(raw):null;
    if(run.error||run.status!==0||got?.ok!==true||got?.id!==job.id) throw new Error("provider process/receipt failed; status uncertain");
    if(job.provider==="buffer"){
      const p=got?.result?.post;
      if(!p?.id || Date.parse(p.dueAt)!==DUE) throw new Error("Buffer did not confirm exact dueAt and post ID");
      result={...result,status:"scheduled_in_buffer",postId:p.id,providerStatus:p.status,dueAt:p.dueAt,channelId:p.channelId};
    }else{
      const up=got?.result?.uploaded;
      const post=got?.result?.post;
      if(!up?.video?.id || !post?.post_id) throw new Error("VK did not confirm both video upload and scheduled wall post");
      result={...result,status:"submitted_to_vk",videoId:up.video.id,wallPostId:post.post_id};
    }
  }catch(e){result={...result,status:"manual_review_required",error:String(e.message).slice(0,450)}}
  result.finishedAt=new Date().toISOString();
  await saveMarker(job.provider,result,"Finalize one-time first-visit "+job.provider+" submission");
  console.log(job.provider+" "+result.status);
  if(result.status==="manual_review_required") throw new Error(job.provider+": check provider and receipt; NEVER blindly retry");
}
git("config","user.name","ls-social-bot");
git("config","user.email","41898282+github-actions[bot]@users.noreply.github.com");
for(const job of JOBS){
  try{await submit(job)}
  catch(e){console.error(job.provider+" failed: "+String(e.message).slice(0,600))}
}
