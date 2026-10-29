/* Owner-approved single-shot 29 Oct 2026 Instagram Stories through BUFFER only.
 * Exactly one provider createPost per approved media item. Durable pre-call checkpoints.
 * Meta Graph API is used for READ-ONLY verification only, NEVER publication.
 */
import fs from "node:fs";
import crypto from "node:crypto";
import {execFileSync} from "node:child_process";
import {createInstagramPost,discoverChannel} from "../src/buffer.js";

const ROOT=process.cwd();
const MANIFEST="media-prep/bar-stories-20261029.json";
const QA="results/verification/bar-stories-20261029-stage.json";
const REQUEST="requests/campaigns/bar-stories-20261029-release.json";
const RECEIPT="results/campaigns/bar-stories-20261029-instagram-buffer.json";
const CHANNEL="6acde74d778b240e2ff489a7";
const PREFIX="https://raw.githubusercontent.com/lsevmos-gpt/ls-vk/main/";
const ORDER=["intro-bar","mojito","berry-smoothie"];
const MEDIA=[
  {id:"intro-bar",file:"media/bar-20261027-intro-vk.mp4",sha256:"1158b8e13b776740476522512843bf3b24bf4a78a764fcdcc693dadf85af1d7b"},
  {id:"mojito",file:"media/bar-20261029-mojito-original.mp4",sha256:"7ffe565a9201f92108643e88d55cd23e03424ee6c9c17dc9380739e7b3c6791f"},
  {id:"berry-smoothie",file:"media/bar-20261021-berry-v2-original.mp4",sha256:"edc6d12b52992e66b730dc4c925906288855822968f2f500a4a63980d1ee48fb"}
];
const stamp=()=>new Date().toISOString();
const sleep=ms=>new Promise(ok=>setTimeout(ok,ms));
function git(...args){
  try{execFileSync("git",args,{cwd:ROOT,timeout:100000,stdio:"pipe"});}
  catch(e){throw Error("Git "+args.slice(0,2).join(" ")+" failed: "+String(e?.stderr||e).slice(-330));}
}
function hash(p){return crypto.createHash("sha256").update(fs.readFileSync(p)).digest("hex");}
async function commitReceipt(rec,first=false){
  rec.updatedAtUTC=stamp();
  fs.mkdirSync("results/campaigns",{recursive:true});
  fs.writeFileSync(RECEIPT,JSON.stringify(rec,null,2)+"\n",first?{flag:"wx"}:undefined);
  git("add","--",RECEIPT);
  git("commit","-m","29 Oct Buffer bar story: "+rec.status+" [skip ci]");
  for(let retry=0;retry<4;retry++){
    try{
      git("pull","--rebase","origin","main");
      git("push","origin","HEAD:main");
      console.log("BUFFER_RECEIPT",rec.status,"count",rec.posts.length);
      return;
    }catch(e){if(retry===3)throw e;await sleep((retry+1)*1000);}
  }
}
async function readBuffer(id){
  const query="query ReadOneBufferPost($input: PostInput!) { post(input: $input) { id status sentAt dueAt channelId } }";
  const r=await fetch("https://api.buffer.com",{
    method:"POST",
    headers:{"content-type":"application/json",authorization:"Bearer "+process.env.BUFFER_API_KEY},
    body:JSON.stringify({query,variables:{input:{id}}})
  });
  const j=await r.json().catch(()=>null);
  if(!r.ok || !j || j.errors?.length || !j.data?.post)
    throw Error("Buffer read-only post query unavailable; HTTP "+r.status+": "+String(j?.errors?.[0]?.message||"missing post").slice(0,140));
  if(j.data.post.id!==id||j.data.post.channelId!==CHANNEL)
    throw Error("Buffer post readback identity mismatch");
  return j.data.post;
}
async function liveStories(){
  if(!process.env.META_IG_ACCESS_TOKEN||!process.env.META_IG_USER_ID)return null;
  try {
    const url=new URL("https://graph.facebook.com/v26.0/"+process.env.META_IG_USER_ID+"/stories");
    url.searchParams.set("fields","id,media_type,timestamp,permalink");
    url.searchParams.set("limit","100");
    const r=await fetch(url,{headers:{Authorization:"Bearer "+process.env.META_IG_ACCESS_TOKEN}});
    const j=await r.json().catch(()=>null);
    if(!r.ok||j?.error||!Array.isArray(j?.data))throw Error("Meta GET unavailable "+r.status);
    return j.data.filter(s=>s?.id);
  }catch(e){console.warn("READ_ONLY_META_UNAVAILABLE",String(e?.message||e).slice(0,130));return null;}
}
async function preflight(){
  if(process.env.GITHUB_REPOSITORY!=="lsevmos-gpt/ls-vk" ||
     process.env.GITHUB_REF!=="refs/heads/main" ||
     process.env.GITHUB_ACTOR!=="lsevmos-gpt" ||
     process.env.GITHUB_EVENT_NAME!=="push" ||
     !/^\d+$/.test(process.env.GITHUB_RUN_ID||""))
      throw Error("Unauthorized repository/actor/event");
  if(!process.env.BUFFER_API_KEY)throw Error("BUFFER_API_KEY missing");
  git("pull","--ff-only","origin","main");
  if(fs.existsSync(RECEIPT))throw Error("Buffer Instagram attempt already exists; NO REPLAY");
  const m=JSON.parse(fs.readFileSync(MANIFEST,"utf8"));
  const qa=JSON.parse(fs.readFileSync(QA,"utf8"));
  const release=JSON.parse(fs.readFileSync(REQUEST,"utf8"));
  if(release.id!=="bar-stories-20261029-release" || release.approved!==true ||
     release.publicContent!==true || release.publishNow!==true ||
     release.instagramProvider!=="buffer" || release.instagram!=="liniya__sporta" ||
     release.vkGroupId!==48198173 ||
     JSON.stringify(release.stories)!==JSON.stringify(ORDER))throw Error("Unapproved release request");
  if(m.id!=="bar-stories-20261029"||m.approved!==true||m.publicContent!==true||
     m.instagramProvider!=="buffer"||m.instagram!=="liniya__sporta"||m.vkGroupId!==48198173||
     qa.id!==m.id||qa.ok!==true||qa.sourceOriginalsVerified!==true||
     qa.videoAndAudioNotReencoded!==true||
     qa.instagramChannelId!==CHANNEL||qa.vkGroupId!==48198173||
     JSON.stringify(qa.order)!==JSON.stringify(ORDER)||
     JSON.stringify(m.sequence.map(s=>s.id))!==JSON.stringify(ORDER)||
     qa.files.length!==3)throw Error("Staged media QA/approval mismatch");
  for(let i=0;i<3;i++){
    const a=MEDIA[i],source=m.sequence[i],q=qa.files[i];
    if(q.id!==a.id||q.media!==a.file||q.sha256!==a.sha256||source.sha256!==a.sha256||
       source.file!==a.file||q.sizeBytes!==source.bytes)
      throw Error("Approved media mapping mismatch for "+a.id);
    if(!fs.statSync(a.file).isFile()||hash(a.file)!==a.sha256||fs.statSync(a.file).size!==q.sizeBytes)
      throw Error("Source bytes changed for "+a.id);
    if(q.resolution!=="1080x1920"||q.fps!==24||q.audioCodec!=="aac"||
       q.durationSeconds>=15||q.durationSeconds<3)
      throw Error("Media incompatible with Stories: "+a.id);
    const res=await fetch(PREFIX+a.file,{method:"HEAD"});
    if(!res.ok)throw Error("Public Buffer media URL unavailable "+a.id+": HTTP "+res.status);
  }
  const resolved=await discoverChannel({service:"instagram",handle:"liniya__sporta"});
  if(resolved.channel.id!==CHANNEL||resolved.channel.isQueuePaused)
    throw Error("Buffer channel ID mismatched or queue paused");
  return {qa,baseline:await liveStories()};
}
async function main(){
  if(fs.existsSync(RECEIPT)){console.log("Prior Buffer attempt receipt exists; no replay");return;}
  const {qa,baseline}=await preflight();
  git("config","user.name","ls-buffer-stories-once");
  git("config","user.email","41898282+github-actions[bot]@users.noreply.github.com");
  git("pull","--ff-only","origin","main");
  if(fs.existsSync(RECEIPT)){console.log("Another actor reserved Buffer Stories; no replay");return;}
  const known=new Set((baseline||[]).map(s=>String(s.id)));
  const rec={id:"bar-stories-20261029-instagram-buffer",provider:"buffer",account:"liniya__sporta",
    channelId:CHANNEL,runId:process.env.GITHUB_RUN_ID,status:"reserved_before_provider_call",
    createdAtUTC:stamp(),order:ORDER,originalHashes:qa.files.map(x=>x.sha256),
    posts:[],baselineMetaStoryIds:[...known],providerCreateAttempts:0,
    note:"Exactly 3 approved Stories through Buffer. No retry of provider submission."};
  await commitReceipt(rec,true);
  for(let i=0;i<MEDIA.length;i++){
    const item=MEDIA[i];
    let acceptedPostId=null;
    try{
      rec.status="submitting_to_buffer";rec.attemptingIndex=i+1;rec.attemptingItem=item.id;
      rec.providerCreateAttempts++;
      await commitReceipt(rec); // persisted before irreversible Buffer createPost
      const post=await createInstagramPost({
        channelId:CHANNEL,text:"",postType:"story",
        media:[{type:"video",url:PREFIX+item.file}],
        publishNow:true,shouldShareToFeed:false,isAiGenerated:true
      });
      if(!post?.id||post.channelId!==CHANNEL)throw Error("Buffer createPost returned no valid post/channel id");
      acceptedPostId=post.id;
      const row={index:i+1,name:item.id,sourceSHA256:item.sha256,
        bufferPostId:String(post.id),bufferInitialStatus:post.status,acceptedAtUTC:stamp()};
      rec.posts.push(row);
      rec.status="buffer_accepted";delete rec.attemptingIndex;delete rec.attemptingItem;
      await commitReceipt(rec);
      let sent=null;
      for(let k=0;k<35;k++){
        const p=await readBuffer(post.id);
        console.log("BUFFER_READBACK",i+1,item.id,k,p.status);
        if(String(p.status).toLowerCase()==="sent"){sent=p;break;}
        if(["failed","error","rejected","cancelled","canceled"].includes(String(p.status).toLowerCase()))
          throw Error("Buffer terminal status "+p.status+" on "+item.id);
        await sleep(8000);
      }
      if(!sent)throw Error("Buffer SENT not confirmed within 280s. Do not retry or submit next Story.");
      row.bufferFinalStatus="sent";row.sentAtUTC=sent.sentAt||stamp();
      rec.status=i===2?"buffer_sent_all_three":"buffer_sent_partial";
      await commitReceipt(rec);
      // Meta is read-only here. Match precisely one newly visible VIDEO story,
      // otherwise leave live attribution unknown rather than guessing.
      for(let wait=0;wait<9;wait++){
        const live=await liveStories();
        if(live){
          const candidates=live.filter(s=>!known.has(String(s.id)) && String(s.media_type)==="VIDEO");
          if(candidates.length===1){
            const candidate=candidates[0];
            row.metaStoryId=String(candidate.id);
            row.permalink=candidate.permalink||null;
            row.metaReadbackConfirmed=true;
            row.metaTimestamp=candidate.timestamp||null;
            known.add(String(candidate.id));
            rec.status=i===2?"buffer_sent_all_three_live_verified":"buffer_sent_partial_live_verified";
            await commitReceipt(rec);
            break;
          }
          if(candidates.length>1){rec.readbackAmbiguity="Multiple unassigned live VIDEO stories; no guessing";break;}
        }
        await sleep(5000);
      }
      if(i<2)await sleep(2500);
    }catch(err){
      rec.status="manual_reconciliation_required";
      rec.error=String(err?.message||err).slice(0,350);
      rec.note="Stop on first uncertain Buffer response. Never replay or publish remaining items without read-only reconciliation.";
      rec.lastAttemptedBufferPostId=acceptedPostId;
      try{await commitReceipt(rec);}catch(inner){console.error("DURABLE_PRECALL_RECEIPT_EXISTS; FINAL_CHECKPOINT_FAILED",String(inner?.message||inner).slice(0,200));}
      throw err;
    }
  }
  rec.status=rec.posts.length===3 && rec.posts.every(x=>x.metaReadbackConfirmed)
    ?"published_three_meta_readback_confirmed":"buffer_sent_three_meta_readback_partial";
  await commitReceipt(rec);
  console.log("BUFFER_THREE_STORIES_FINAL",JSON.stringify({status:rec.status,posts:rec.posts.map(x=>({name:x.name,id:x.bufferPostId,liveId:x.metaStoryId||null,permalink:x.permalink||null}))}));
}
main().catch(e=>{
  console.error("::error::BUFFER_BAR_20261029 "+String(e?.message||e).slice(0,360));
  process.exitCode=1;
});