/* Explicitly approved single Coach Day image Story: Instagram via Buffer only, 30 Oct 2026. */
import fs from 'node:fs';
import crypto from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {createInstagramPost,discoverChannel} from '../src/buffer.js';
const MEDIA='media/coach-day-20261030-original.png';
const SHA='96fadda082d858c6f40c637263dd11f134236dfb8dc9dcb917e1fc148f05a345';
const SIZE=3563841;
const CHANNEL='6acde74d778b240e2ff489a7';
const URL='https://raw.githubusercontent.com/lsevmos-gpt/ls-vk/main/'+MEDIA;
const RECEIPT='results/campaigns/coach-day-20261030-buffer-instagram.json';
const pause=ms=>new Promise(ok=>setTimeout(ok,ms));
const stamp=()=>new Date().toISOString();
const git=(...args)=>execFileSync('git',args,{timeout:90000,stdio:'pipe'});
async function checkpoint(obj,first=false){
  obj.updatedAtUTC=stamp();
  fs.mkdirSync('results/campaigns',{recursive:true});
  fs.writeFileSync(RECEIPT,JSON.stringify(obj,null,2)+'\n',first?{flag:'wx'}:undefined);
  git('add','--',RECEIPT);
  git('commit','-m','Coach Day Buffer Instagram Story: '+obj.status+' [skip ci]');
  for(let i=0;i<5;i++){
    try {git('pull','--rebase','origin','main');git('push','origin','HEAD:main');return}
    catch(e){if(i===4)throw e;await pause(1000*(i+1))}
  }
}
async function metaStories(){
  if(!process.env.META_IG_ACCESS_TOKEN||!process.env.META_IG_USER_ID)return null;
  try {
    const u=new URL('https://graph.facebook.com/v26.0/'+process.env.META_IG_USER_ID+'/stories');
    u.searchParams.set('fields','id,media_type,timestamp,permalink');u.searchParams.set('limit','100');
    const r=await fetch(u,{headers:{Authorization:'Bearer '+process.env.META_IG_ACCESS_TOKEN}});
    const j=await r.json();
    if(!r.ok||j.error||!Array.isArray(j.data))throw Error('Meta GET unavailable');
    return j.data;
  } catch(e){console.log('META_READ_ONLY_UNAVAILABLE',String(e.message).slice(0,110));return null}
}
async function bufferRead(id){
  const query='query FetchBufferPost($input: PostInput!) { post(input: $input) { id status sentAt dueAt channelId } }';
  const r=await fetch('https://api.buffer.com',{method:'POST',headers:{
    authorization:'Bearer '+process.env.BUFFER_API_KEY,'content-type':'application/json'
  },body:JSON.stringify({query,variables:{input:{id}}})});
  const j=await r.json();
  if(!r.ok||j.errors?.length||!j.data?.post)throw Error('Buffer readback failed HTTP '+r.status);
  if(j.data.post.id!==id||j.data.post.channelId!==CHANNEL)throw Error('Buffer identity mismatch');
  return j.data.post;
}
async function main(){
  if(process.env.GITHUB_REPOSITORY!=='lsevmos-gpt/ls-vk'||
     process.env.GITHUB_ACTOR!=='lsevmos-gpt'||
     process.env.GITHUB_REF!=='refs/heads/main'||
     process.env.GITHUB_EVENT_NAME!=='push')throw Error('Unapproved GitHub context');
  if(Date.now()<Date.parse('2026-10-30T00:00:00+03:00')||
     Date.now()>=Date.parse('2026-10-31T00:00:00+03:00'))throw Error('Only on Coach Day 30 Oct MSK');
  if(!process.env.BUFFER_API_KEY)throw Error('BUFFER_API_KEY absent');
  git('pull','--ff-only','origin','main');
  if(fs.existsSync(RECEIPT)) {console.log('Prior Buffer attempt: NO DUPLICATE');return}
  if(!fs.existsSync(MEDIA)||fs.statSync(MEDIA).size!==SIZE||
    crypto.createHash('sha256').update(fs.readFileSync(MEDIA)).digest('hex')!==SHA)
    throw Error('Source original bytes not verified');
  let available=false;
  for(let i=0;i<12;i++){try{const r=await fetch(URL,{method:'HEAD'});if(r.ok){available=true;break}}catch(e){}await pause(3000)}
  if(!available)throw Error('Public original media URL unavailable to Buffer');
  const target=await discoverChannel({service:'instagram',handle:'liniya__sporta'});
  if(target.channel.id!==CHANNEL||target.channel.isQueuePaused)throw Error('Wrong or paused Buffer channel');
  const before=await metaStories();
  const known=new Set((before||[]).map(x=>String(x.id)));
  git('config','user.name','ls-coach-day-buffer-once');
  git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com');
  git('pull','--ff-only','origin','main');
  if(fs.existsSync(RECEIPT)){console.log('Another Buffer run already reserved');return}
  const rec={id:'coach-day-20261030-buffer-instagram',provider:'buffer',
    account:'liniya__sporta',channelId:CHANNEL,runId:process.env.GITHUB_RUN_ID,
    source:MEDIA,sourceSha256:SHA,sourceBytes:SIZE,mediaType:'image/png',
    resolution:'1080x1920',postType:'story',approved:true,withLinks:false,
    createdAtUTC:stamp(),status:'reserved_before_provider_call',providerCreateAttempts:0,
    baselineMetaStoryIds:[...known]};
  await checkpoint(rec,true);
  try{
    rec.status='submitting_to_buffer';rec.providerCreateAttempts=1;
    await checkpoint(rec);
    const p=await createInstagramPost({channelId:CHANNEL,text:'',postType:'story',
      media:[{type:'image',url:URL}],publishNow:true,shouldShareToFeed:false,isAiGenerated:true});
    if(!p?.id||p.channelId!==CHANNEL)throw Error('Buffer post ID/channel invalid');
    rec.bufferPostId=p.id;rec.bufferInitialStatus=p.status;rec.status='buffer_accepted';
    await checkpoint(rec);
    let sent=null;
    for(let i=0;i<38;i++){
      const q=await bufferRead(p.id);
      console.log('BUFFER_STORY_STATUS',i,q.status);
      if(q.status==='sent'){sent=q;break}
      if(['failed','error','rejected','cancelled','canceled'].includes(String(q.status).toLowerCase()))
        throw Error('Buffer terminal status '+q.status);
      await pause(8000);
    }
    if(!sent)throw Error('Buffer has not confirmed sent; no retry allowed');
    rec.bufferFinalStatus='sent';rec.bufferSentAt=sent.sentAt||stamp();
    rec.status='buffer_sent_meta_verification_pending';await checkpoint(rec);
    for(let i=0;i<15;i++){
      const now=await metaStories();
      if(now){
        const fresh=now.filter(x=>!known.has(String(x.id))&&x.media_type==='IMAGE'&&
          Date.parse(x.timestamp||'')>=Date.parse(rec.createdAtUTC)-20000);
        if(fresh.length===1){
          rec.metaStoryId=String(fresh[0].id);
          rec.permalink=fresh[0].permalink||null;
          rec.metaTimestamp=fresh[0].timestamp||null;
          rec.status='published_meta_readback_confirmed';
          await checkpoint(rec);break;
        }
        if(fresh.length>1){rec.metaReadbackAmbiguous=true;break}
      }
      await pause(5000);
    }
    console.log('COACH_DAY_INSTAGRAM_FINAL',JSON.stringify({
      status:rec.status,postId:rec.bufferPostId,storyId:rec.metaStoryId||null,
      permalink:rec.permalink||null
    }));
  }catch(e){
    rec.status='manual_reconciliation_required';rec.error=String(e.message).slice(0,350);
    try{await checkpoint(rec)}catch(ce){console.log('FINAL_RECEIPT_ERROR',String(ce).slice(0,200))}
    throw e;
  }
}
main().catch(e=>{console.error('::error::COACH_DAY_BUFFER',String(e.message).slice(0,360));process.exitCode=1});
