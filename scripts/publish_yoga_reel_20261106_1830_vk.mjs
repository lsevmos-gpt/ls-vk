/* 6 Nov Yoga VK Clip: authorized WITHOUT native coauthor; one upload + one wall post.
   Uses the proven same-runner VK ID refresh flow; no modifications to Instagram job. */
import fs from 'node:fs';
import {execFileSync, spawnSync} from 'node:child_process';
import {randomBytes, createHash} from 'node:crypto';
import {buildVkRefreshRequest, parseVkRefreshResponse, readOnlyVkTokenCheck} from './vk-refresh-lib.mjs';

const REPO='lsevmos-gpt/ls-vk';
const GROUP=48198173;
const JOB='yoga-reel-20261106-1830-vk';
const REQUEST='requests/campaigns/'+JOB+'.json';
const CAMPAIGN='requests/campaigns/yoga-reel-20261106-1830.json';
const QA='results/verification/yoga-reel-20261103-2k.json';
const VIDEO='media/yoga-reel-20261103-2k-ig-vk.mp4';
const RECEIPT='results/campaigns/'+JOB+'.json';
const EXPECTED_SHA='d225a0b0f5598e9c9a0a40d9a77d0828acdd8cdde63c31511a48c0bd035388ec';
const READY_FROM=Date.parse('2026-11-06T14:50:00Z'); // 17:50 MSK: prepare VK upload
const PUBLISH_AT=Date.parse('2026-11-06T15:30:00Z'); // 18:30 MSK
const DEADLINE=Date.parse('2026-11-06T15:45:00Z'); // don't publish too late
const wait=ms=>new Promise(r=>setTimeout(r,ms));
const iso=()=>new Date().toISOString();
function git(...args){
  try{return execFileSync('git',args,{encoding:'utf8',stdio:'pipe',timeout:100000}).trim()}
  catch(e){throw Error('GIT_FAILED '+args.slice(0,2).join(' ')+' '+String(e.stderr||e).slice(-170))}
}
function hashFile(file){return createHash('sha256').update(fs.readFileSync(file)).digest('hex')}
function required(name){const v=process.env[name];if(!v?.trim())throw Error('MISSING_'+name);return v.trim()}
async function awaitTime(time){
  while(Date.now()<time)await wait(Math.min(12000,time-Date.now()));
}
async function checkpoint(doc,first=false){
  doc.updatedAtUTC=iso();
  fs.mkdirSync('results/campaigns',{recursive:true});
  fs.writeFileSync(RECEIPT,JSON.stringify(doc,null,2)+'\n',first?{flag:'wx'}:{});
  git('add','--',RECEIPT);
  git('commit','-m','Record Yoga VK Clip '+doc.status+' [skip ci]');
  for(let i=0;i<8;i++){
    try{git('pull','--rebase','origin','main');git('push','origin','HEAD:main');return}
    catch(e){if(i===7)throw Error('RECEIPT_PERSIST_FAILED');await wait(1000*(i+1))}
  }
}
function secretWrite(args,value,pat){
  const proc=spawnSync('gh',args,{input:value,encoding:'utf8',timeout:35000,maxBuffer:65536,
    env:{PATH:process.env.PATH||'',HOME:process.env.HOME||'',GH_TOKEN:pat,GH_HOST:'github.com',CI:'true'}});
  if(proc.status!==0||proc.error)throw Error('GITHUB_SECRET_WRITE_FAILED');
}
async function refreshOnRunner(){
  const pat=required('VK_SECRETS_WRITE_PAT');
  const probe='VK_YOGA_REFRESH_PROBE_20261106';
  secretWrite(['secret','set',probe,'--repo',REPO],randomBytes(24).toString('base64url'),pat);
  try{secretWrite(['secret','delete',probe,'--repo',REPO],'',pat)}catch{}
  const state=randomBytes(24).toString('base64url');
  const r=buildVkRefreshRequest({clientId:'54806879',redirectUri:'https://vk.liniyasporta.ru/oauth/callback',
    deviceId:required('VK_DEVICE_ID'),refreshToken:required('VK_REFRESH_TOKEN'),state});
  let response,payload;
  try{response=await fetch(r.url,r.options);payload=await response.json().catch(()=>null)}
  catch{throw Error('VK_REFRESH_NETWORK_FAILED')}
  if(!response.ok)throw Error('VK_REFRESH_HTTP_'+response.status);
  const tokens=parseVkRefreshResponse(payload,state);
  // Persist rotated token before any VK API mutation.
  secretWrite(['secret','set','VK_REFRESH_TOKEN','--repo',REPO],tokens.refreshToken,pat);
  const check=await readOnlyVkTokenCheck(tokens.accessToken,'54806879');
  if(check.vkId!=='OK'||check.vkApiUsers!=='OK'||!check.vkApiAllowed){
    throw Error('VK_REFRESHED_TOKEN_VIDEO_SCOPE_UNAVAILABLE');
  }
  console.log('VK_YOGA_SAME_RUNNER_REFRESH_OK_VIDEO_SCOPE_YES');
  return tokens.accessToken;
}
function readApproval(){
  if(process.env.GITHUB_REPOSITORY!==REPO||process.env.GITHUB_REF!=='refs/heads/main'
      ||process.env.GITHUB_EVENT_NAME!=='schedule'||!(/^\d+$/.test(process.env.GITHUB_RUN_ID||''))){
    throw Error('UNAUTHORIZED_SCHEDULE_CONTEXT');
  }
  if(Date.now()>DEADLINE)throw Error('YOGA_RELEASE_WINDOW_EXPIRED_NO_PUBLISH');
  const request=JSON.parse(fs.readFileSync(REQUEST,'utf8'));
  const campaign=JSON.parse(fs.readFileSync(CAMPAIGN,'utf8'));
  const qa=JSON.parse(fs.readFileSync(QA,'utf8'));
  if(!(request.id===JOB && request.approved===true && request.publicContent===true &&
    request.scheduledFor==='2026-11-06T18:30:00+03:00' &&
    request.vkGroupId===GROUP && request.postToWall===true &&
    request.noCollaborator===true && request.authorizedByUser===true &&
    request.videoPath===VIDEO && request.videoSHA256===EXPECTED_SHA &&
    campaign.id==='yoga-reel-20261106-1830' && campaign.approved===true &&
    campaign.instagram.account==='liniya__sporta' &&
    JSON.stringify(campaign.instagram.collaborators)==='["sir_ena06"]' &&
    campaign.scheduledFor===request.scheduledFor &&
    request.caption===campaign.caption &&
    qa.id==='yoga-reel-20261103' && qa.ok===true &&
    qa.stagingOnly===true && qa.sourceSHA256===campaign.sourceSHA256 &&
    qa.videoPath===VIDEO && qa.videoSHA256===EXPECTED_SHA && qa.videoBytes===90609020 &&
    qa.videoResolution==='1440x2560' && Math.abs(qa.videoFps-25)<0.01 &&
    qa.videoCodec==='h264' && qa.audioCodec==='aac' &&
    fs.existsSync(VIDEO) && fs.statSync(VIDEO).size===qa.videoBytes &&
    hashFile(VIDEO)===EXPECTED_SHA)){
    throw Error('APPROVAL_SOURCE_CAPTION_OR_2K_SHA_MISMATCH');
  }
  required('VK_GROUP_TOKEN'); required('VK_REFRESH_TOKEN'); required('VK_DEVICE_ID'); required('VK_SECRETS_WRITE_PAT');
  return request;
}
async function main(){
  git('pull','--ff-only','origin','main');
  if(fs.existsSync(RECEIPT)){
    console.log('YOGA_VK_ALREADY_RESERVED_OR_PUBLISHED_NO_RETRY');return;
  }
  const request=readApproval();
  console.log('YOGA_VK_APPROVED_2K_SHA_NO_COAUTHOR_READINESS_OK');
  await awaitTime(READY_FROM);
  if(Date.now()>DEADLINE)throw Error('YOGA_RELEASE_WINDOW_EXPIRED_BEFORE_UPLOAD');
  git('config','user.name','ls-yoga-vk-publisher');
  git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com');
  const accessToken=await refreshOnRunner();
  process.env.VK_USER_TOKEN=accessToken;
  // Import AFTER refreshing: src/config.js snapshots env when loaded.
  const {getGroupId,vkCall,uploadWallVideo,publishWallPost}=await import('../src/vk.js');
  if(Number(await getGroupId())!==GROUP)throw Error('WRONG_VK_GROUP_ID');
  const groups=await vkCall('groups.getById',{group_id:GROUP},process.env.VK_GROUP_TOKEN);
  const group=Array.isArray(groups?.groups)?groups.groups[0]:Array.isArray(groups)?groups[0]:groups;
  if(Number(group?.id)!==GROUP||group?.screen_name!=='liniya__sporta')throw Error('WRONG_VK_GROUP_IDENTITY');
  git('pull','--ff-only','origin','main');
  if(fs.existsSync(RECEIPT)){console.log('YOGA_VK_RACE_ALREADY_RESERVED_NO_REPEAT');return}
  const doc={id:JOB,provider:'vk',account:'liniya__sporta',groupId:GROUP,
    type:'clip',videoPath:VIDEO,videoSHA256:EXPECTED_SHA,videoResolution:'1440x2560',
    original2KStreamUnchanged:true,noCoauthorRequested:true,postToWall:true,
    scheduledFor:request.scheduledFor,caption:request.caption,
    runId:process.env.GITHUB_RUN_ID,status:'reserved_before_provider_upload',
    videoId:null,wallPostId:null,noRetries:true,createdAtUTC:iso(),
    coverNote:'Custom VK cover not set through API; do not claim original cover applied'};
  await checkpoint(doc,true);
  try{
    doc.status='video_save_upload_started';await checkpoint(doc);
    const uploaded=await uploadWallVideo({path:VIDEO,originalname:'yoga-liniya-sporta-1440x2560.mp4',mimetype:'video/mp4'},
      {name:'Йога — Линия спорта',description:request.caption});
    const videoId=Number(uploaded?.video?.id);
    const ownerId=Number(uploaded?.video?.owner_id);
    if(!Number.isSafeInteger(videoId)||videoId<=0||ownerId!==-GROUP||!uploaded.attachment){
      throw Error('VK_VIDEO_UPLOAD_UNCONFIRMED');
    }
    doc.videoId=videoId;doc.videoOwnerId=ownerId;doc.attachment=uploaded.attachment;
    doc.videoUrl='https://vk.com/video'+ownerId+'_'+videoId;
    doc.status='video_uploaded_api_confirmed';doc.uploadedAtUTC=iso();await checkpoint(doc);
    console.log('YOGA_VK_VIDEO_API_ACCEPTED',JSON.stringify({videoId,videoUrl:doc.videoUrl}));
    await awaitTime(PUBLISH_AT);
    if(Date.now()>DEADLINE)throw Error('VK_WALL_RELEASE_DEADLINE_MISSED_NO_POST');
    doc.status='wall_post_call_started';await checkpoint(doc);
    const post=await publishWallPost({text:request.caption,attachments:[uploaded.attachment]});
    const postId=Number(post?.post_id);
    if(!Number.isSafeInteger(postId)||postId<=0)throw Error('VK_WALL_POST_ID_UNKNOWN_NO_RETRY');
    doc.wallPostId=postId;doc.wallUrl='https://vk.com/wall-'+GROUP+'_'+postId;
    doc.status='vk_video_wall_api_accepted';doc.postedAtUTC=iso();await checkpoint(doc);
    let wallSeen=false,videoSeen=false;
    for(let i=0;i<5;i++){
      try{
        const x=await vkCall('wall.getById',{posts:'-'+GROUP+'_'+postId},accessToken);
        const items=Array.isArray(x?.items)?x.items:Array.isArray(x)?x:[];
        wallSeen=items.some(p=>Number(p?.id)===postId&&Number(p?.owner_id)===-GROUP);
      }catch(e){doc.wallReadbackErrorClass=e?.name||'VkError'}
      try{
        const x=await vkCall('video.get',{videos:String(ownerId)+'_'+videoId},accessToken);
        videoSeen=Array.isArray(x?.items)&&x.items.some(v=>Number(v?.id)===videoId&&Number(v?.owner_id)===ownerId);
      }catch(e){doc.videoReadbackErrorClass=e?.name||'VkError'}
      if(wallSeen&&videoSeen)break;
      if(i<4)await wait(3000);
    }
    doc.videoReadbackConfirmed=videoSeen;doc.wallReadbackConfirmed=wallSeen;
    doc.status=wallSeen&&videoSeen?'published_verified_by_vk':'vk_api_accepted_readback_partial';
    await checkpoint(doc);
    console.log('YOGA_VK_FINAL',JSON.stringify({status:doc.status,videoId,wallPostId:postId,
      videoReadbackConfirmed:videoSeen,wallReadbackConfirmed:wallSeen,videoUrl:doc.videoUrl,wallUrl:doc.wallUrl}));
  }catch(e){
    doc.status='manual_reconciliation_required';doc.error=String(e?.message||e).slice(0,240);
    doc.note='Partial upload or wall post possible; never blindly retry';
    try{await checkpoint(doc)}catch(x){console.error('YOGA_VK_RECEIPT_ERROR',String(x).slice(0,120))}
    throw e;
  }
}
main().catch(e=>{
  const msg=String(e?.message||e);
  const safe=/^(YOGA_|VK_|WRONG_|MISSING_|UNAUTHORIZED_|APPROVAL_|GIT_|RECEIPT_)/.test(msg)
    ?msg.slice(0,250):String(e?.name||'UnknownError');
  console.error('::error::YOGA_VK_CLIP '+safe);
  process.exitCode=1;
});