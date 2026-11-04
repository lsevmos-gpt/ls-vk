/* VK video upload: proven 27-Oct Shpagat workflow — refresh token and publish ON SAME GitHub runner.
   Exactly one Sofia clip, approved without collaborator, exact 1080x1920 original video bytes. */
import fs from 'node:fs';
import {execFileSync,spawnSync} from 'node:child_process';
import {randomBytes,createHash} from 'node:crypto';
import {buildVkRefreshRequest,parseVkRefreshResponse,readOnlyVkTokenCheck} from './vk-refresh-lib.mjs';

const ID="sofiya-bulatetskaya-20261104-vk-clip";
const REPO='lsevmos-gpt/ls-vk';
const REQUEST="requests/vk/sofiya-bulatetskaya-20261104-recovery.json";
const ORIGINAL="requests/campaigns/sofiya-bulatetskaya-20261104-vk-clip.json";
const QA="results/verification/sofiya-bulatetskaya-20261104-reel-qa.json";
const RECEIPT="results/campaigns/sofiya-bulatetskaya-20261104-vk-clip.json";
const FILE="media/sofiya-bulatetskaya-20261104-reel-meta.mp4";
const EXPECTED_VIDEO_SHA="eeef216d93c29b4f0ebcbeba8e763466c411adb7b1d0a1c96d06c5b01b30a072";
const GROUP=48198173;
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const iso=()=>new Date().toISOString();
function git(...args){
  try{return execFileSync('git',args,{encoding:'utf8',timeout:105000,stdio:'pipe'}).trim();}
  catch(err){throw Error('GIT '+args.slice(0,2).join(' ')+' FAILED '+String(err.stderr||err).slice(-160))}
}
function hashFile(file){return createHash('sha256').update(fs.readFileSync(file)).digest('hex')}
async function checkpoint(record,first=false){
  record.updatedAtUTC=iso();
  fs.mkdirSync('results/campaigns',{recursive:true});
  fs.writeFileSync(RECEIPT,JSON.stringify(record,null,2)+'\n',first?{flag:'wx'}:{});
  git('add','--',RECEIPT);
  git('commit','-m','Record Sofia VK Clip proven VK ID refresh publisher '+record.status+' [skip ci]');
  for(let i=0;i<7;i++){
    try{git('pull','--rebase','origin','main');git('push','origin','HEAD:main');return}
    catch(err){if(i===6)throw Error('GIT_RECEIPT_PERSIST_FAILED');await wait(1000*(i+1))}
  }
}
function required(name){
  const value=process.env[name];
  if(!value||!value.trim())throw Error('MISSING_'+name);
  return value.trim();
}
function ghSecret(args,value,pat){
  const out=spawnSync('gh',args,{input:value,encoding:'utf8',timeout:35000,maxBuffer:65536,
    env:{PATH:process.env.PATH||'',HOME:process.env.HOME||'',GH_TOKEN:pat,GH_HOST:'github.com',CI:'true'}});
  if(out.status!==0||out.error)throw Error('GITHUB_SECRET_WRITE_FAILED');
}
async function refreshOnSameRunner(){
  const pat=required('VK_SECRETS_WRITE_PAT');
  const probe='VK_SOFIYA_WRITE_PROBE_20261104';
  // Verify ability to persist rotated refresh token BEFORE contacting VK ID.
  ghSecret(['secret','set',probe,'--repo',REPO],randomBytes(24).toString('base64url'),pat);
  try{ghSecret(['secret','delete',probe,'--repo',REPO],'',pat)}catch{}
  console.log('VK_SAME_RUNNER_GITHUB_SECRET_PREFLIGHT=OK');
  const state=randomBytes(24).toString('base64url');
  const built=buildVkRefreshRequest({clientId:'54806879',
    redirectUri:'https://vk.liniyasporta.ru/oauth/callback',
    deviceId:required('VK_DEVICE_ID'),refreshToken:required('VK_REFRESH_TOKEN'),state});
  let response,payload;
  try{response=await fetch(built.url,built.options);payload=await response.json().catch(()=>null)}
  catch{throw Error('VK_REFRESH_NETWORK_FAILED')}
  if(!response.ok)throw Error('VK_REFRESH_HTTP_'+response.status);
  const tokens=parseVkRefreshResponse(payload,state);
  // Rotating token MUST be persisted before any VK API calls.
  ghSecret(['secret','set','VK_REFRESH_TOKEN','--repo',REPO],tokens.refreshToken,pat);
  console.log('VK_REFRESH_TOKEN_ROTATION_PERSISTED=YES');
  const check=await readOnlyVkTokenCheck(tokens.accessToken,'54806879');
  if(check.vkId!=='OK'||!check.vkApiAllowed)
     throw Error('VK_REFRESHED_TOKEN_NOT_AUTHORIZED_FROM_SAME_RUNNER');
  console.log('VK_SAME_RUNNER_REFRESH=ACCEPTED;VK_VIDEO_SCOPE=YES');
  return tokens.accessToken;
}
async function preflight(){
  if(process.env.GITHUB_REPOSITORY!==REPO ||
     process.env.GITHUB_REF!=='refs/heads/main' ||
     process.env.GITHUB_EVENT_NAME!=='push' ||
     process.env.GITHUB_ACTOR!=='lsevmos-gpt' ||
     !/^\d+$/.test(process.env.GITHUB_RUN_ID||''))
      throw Error('UNAUTHORIZED_RUN_CONTEXT');
  git('pull','--ff-only','origin','main');
  if(fs.existsSync(RECEIPT)){
    console.log('SOFIYA_VK_EXISTING_RECEIPT_DO_NOT_DUPLICATE');return null;
  }
  // User approved publishing now after the failed IP-bound token preflight.
  const req=JSON.parse(fs.readFileSync(REQUEST,'utf8'));
  const original=JSON.parse(fs.readFileSync(ORIGINAL,'utf8'));
  const qa=JSON.parse(fs.readFileSync(QA,'utf8'));
  const meta=JSON.parse(fs.readFileSync('results/instagram-meta/sofiya-bulatetskaya-20261104-reel.json','utf8'));
  if(req.id!==ID || !req.approved || !req.publicContent || !req.submitNow ||
     req.type!=='clip'||req.groupId!==GROUP||req.groupScreenName!=='liniya__sporta' ||
     req.postToWall!==true||req.noCollaborator!==true||
     req.publisher!=='shpagat-20261027-working-refresh' ||
     req.videoPath!==FILE||req.videoSHA256!==EXPECTED_VIDEO_SHA||req.videoBytes!==58890709 ||
     req.text!==original.description||req.text!==original.wallText||req.text!==meta.caption ||
     req.name!==original.name||
     original.nativeCollaborator.approvedToPublishWithoutCollaborator!==true ||
     original.nativeCollaborator.required!==false||
     meta.status!=='published_readback_confirmed' ||
     !qa.ok || !qa.videoStreamUnchanged || qa.videoPath!==FILE ||
     qa.videoSHA256!==EXPECTED_VIDEO_SHA||qa.videoBytes!==58890709 ||
     qa.videoWidth!==1080||qa.videoHeight!==1920||qa.fps!==25||
     qa.videoCodec!=='h264'||qa.audioCodec!=='aac' ||
     !fs.existsSync(FILE)||fs.statSync(FILE).size!==58890709||
     hashFile(FILE)!==EXPECTED_VIDEO_SHA)
       throw Error('EXACT_APPROVED_SOURCE_OR_NO_COAUTHOR_RELEASE_MISMATCH');
  // Verify local MP4 without any reencoding.
  const probe=spawnSync('ffprobe',['-v','error','-select_streams','v:0',
      '-show_entries','stream=width,height,codec_name,avg_frame_rate',
      '-of','csv=p=0',FILE],{encoding:'utf8',timeout:20000});
  if(probe.status!==0 || !(probe.stdout||'').includes('1080,1920'))
    throw Error('SOURCE_VIDEO_STREAM_FORMAT_INVALID');
  required('VK_GROUP_TOKEN');required('VK_REFRESH_TOKEN');required('VK_DEVICE_ID');
  required('VK_SECRETS_WRITE_PAT');
  console.log('SOFIYA_EXACT_APPROVED_1080P_SOURCE_AND_CAPTION_OK_NO_COLLABORATOR');
  return req;
}
async function main(){
  const req=await preflight();
  if(!req)return;
  git('config','user.name','ls-vk-sofiya-refresh-clip-one-shot');
  git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com');
  // Proven 27-Oct sequence: refresh + save rotating secret + video.save in same runner.
  const token=await refreshOnSameRunner();
  process.env.VK_USER_TOKEN=token;
  // IMPORTANT: import VK module only AFTER refreshing access token (src/config.js snapshots env).
  const {getGroupId,vkCall,uploadWallVideo,publishWallPost}=await import('../src/vk.js');
  const groupId=await getGroupId();
  if(Number(groupId)!==GROUP)throw Error('WRONG_VK_COMMUNITY');
  const groupRes=await vkCall('groups.getById',{group_id:GROUP},process.env.VK_GROUP_TOKEN);
  const group=Array.isArray(groupRes?.groups)?groupRes.groups[0]:Array.isArray(groupRes)?groupRes[0]:groupRes;
  if(Number(group?.id)!==GROUP||group?.screen_name!=='liniya__sporta')
    throw Error('WRONG_VK_COMMUNITY_IDENTITY');
  const users=await vkCall('users.get',{},token);
  if(!Array.isArray(users)||users.length===0)throw Error('REFRESHED_VK_USER_INVALID');
  git('pull','--ff-only','origin','main');
  if(fs.existsSync(RECEIPT)){console.log('SOFIYA_VK_ALREADY_RESERVED_NO_REPLAY');return;}
  const record={id:ID,provider:'vk',type:'clip',groupId:GROUP,runId:process.env.GITHUB_RUN_ID,
    status:'reserved_before_provider_mutation',videoPath:FILE,videoSHA256:EXPECTED_VIDEO_SHA,
    videoResolution:'1080x1920',h264Unchanged:true,caption:req.text,
    noCoauthorRequested:true,createdAtUTC:iso(),
    refreshScheme:'27-oct-shpagat-same-runner-vkid',videoId:null,wallPostId:null,
    coverNote:'Original approved cover stored; platform cover upload not configured; do not claim custom VK thumbnail was applied',
    note:'Exactly one provider video upload and one wall post. Never retry if outcome uncertain'};
  await checkpoint(record,true);
  try{
    record.status='video_save_and_upload_started';await checkpoint(record);
    const uploaded=await uploadWallVideo({path:FILE,originalname:'sofiya-bulatetskaya-1080x1920.mp4',mimetype:'video/mp4'},
      {name:req.name,description:req.text});
    const videoId=Number(uploaded?.video?.id);
    const ownerId=Number(uploaded?.video?.owner_id);
    if(!Number.isSafeInteger(videoId)||videoId<=0||ownerId!==-GROUP||!uploaded?.attachment)
      throw Error('VK_VIDEO_SAVE_OR_UPLOAD_OUTCOME_UNCERTAIN');
    record.videoId=videoId;record.videoOwnerId=ownerId;record.attachment=uploaded.attachment;
    record.status='video_uploaded_api_confirmed';await checkpoint(record);
    record.status='wall_post_call_started';await checkpoint(record);
    const wall=await publishWallPost({text:req.text,attachments:[uploaded.attachment]});
    const postId=Number(wall?.post_id);
    if(!Number.isSafeInteger(postId)||postId<=0)throw Error('VK_WALL_POST_RESULT_UNKNOWN');
    record.wallPostId=postId;record.status='vk_video_and_wall_api_accepted';record.submittedAtUTC=iso();
    await checkpoint(record);
    let wallSeen=false,videoSeen=false;
    for(let i=0;i<5;i++){
      try{
        const check=await vkCall('wall.getById',{posts:'-48198173_'+postId},process.env.VK_GROUP_TOKEN);
        const items=Array.isArray(check?.items)?check.items:Array.isArray(check)?check:[];
        wallSeen=items.some(p=>Number(p.id)===postId&&Number(p.owner_id)===-GROUP);
      }catch(e){record.wallReadbackErrorClass=e?.name||'VkError'}
      try{
        const check=await vkCall('video.get',{videos:String(ownerId)+'_'+videoId},token);
        videoSeen=Array.isArray(check?.items)&&check.items.some(v=>Number(v.id)===videoId&&Number(v.owner_id)===ownerId);
      }catch(e){record.videoReadbackErrorClass=e?.name||'VkError'}
      if(wallSeen&&videoSeen)break;
      if(i<4)await wait(3000);
    }
    record.videoReadbackConfirmed=videoSeen;record.wallReadbackConfirmed=wallSeen;
    record.status=(wallSeen&&videoSeen)?'published_verified_by_vk':'vk_api_accepted_readback_partial';
    record.videoUrl='https://vk.com/video'+ownerId+'_'+videoId;
    record.wallUrl='https://vk.com/wall'+(-GROUP)+'_'+postId;
    record.checkedAtUTC=iso();
    await checkpoint(record);
    console.log('SOFIYA_VK_REFRESHED_PUBLISH_FINAL',JSON.stringify({
      status:record.status,videoId,postId,videoReadbackConfirmed:videoSeen,wallReadbackConfirmed:wallSeen,
      videoUrl:record.videoUrl,wallUrl:record.wallUrl}));
  }catch(err){
    record.status='manual_reconciliation_required';
    record.error=String(err?.message||err).slice(0,250);
    record.note='VK video.save/upload/wall.post may have partially succeeded. DO NOT REPLAY.';
    try{await checkpoint(record)}catch(e){console.error('SOFIYA_RESULT_PERSIST_FAILED',String(e).slice(0,120))}
    throw err;
  }
}
main().catch(err=>{
  const msg=String(err?.message||err);
  const allowed=/(GITHUB_SECRET_WRITE_FAILED|VK_REFRESH_|REFRESHED_|VK_VIDEO|VK_WALL|WRONG_|MISSING_|UNAUTHORIZED_|SOURCE_|EXACT_|ALREADY_|GIT_)/.test(msg)?msg.slice(0,270):'UNKNOWN_ERROR';
  console.error('::error::SOFIYA_VK_REFRESH_'+allowed);process.exitCode=1;
});
