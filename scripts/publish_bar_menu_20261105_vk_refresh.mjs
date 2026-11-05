/* Single controlled VK carousel recovery using proven same-runner VK ID token rotation. */
import fs from 'node:fs';
import {execFileSync,spawnSync} from 'node:child_process';
import {randomBytes,createHash} from 'node:crypto';
import {buildVkRefreshRequest,parseVkRefreshResponse,readOnlyVkTokenCheck} from './vk-refresh-lib.mjs';
const ID='bar-menu-20261105';
const BASE='results/campaigns/'+ID+'-vk.json';
const RECEIPT='results/campaigns/'+ID+'-vk-refresh-recover.json';
const RELEASE='requests/campaigns/'+ID+'-release.json';
const QA='results/verification/'+ID+'-stage.json';
const GROUP=48198173;
const REPO='lsevmos-gpt/ls-vk';
const pause=n=>new Promise(r=>setTimeout(r,n));
function git(...a){try{return execFileSync('git',a,{encoding:'utf8',stdio:'pipe',timeout:105000}).trim()}catch(e){throw Error('GIT_FAILED: '+String(e.stderr||e).slice(-200))}}
function sha(path){return createHash('sha256').update(fs.readFileSync(path)).digest('hex')}
function required(key){const val=process.env[key];if(!val||!val.trim())throw Error('MISSING_'+key);return val.trim()}
function writeSecret(args,val,pat){const r=spawnSync('gh',args,{input:val,encoding:'utf8',timeout:35000,maxBuffer:65536,env:{PATH:process.env.PATH||'',HOME:process.env.HOME||'',GH_TOKEN:pat,GH_HOST:'github.com',CI:'true'}});if(r.status!==0||r.error)throw Error('GITHUB_SECRET_WRITE_FAILED')}
async function checkpoint(doc,first=false){
  doc.updatedAtUTC=new Date().toISOString();
  fs.mkdirSync('results/campaigns',{recursive:true});
  fs.writeFileSync(RECEIPT,JSON.stringify(doc,null,2)+'\n',first?{flag:'wx'}:{});
  git('add','--',RECEIPT);
  git('commit','-m','Bar menu VK refreshed token '+doc.status+' [skip ci]');
  for(let i=0;i<7;i++){
    try{git('pull','--rebase','origin','main');git('push','origin','HEAD:main');return}
    catch(e){if(i===6)throw Error('GIT_RECEIPT_PERSIST_FAILED');await pause((i+1)*1100)}
  }
}
async function refresh(){
  const pat=required('VK_SECRETS_WRITE_PAT');
  const probe='VK_BAR_MENU_REFRESH_PROBE_20261105';
  writeSecret(['secret','set',probe,'--repo',REPO],randomBytes(24).toString('base64url'),pat);
  try{writeSecret(['secret','delete',probe,'--repo',REPO],'',pat)}catch{}
  const state=randomBytes(24).toString('base64url');
  const built=buildVkRefreshRequest({clientId:'54806879',redirectUri:'https://vk.liniyasporta.ru/oauth/callback',deviceId:required('VK_DEVICE_ID'),refreshToken:required('VK_REFRESH_TOKEN'),state});
  let res,obj;
  try{res=await fetch(built.url,built.options);obj=await res.json().catch(()=>null)}
  catch{throw Error('VK_REFRESH_NETWORK_FAILED')}
  if(!res.ok)throw Error('VK_REFRESH_HTTP_'+res.status);
  const tokens=parseVkRefreshResponse(obj,state);
  writeSecret(['secret','set','VK_REFRESH_TOKEN','--repo',REPO],tokens.refreshToken,pat);
  console.log('ROTATED_REFRESH_TOKEN_PERSISTED');
  const check=await readOnlyVkTokenCheck(tokens.accessToken,'54806879');
  if(check.vkId!=='OK'||check.vkApiUsers!=='OK')throw Error('VK_REFRESHED_TOKEN_NOT_AUTHORIZED_ON_RUNNER');
  console.log('VK_REFRESHED_TOKEN_USER_API_OK');
  return tokens.accessToken;
}
async function main(){
  if(process.env.GITHUB_REPOSITORY!==REPO||process.env.GITHUB_REF!=='refs/heads/main'||process.env.GITHUB_ACTOR!=='lsevmos-gpt'||process.env.GITHUB_EVENT_NAME!=='push')throw Error('UNAUTHORIZED_RUN_CONTEXT');
  git('pull','--ff-only','origin','main');
  if(fs.existsSync(RECEIPT)){console.log('VK_REFRESH_RECOVERY_ALREADY_RESERVED_NO_REPOST');return}
  const previous=JSON.parse(fs.readFileSync(BASE,'utf8'));
  if(previous.status!=='manual_review_required'||!previous.error.includes('another ip address')||previous.wallPostId||previous.attachments)throw Error('PREVIOUS_FAILURE_WAS_NOT_PRE_UPLOAD');
  const r=JSON.parse(fs.readFileSync(RELEASE,'utf8')),q=JSON.parse(fs.readFileSync(QA,'utf8'));
  if(r.id!==ID||q.id!==ID||!r.approved||!r.publicContent||!r.submitNow||q.images.length!==6||r.vkGroupId!==GROUP)throw Error('APPROVED_RELEASE_MISMATCH');
  const images=q.images.map((row,i)=>{
    if(row.order!==i+1||r.mediaOrder[i]!==row.original||sha(row.original)!==row.sha256)throw Error('SOURCE_HASH_MISMATCH_'+i);
    return row.original;
  });
  required('VK_GROUP_TOKEN');
  git('config','user.name','ls-vk-bar-refreshed-publish');
  git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com');
  const token=await refresh();
  process.env.VK_USER_TOKEN=token;
  const {getGroupId,vkCall,uploadWallPhoto,publishWallPost}=await import('../src/vk.js');
  if(Number(await getGroupId())!==GROUP)throw Error('WRONG_VK_GROUP');
  const users=await vkCall('users.get',{},token);
  if(!Array.isArray(users)||!users.length)throw Error('REFRESHED_TOKEN_INVALID');
  git('pull','--ff-only','origin','main');
  if(fs.existsSync(RECEIPT)){console.log('VK_RECOVERY_RACE_ALREADY_RESERVED');return}
  const doc={id:ID,network:'vk',status:'reserved_before_provider_upload',groupId:GROUP,runId:process.env.GITHUB_RUN_ID,originalPNGs:true,attachments:[]};
  await checkpoint(doc,true);
  try{
    for(let i=0;i<images.length;i++){
      doc.status='upload_in_progress_'+(i+1);await checkpoint(doc);
      const path=images[i];
      const photo=await uploadWallPhoto({path,originalname:'bar-menu-'+String(i+1).padStart(2,'0')+'.png',mimetype:'image/png'});
      doc.attachments.push(photo.attachment);
      doc.status='uploaded_photo_'+(i+1);await checkpoint(doc);
      console.log('BAR_VK_PHOTO_SAVED',i+1,photo.photo.id);
    }
    doc.status='wall_post_call_started';await checkpoint(doc);
    const wall=await publishWallPost({text:r.text,attachments:doc.attachments});
    const postId=Number(wall?.post_id);
    if(!Number.isSafeInteger(postId)||postId<=0)throw Error('VK_POST_ID_NOT_RETURNED');
    doc.wallPostId=postId;doc.wallUrl='https://vk.com/wall-'+GROUP+'_'+postId;
    doc.status='vk_wall_api_accepted';await checkpoint(doc);
    try{
      const data=await vkCall('wall.getById',{posts:'-'+GROUP+'_'+postId},token);
      const items=Array.isArray(data?.items)?data.items:Array.isArray(data)?data:[];
      const row=items.find(x=>Number(x.id)===postId&&Number(x.owner_id)===-GROUP);
      doc.readbackConfirmed=Boolean(row);
      doc.readbackPhotoCount=(row?.attachments||[]).filter(x=>x.type==='photo').length;
    }catch(e){doc.readbackConfirmed=false;doc.readbackErrorClass=e?.name||'VKError'}
    doc.status=doc.readbackConfirmed&&doc.readbackPhotoCount===6?'published_verified_by_vk':'vk_api_accepted_readback_partial';
    await checkpoint(doc);
    console.log('VK_BAR_MENU_FINAL',JSON.stringify({status:doc.status,postId:doc.wallPostId,url:doc.wallUrl,photoCount:doc.readbackPhotoCount||0}));
  }catch(e){
    doc.status='manual_reconciliation_required';doc.error=String(e.message||e).slice(0,240);
    doc.note='Do not replay after reserved upload outcome. Check provider and results.';
    try{await checkpoint(doc)}catch(x){console.error('RECEIPT_SAVE_ERROR',String(x).slice(0,120))}
    throw e;
  }
}
main().catch(e=>{console.error('VK_BAR_REFRESH_ERROR',String(e.message||e).slice(0,250));process.exitCode=1});
