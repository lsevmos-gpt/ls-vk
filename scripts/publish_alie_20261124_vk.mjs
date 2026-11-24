// One-shot, expressly approved VK-only publication of Alie, original resolution.
import fs from 'node:fs';
import https from 'node:https';
import {execFileSync,spawnSync} from 'node:child_process';
import {createHash,randomBytes} from 'node:crypto';
import FormData from 'form-data';
import {buildVkRefreshRequest,parseVkRefreshResponse,readOnlyVkTokenCheck} from './vk-refresh-lib.mjs';

const REPO='lsevmos-gpt/ls-vk',GROUP=48198173,ID='alie-20261124-vk';
const REQUEST='requests/campaigns/alie-20261124-vk.json';
const RECEIPT='results/campaigns/alie-20261124-vk.json';
const VIDEO='/tmp/alie-20261124-native.mp4';
const COVER='/tmp/alie-20261124-cover.jpg', ORIGINAL_COVER='/tmp/alie-20261124-cover.png';
const V_SHA='fd6801bdac28abf8f6223c3b72a64d0db8eb373f1d758563916be1c53e2b6999';
const C_SHA='c75a3ac911db2ad4c675350bef8bf459ee7e9f9917c91fd4240d44a375e9b7e2';
const now=()=>new Date().toISOString();
const pause=ms=>new Promise(r=>setTimeout(r,ms));
const sha=p=>createHash('sha256').update(fs.readFileSync(p)).digest('hex');
function git(...args){try{return execFileSync('git',args,{encoding:'utf8',timeout:100000,stdio:'pipe'}).trim()}catch(e){throw Error('GIT_'+args[0]+'_FAILED '+String(e.stderr||e).slice(-150))}}
function required(name){const value=process.env[name];if(!value?.trim())throw Error('MISSING_'+name);return value.trim()}
async function checkpoint(d,first=false){
 d.updatedAtUTC=now();fs.mkdirSync('results/campaigns',{recursive:true});
 fs.writeFileSync(RECEIPT,JSON.stringify(d,null,2)+'\n',first?{flag:'wx'}:{});
 git('add','--',RECEIPT);git('commit','-m','ALIE VK '+d.status+' [skip ci]');
 for(let i=0;i<7;i++){try{git('pull','--rebase','origin','main');git('push','origin','HEAD:main');return}catch(e){if(i===6)throw e;await pause(1000*(i+1))}}
}
function saveSecret(name,value,pat){
 const proc=spawnSync('gh',['secret','set',name,'--repo',REPO],{input:value,encoding:'utf8',timeout:35000,maxBuffer:65536,
 env:{HOME:process.env.HOME||'',PATH:process.env.PATH||'',GH_TOKEN:pat,GH_HOST:'github.com',CI:'true'}});
 if(proc.status!==0||proc.error)throw Error('GH_SECRET_WRITE_FAILED');
}
async function refresh(){
 const pat=required('VK_SECRETS_WRITE_PAT');
 const state=randomBytes(22).toString('base64url');
 const args=buildVkRefreshRequest({clientId:'54806879',redirectUri:'https://vk.liniyasporta.ru/oauth/callback',
   deviceId:required('VK_DEVICE_ID'),refreshToken:required('VK_REFRESH_TOKEN'),state});
 const response=await fetch(args.url,args.options);
 const body=await response.json().catch(()=>null);
 if(!response.ok)throw Error('VK_REFRESH_HTTP_'+response.status);
 const tokens=parseVkRefreshResponse(body,state);
 saveSecret('VK_REFRESH_TOKEN',tokens.refreshToken,pat);
 const chk=await readOnlyVkTokenCheck(tokens.accessToken,'54806879');
 if(chk.vkId!=='OK'||chk.vkApiUsers!=='OK'||!chk.vkApiAllowed)throw Error('VK_VIDEO_PERMISSION_NOT_CONFIRMED');
 return tokens.accessToken;
}
async function uploadThumb(uploadURL){
 const url=new URL(uploadURL);
 if(url.protocol!=='https:'||!(/(^|\.)vk\.com$/.test(url.hostname)||/(^|\.)vk\.ru$/.test(url.hostname)))throw Error('UNTRUSTED_VK_THUMB_HOST');
 const form=new FormData();
 form.append('file',fs.createReadStream(COVER),{filename:'alie-cover.jpg',contentType:'image/jpeg'});
 return await new Promise((resolve,reject)=>{
  const req=https.request(url,{method:'POST',headers:form.getHeaders(),timeout:60000},res=>{
   const chunks=[];let count=0;res.on('data',c=>{count+=c.length;if(count<300000)chunks.push(c)});
   res.on('end',()=>res.statusCode>=200&&res.statusCode<300?resolve(Buffer.concat(chunks).toString('utf8')):reject(Error('VK_THUMB_HTTP_'+res.statusCode)));
   res.on('error',reject);
  });
  req.on('timeout',()=>req.destroy(Error('VK_THUMB_TIMEOUT')));req.on('error',reject);form.pipe(req);
 });
}
async function main(){
 if(process.env.GITHUB_REPOSITORY!==REPO||process.env.GITHUB_REF!=='refs/heads/main'||
    process.env.GITHUB_EVENT_NAME!=='push'||process.env.GITHUB_ACTOR!=='lsevmos-gpt')throw Error('UNAUTHORIZED_CONTEXT');
 git('pull','--ff-only','origin','main');
 if(fs.existsSync(RECEIPT)){console.log('ALIE_VK_EXISTING_RECEIPT_NO_REPEAT');return}
 const req=JSON.parse(fs.readFileSync(REQUEST,'utf8'));
 if(req.id!==ID||req.approved!==true||req.authorizedByUser!==true||req.publishNow!==true||req.groupId!==GROUP||
    req.videoSHA256!==V_SHA||req.coverSHA256!==C_SHA||
    req.videoURL!=='https://ls-social-media-bridge.ls-evmos.workers.dev/alie-20261124/vk-original.mp4'||
    req.coverURL!=='https://ls-social-media-bridge.ls-evmos.workers.dev/alie-20261124/vk-original.png'||
    typeof req.caption!=='string'||!req.caption.includes('Боджек Алие')||
    !fs.existsSync(VIDEO)||!fs.existsSync(COVER)||fs.statSync(VIDEO).size<1000000||!fs.existsSync(ORIGINAL_COVER)||fs.statSync(COVER).size<10000||sha(VIDEO)!==V_SHA||sha(ORIGINAL_COVER)!==C_SHA)throw Error('ALIE_MEDIA_REQUEST_MISMATCH');
 
 required('VK_GROUP_TOKEN');required('VK_DEVICE_ID');required('VK_REFRESH_TOKEN');required('VK_SECRETS_WRITE_PAT');
 const userToken=await refresh();process.env.VK_USER_TOKEN=userToken;
 const {getGroupId,vkCall,uploadWallVideo,publishWallPost}=await import('../src/vk.js');
 if(Number(await getGroupId())!==GROUP)throw Error('WRONG_VK_GROUP');
 const groups=await vkCall('groups.getById',{group_id:GROUP},required('VK_GROUP_TOKEN'));
 const current=Array.isArray(groups?.groups)?groups.groups[0]:Array.isArray(groups)?groups[0]:groups;
 if(Number(current?.id)!==GROUP||current?.screen_name!=='liniya__sporta')throw Error('WRONG_VK_SCREEN_NAME');
 const wall=await vkCall('wall.get',{owner_id:-GROUP,count:60,filter:'owner'},userToken);
 if((wall?.items||[]).some(p=>String(p.text||'').includes('Знакомьтесь — Боджек Алие!')))throw Error('ALIE_DUPLICATE_WALL_FOUND_NO_UPLOAD');
 const videos=await vkCall('video.get',{owner_id:-GROUP,count:100},userToken);if((videos?.items||[]).some(v=>String(v.title||'').includes('Боджек Алие')||String(v.description||'').includes('Знакомьтесь — Боджек Алие!')))throw Error('ALIE_DUPLICATE_VIDEO_FOUND_NO_UPLOAD');
 git('pull','--ff-only','origin','main');
 if(fs.existsSync(RECEIPT))return;
 git('config','user.name','ls-alie-vk-once');
 git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com');
 const receipt={id:ID,status:'reserved_before_provider_upload',createdAtUTC:now(),groupId:GROUP,
  videoSHA256:V_SHA,originalCoverSHA256:C_SHA,coverSHA256:sha(COVER),videoResolution:'1920x3114',
  runId:process.env.GITHUB_RUN_ID,videoId:null,wallPostId:null,coverStatus:'not_attempted',noRetries:true};
 await checkpoint(receipt,true);
 try{
  receipt.status='upload_started';await checkpoint(receipt);
  const v=await uploadWallVideo({path:VIDEO,originalname:'alie-reel.mp4',mimetype:'video/mp4'},
    {name:'Боджек Алие — тренер «Линии спорта»',description:req.caption});
  const videoId=Number(v?.video?.id),ownerId=Number(v?.video?.owner_id);
  if(!Number.isSafeInteger(videoId)||videoId<=0||ownerId!==-GROUP||!v.attachment)throw Error('VK_VIDEO_SAVE_UNCONFIRMED');
  receipt.videoId=videoId;receipt.videoOwnerId=ownerId;receipt.videoURL='https://vk.com/video'+ownerId+'_'+videoId;
  receipt.status='video_api_accepted';await checkpoint(receipt);
  const thumb=await vkCall('video.getThumbUploadUrl',{owner_id:ownerId},userToken);
  if(!thumb?.upload_url)throw Error('VK_THUMB_UPLOAD_URL_MISSING');
  const thumbJSON=await uploadThumb(thumb.upload_url);
  const thumbs=await vkCall('video.saveUploadedThumb',{owner_id:ownerId,thumb_json:thumbJSON,video_id:videoId,set_thumb:1},userToken);
  if(!thumbs)throw Error('VK_THUMB_SAVE_UNCONFIRMED');
  receipt.coverStatus='api_accepted';receipt.status='cover_api_accepted';await checkpoint(receipt);
  
  receipt.status='wall_post_call_started';await checkpoint(receipt);
  const p=await publishWallPost({text:req.caption,attachments:[v.attachment]});
  const postId=Number(p?.post_id);
  if(!Number.isSafeInteger(postId)||postId<=0)throw Error('VK_WALL_POST_ID_UNCONFIRMED');
  receipt.wallPostId=postId;receipt.wallURL='https://vk.com/wall-'+GROUP+'_'+postId;
  receipt.status='vk_api_accepted';await checkpoint(receipt);
  let wallOK=false,videoOK=false;
  for(let i=0;i<8;i++){try{const w=await vkCall('wall.getById',{posts:'-'+GROUP+'_'+postId},required('VK_GROUP_TOKEN'));wallOK=(Array.isArray(w?.items)?w.items:Array.isArray(w)?w:[]).some(x=>Number(x.id)===postId&&Number(x.owner_id)===-GROUP)}catch{};try{const v=await vkCall('video.get',{videos:ownerId+'_'+videoId},userToken);videoOK=(v?.items||[]).some(x=>Number(x.id)===videoId&&Number(x.owner_id)===ownerId)}catch{};if(wallOK&&videoOK)break;await pause(3000)}
  receipt.wallReadbackConfirmed=wallOK;receipt.videoReadbackConfirmed=videoOK;receipt.status=wallOK&&videoOK?'published_verified_by_vk':'vk_api_accepted_readback_partial';await checkpoint(receipt);
  console.log('ALIE_VK_SCHEDULE_RESULT',JSON.stringify({status:receipt.status,post:receipt.wallURL,video:receipt.videoURL,cover:receipt.coverStatus,publishAt:req.publishAt}));
 }catch(e){receipt.status='manual_reconciliation_required';receipt.error=String(e?.message||e).slice(0,170);try{await checkpoint(receipt)}catch{}throw e}
}
main().catch(e=>{console.error('::error::ALIE_VK '+String(e.message||e).slice(0,190));process.exitCode=1});
