/* Yulia 20 Nov 2026: one explicitly authorized VK recovery after video.save authorization failure.
 * Uses the existing proven VK ID same-runner refresh and exact Cloudflare-hosted video.
 * Never retries a provider mutation after an uncertain outcome.
 */
import fs from 'node:fs';
import { execFileSync, spawnSync } from 'node:child_process';
import { randomBytes, createHash } from 'node:crypto';
import { buildVkRefreshRequest, parseVkRefreshResponse, readOnlyVkTokenCheck } from './vk-refresh-lib.mjs';

const REPO='lsevmos-gpt/ls-vk', GROUP=48198173, ID='yulia-20261120-vk';
const REQUEST='requests/vk/yulia-20261120-recovery.json';
const APPROVED='requests/campaigns/yulia-20261120-vk.json';
const OLD_RECEIPT='results/campaigns/yulia-20261120-vk.json';
const RECEIPT='results/campaigns/yulia-20261120-vk-refresh-recovery.json';
const VIDEO='/tmp/yulia-20261120-2k.mp4';
const COVER='/tmp/yulia-20261120-cover.jpg';
const VIDEO_SHA='d081759644182aab2c8e67e153296a30aef5911f18fab4b217d05d2c920f2fcd';
const COVER_SHA='4b97c883d7a7042113bdd7be8594a913dc163c9a6f827db20565b2e085f54cb2';
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const iso=()=>new Date().toISOString();
function git(...args) {
  try { return execFileSync('git',args,{encoding:'utf8',timeout:105000,stdio:'pipe'}).trim(); }
  catch(error) { throw Error('GIT_'+args[0]+'_FAILED '+String(error.stderr||error).slice(-200)); }
}
function sha(p) { return createHash('sha256').update(fs.readFileSync(p)).digest('hex'); }
function required(n) { const v=process.env[n]; if(!v||!v.trim())throw Error('MISSING_'+n); return v.trim(); }
async function checkpoint(rec,first=false) {
  rec.updatedAtUTC=iso();
  fs.mkdirSync('results/campaigns',{recursive:true});
  fs.writeFileSync(RECEIPT,JSON.stringify(rec,null,2)+'\n',first?{flag:'wx'}:{});
  git('add','--',RECEIPT);
  git('commit','-m','Yulia VK 2K refresh recovery '+rec.status+' [skip ci]');
  for(let i=0;i<8;i++) {
    try { git('pull','--rebase','origin','main'); git('push','origin','HEAD:main'); return; }
    catch(error) { if(i===7)throw Error('GIT_RECEIPT_PERSIST_FAILED'); await wait(1100*(i+1)); }
  }
}
function ghSecret(args,value,pat) {
  const r=spawnSync('gh',args,{input:value,encoding:'utf8',timeout:35000,maxBuffer:65536,
    env:{PATH:process.env.PATH||'',HOME:process.env.HOME||'',GH_TOKEN:pat,GH_HOST:'github.com',CI:'true'}});
  if(r.status!==0||r.error) throw Error('GITHUB_SECRET_WRITE_FAILED');
}
async function refreshOnRunner() {
  const pat=required('VK_SECRETS_WRITE_PAT');
  const probe='VK_YULIA_REFRESH_PROBE_20261120';
  ghSecret(['secret','set',probe,'--repo',REPO],randomBytes(24).toString('base64url'),pat);
  try { ghSecret(['secret','delete',probe,'--repo',REPO],'',pat); } catch {}
  const state=randomBytes(24).toString('base64url');
  const req=buildVkRefreshRequest({clientId:'54806879',redirectUri:'https://vk.liniyasporta.ru/oauth/callback',
    deviceId:required('VK_DEVICE_ID'),refreshToken:required('VK_REFRESH_TOKEN'),state});
  let res,payload;
  try { res=await fetch(req.url,req.options); payload=await res.json().catch(()=>null); }
  catch { throw Error('VK_REFRESH_NETWORK_FAILED'); }
  if(!res.ok)throw Error('VK_REFRESH_HTTP_'+res.status);
  const tokens=parseVkRefreshResponse(payload,state);
  // Refresh tokens rotate: persist the new one BEFORE attempting provider upload.
  ghSecret(['secret','set','VK_REFRESH_TOKEN','--repo',REPO],tokens.refreshToken,pat);
  const check=await readOnlyVkTokenCheck(tokens.accessToken,'54806879');
  if(check.vkId!=='OK'||!check.vkApiAllowed)throw Error('VK_REFRESHED_TOKEN_VIDEO_SCOPE_UNAVAILABLE');
  console.log('YULIA_VK_REFRESH_PERSISTED_AUTH_OK_VIDEO_SCOPE_OK');
  return tokens.accessToken;
}
function preflight() {
  if(process.env.GITHUB_REPOSITORY!==REPO||process.env.GITHUB_REF!=='refs/heads/main'
    ||process.env.GITHUB_EVENT_NAME!=='push'||process.env.GITHUB_ACTOR!=='lsevmos-gpt'
    ||!(/^\d+$/.test(process.env.GITHUB_RUN_ID||'')))throw Error('UNAUTHORIZED_GITHUB_CONTEXT');
  git('pull','--ff-only','origin','main');
  if(fs.existsSync(RECEIPT)) { console.log('YULIA_VK_RECOVERY_ALREADY_RESERVED_NO_RETRY'); return null; }
  const a=JSON.parse(fs.readFileSync(APPROVED,'utf8'));
  const r=JSON.parse(fs.readFileSync(REQUEST,'utf8'));
  const old=JSON.parse(fs.readFileSync(OLD_RECEIPT,'utf8'));
  if(a.id!==ID||a.approved!==true||a.publicContent!==true||a.submitNow!==true||
     a.groupId!==GROUP||a.postToWall!==true||a.noCollaborator!==true||
     a.videoSHA256!==VIDEO_SHA||a.videoBytes!==68849298||a.coverSHA256!==COVER_SHA||
     a.description!==a.wallText||
     r.id!=='yulia-20261120-vk-refresh-recovery'||r.approved!==true||
     r.authorizedByUser!==true||r.publicContent!==true||r.submitNow!==true||
     r.groupId!==GROUP||r.noCollaborator!==true||r.videoSHA256!==VIDEO_SHA||
     r.videoBytes!==68849298||r.coverSHA256!==COVER_SHA||r.text!==a.description||
     old.id!==ID||old.status!=='manual_reconciliation_required'||old.videoId!==null||
     old.wallPostId!==null||!String(old.error||'').includes('video.save: User authorization failed')||
     !fs.existsSync(VIDEO)||fs.statSync(VIDEO).size!==68849298||sha(VIDEO)!==VIDEO_SHA||
     !fs.existsSync(COVER)||fs.statSync(COVER).size!==2136802||sha(COVER)!==COVER_SHA)
     throw Error('YULIA_APPROVAL_OLD_FAILURE_OR_MEDIA_MISMATCH_NO_PUBLISH');
  required('VK_GROUP_TOKEN'); required('VK_REFRESH_TOKEN');
  required('VK_DEVICE_ID'); required('VK_SECRETS_WRITE_PAT');
  console.log('YULIA_VK_RECOVERY_PREFLIGHT_OK_2K_VIDEO_AND_COVER_SHA');
  return {a,r};
}
async function main() {
  const info=preflight();
  if(!info)return;
  git('config','user.name','ls-yulia-vk-refresh-recovery');
  git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com');
  const token=await refreshOnRunner();
  process.env.VK_USER_TOKEN=token;
  // This import MUST be after token refresh because src/config.js snapshots process.env.
  const {getGroupId,vkCall,uploadWallVideo,publishWallPost}=await import('../src/vk.js');
  if(Number(await getGroupId())!==GROUP)throw Error('WRONG_VK_GROUP_ID');
  const target=await vkCall('groups.getById',{group_id:GROUP},token);
  const group=Array.isArray(target?.groups)?target.groups[0]:Array.isArray(target)?target[0]:target;
  if(Number(group?.id)!==GROUP||group?.screen_name!=='liniya__sporta')throw Error('WRONG_VK_GROUP_IDENTITY');
  // Read-only public feed check to avoid a second post if a separate publisher succeeded.
  const wall=await vkCall('wall.get',{owner_id:-GROUP,count:60,filter:'owner'},token);
  const duplicate=(wall?.items||[]).find(p=>String(p?.text||'').includes('Знакомьтесь, Юлия — тренер тренажёрного зала') &&
    String(p?.text||'').includes('ЛИНИЯ СПОРТА — ГНИ СВОЮ ЛИНИЮ!'));
  if(duplicate) { console.log('YULIA_ALREADY_ON_VK_WALL_NO_DUPLICATE_POST_ID='+duplicate.id);return; }
  git('pull','--ff-only','origin','main');
  if(fs.existsSync(RECEIPT)){console.log('YULIA_VK_RECOVERY_RACE_RESERVATION_EXISTS');return;}
  const d={id:'yulia-20261120-vk-refresh-recovery',provider:'vk',groupId:GROUP,
    videoSHA256:VIDEO_SHA,coverSHA256:COVER_SHA,videoResolution:'1440x2560',caption:info.r.text,
    status:'reserved_before_vk_mutation',runId:process.env.GITHUB_RUN_ID,
    refreshScheme:'same-runner-vk-id-rotation',previousError:'video.save User authorization failed',
    noCollaborator:true,videoId:null,wallPostId:null,noRetries:true,createdAtUTC:iso(),
    coverNote:'Approved cover verified; custom VK thumbnail API not guaranteed'};
  await checkpoint(d,true);
  try {
    d.status='video_save_upload_started';await checkpoint(d);
    const upload=await uploadWallVideo({path:VIDEO,originalname:'yulia-20261120-2k.mp4',mimetype:'video/mp4'},
       {name:'Тренер Юлия — Линия спорта',description:info.r.text});
    const vid=Number(upload?.video?.id),oid=Number(upload?.video?.owner_id);
    if(!Number.isSafeInteger(vid)||vid<=0||oid!==-GROUP||!upload?.attachment)throw Error('VK_VIDEO_UPLOAD_RESULT_UNCERTAIN');
    d.videoId=vid;d.videoOwnerId=oid;d.videoUrl='https://vk.com/video'+oid+'_'+vid;
    d.status='vk_video_uploaded';await checkpoint(d);
    d.status='vk_wall_post_call_started';await checkpoint(d);
    const post=await publishWallPost({text:info.r.text,attachments:[upload.attachment]});
    const pid=Number(post?.post_id);
    if(!Number.isSafeInteger(pid)||pid<=0)throw Error('VK_WALL_POST_RESULT_UNCERTAIN');
    d.wallPostId=pid;d.wallUrl='https://vk.com/wall-'+GROUP+'_'+pid;
    d.status='vk_video_wall_api_accepted';await checkpoint(d);
    let seenWall=false,seenVideo=false;
    for(let attempt=0;attempt<6;attempt++) {
      try {
        const w=await vkCall('wall.getById',{posts:'-'+GROUP+'_'+pid},process.env.VK_GROUP_TOKEN);
        const items=Array.isArray(w?.items)?w.items:Array.isArray(w)?w:[];
        seenWall=items.some(p=>Number(p.id)===pid&&Number(p.owner_id)===-GROUP);
      }catch {}
      try {
        const v=await vkCall('video.get',{videos:String(oid)+'_'+vid},token);
        seenVideo=Array.isArray(v?.items)&&v.items.some(item=>Number(item.id)===vid&&Number(item.owner_id)===oid);
      }catch {}
      if(seenWall&&seenVideo)break;
      if(attempt<5)await wait(3000);
    }
    d.wallReadbackConfirmed=seenWall;d.videoReadbackConfirmed=seenVideo;
    d.status=seenWall&&seenVideo?'published_verified_by_vk':'vk_api_accepted_readback_partial';
    await checkpoint(d);
    console.log('YULIA_VK_FINAL',JSON.stringify({status:d.status,videoUrl:d.videoUrl,wallUrl:d.wallUrl,
      videoReadbackConfirmed:seenVideo,wallReadbackConfirmed:seenWall}));
  } catch(error) {
    d.status='manual_reconciliation_required';d.error=String(error?.message||error).slice(0,230);
    d.note='Provider outcome uncertain: do NOT replay without reconciling video/wall.';
    try { await checkpoint(d); } catch{console.error('YULIA_VK_RECOVERY_RECEIPT_FAILED');}
    throw error;
  }
}
main().catch(error=>{
  const s=String(error?.message||error);
  const safe=error?.name==='VkApiError' ? ('VK_API_'+String(error.method||'unknown')+'_CODE_'+String(error.code||'unknown')) : /^(YULIA_|VK_|GIT_|MISSING_|WRONG_|REFRESH_|UNAUTHORIZED_|GITHUB_)/.test(s)?s.slice(0,245):String(error?.name||'UnexpectedError');
  console.error('::error::YULIA_VK_RECOVERY '+safe);
  process.exitCode=1;
});
