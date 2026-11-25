// One-off authorized VK feed photo for Black Friday 2026. NEVER touches Instagram.
import fs from 'node:fs';
import {execFileSync,spawnSync} from 'node:child_process';
import {createHash,randomBytes} from 'node:crypto';
import {buildVkRefreshRequest,parseVkRefreshResponse,readOnlyVkTokenCheck} from './vk-refresh-lib.mjs';

const REPO='lsevmos-gpt/ls-vk', GROUP=48198173, ID='bf-20261125-feed-photo-vk';
const REQUEST='requests/campaigns/'+ID+'.json', RECEIPT='results/campaigns/'+ID+'.json';
const PHOTO='/tmp/bf-20261125-feed-1080x1350.jpg';
const SHA='12a510b27a9d8599b37e762b15690a3d5ecb564113f67016039a1c71abc5bd51';
const URL='https://ls-social-media-bridge.ls-evmos.workers.dev/bf-20261125/feed-4x5-1080x1350.jpg';
const now=()=>new Date().toISOString();
const pause=ms=>new Promise(r=>setTimeout(r,ms));
function required(k){const v=process.env[k];if(!v?.trim())throw Error('MISSING_'+k);return v.trim()}
function git(...args){try{return execFileSync('git',args,{encoding:'utf8',timeout:100000,stdio:'pipe'}).trim()}catch(e){throw Error('GIT_'+args[0]+'_FAILED '+String(e.stderr||e).slice(-120))}}
async function checkpoint(data,first=false){
 data.updatedAtUTC=now();fs.mkdirSync('results/campaigns',{recursive:true});
 fs.writeFileSync(RECEIPT,JSON.stringify(data,null,2)+'\n',first?{flag:'wx'}:{});
 git('add','--',RECEIPT);git('commit','-m','Record BF VK feed '+data.status+' [skip ci]');
 for(let n=0;n<6;n++){try{git('pull','--rebase','origin','main');git('push','origin','HEAD:main');return}catch(e){if(n===5)throw e;await pause((n+1)*1500)}}
}
function saveSecret(name,value,pat){
 const p=spawnSync('gh',['secret','set',name,'--repo',REPO],{
  input:value,encoding:'utf8',timeout:35000,maxBuffer:65536,
  env:{HOME:process.env.HOME||'',PATH:process.env.PATH||'',GH_TOKEN:pat,GH_HOST:'github.com',CI:'true'}
 });
 if(p.status!==0||p.error)throw Error('VK_REFRESH_SECRET_UPDATE_FAILED');
}
async function refresh(){
 const pat=required('VK_SECRETS_WRITE_PAT'),state=randomBytes(22).toString('base64url');
 const req=buildVkRefreshRequest({clientId:'54806879',redirectUri:'https://vk.liniyasporta.ru/oauth/callback',
  deviceId:required('VK_DEVICE_ID'),refreshToken:required('VK_REFRESH_TOKEN'),state});
 const r=await fetch(req.url,req.options),obj=await r.json().catch(()=>null);
 if(!r.ok)throw Error('VK_REFRESH_HTTP_'+r.status);
 const tokens=parseVkRefreshResponse(obj,state);
 saveSecret('VK_REFRESH_TOKEN',tokens.refreshToken,pat);
 const chk=await readOnlyVkTokenCheck(tokens.accessToken,'54806879');
 if(chk.vkId!=='OK'||chk.vkApiUsers!=='OK')throw Error('VK_ID_USER_TOKEN_INVALID');
 return tokens.accessToken;
}
async function main(){
 if(process.env.GITHUB_REPOSITORY!==REPO||process.env.GITHUB_REF!=='refs/heads/main'||
   process.env.GITHUB_EVENT_NAME!=='push'||process.env.GITHUB_ACTOR!=='lsevmos-gpt')
   throw Error('UNAUTHORIZED_GITHUB_CONTEXT');
 git('pull','--ff-only','origin','main');
 if(fs.existsSync(RECEIPT)){console.log('BF_VK_EXISTING_RECEIPT_NO_REPEAT');return}
 const data=JSON.parse(fs.readFileSync(REQUEST,'utf8'));
 if(data.id!==ID||data.authorizedByUser!==true||data.approved!==true||
    data.publishNow!==true||data.groupId!==GROUP||data.imageSHA256!==SHA||
    data.imageURL!==URL||typeof data.caption!=='string'||
    !data.caption.startsWith('🖤💚 ЧЁРНАЯ ПЯТНИЦА В «ЛИНИИ СПОРТА»!')||
    !data.caption.includes('27 и 28 ноября')||data.caption.length>2200)throw Error('BF_VK_REQUEST_INVALID');
 if(!fs.existsSync(PHOTO)||fs.statSync(PHOTO).size!==872247||
    createHash('sha256').update(fs.readFileSync(PHOTO)).digest('hex')!==SHA)
    throw Error('BF_VK_MEDIA_MISMATCH');
 required('VK_GROUP_TOKEN');required('VK_REFRESH_TOKEN');required('VK_DEVICE_ID');
 required('VK_SECRETS_WRITE_PAT');
 process.env.VK_USER_TOKEN=await refresh();
 const {getGroupId,vkCall,uploadWallPhoto,publishWallPost}=await import('../src/vk.js');
 if(Number(await getGroupId())!==GROUP)throw Error('WRONG_VK_COMMUNITY');
 const g=await vkCall('groups.getById',{group_id:GROUP},required('VK_GROUP_TOKEN'));
 const actual=Array.isArray(g?.groups)?g.groups[0]:Array.isArray(g)?g[0]:g;
 if(Number(actual?.id)!==GROUP||actual.screen_name!=='liniya__sporta')throw Error('WRONG_VK_GROUP_NAME');
 const wall=await vkCall('wall.get',{owner_id:-GROUP,count:70,filter:'owner'},required('VK_GROUP_TOKEN'));
 const duplicates=(wall?.items||[]).filter(x=>typeof x.text==='string'&&
  x.text.includes('ЧЁРНАЯ ПЯТНИЦА В «ЛИНИИ СПОРТА»!')&&x.text.includes('27 и 28 ноября'));
 if(duplicates.length){console.log('BF_VK_ALREADY_ON_WALL_NO_DUPLICATE',duplicates.map(x=>x.id));return}
 git('pull','--ff-only','origin','main');if(fs.existsSync(RECEIPT))return;
 git('config','user.name','ls-bf-vk-feed-once');
 git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com');
 const receipt={id:ID,status:'reserved_before_provider_upload',createdAtUTC:now(),
  imageSHA256:SHA,groupId:GROUP,sourceURL:URL,wallPostId:null,runId:process.env.GITHUB_RUN_ID,noAutoRetry:true};
 await checkpoint(receipt,true);
 try{
  const upload=await uploadWallPhoto({path:PHOTO,originalname:'black-friday-2026-feed.jpg',mimetype:'image/jpeg'});
  if(!/^photo-?\d+_\d+$/.test(String(upload?.attachment||'')))throw Error('VK_PHOTO_ATTACHMENT_UNCONFIRMED');
  receipt.attachment=upload.attachment;receipt.status='photo_saved';await checkpoint(receipt);
  receipt.status='wall_post_call_started';await checkpoint(receipt);
  const result=await publishWallPost({text:data.caption,attachments:[upload.attachment]});
  const postId=Number(result?.post_id);
  if(!Number.isSafeInteger(postId)||postId<=0)throw Error('VK_WALL_POST_ID_UNCONFIRMED');
  receipt.wallPostId=postId;receipt.wallURL='https://vk.com/wall-'+GROUP+'_'+postId;
  receipt.status='vk_api_accepted';await checkpoint(receipt);
  let verified=false;
  for(let k=0;k<9;k++){
   try{
    const r=await vkCall('wall.getById',{posts:'-'+GROUP+'_'+postId},required('VK_GROUP_TOKEN'));
    const items=Array.isArray(r?.items)?r.items:Array.isArray(r)?r:[];
    verified=items.some(x=>Number(x.id)===postId&&Number(x.owner_id)===-GROUP);
    if(verified)break;
   }catch(e){}
   if(k<8)await pause(3000);
  }
  receipt.status=verified?'published_verified_by_vk':'vk_api_accepted_readback_pending';
  receipt.wallReadbackConfirmed=verified;await checkpoint(receipt);
  console.log('BLACK_FRIDAY_VK_POST',JSON.stringify({status:receipt.status,wallURL:receipt.wallURL,postId,verified}));
 }catch(e){
  receipt.status='manual_reconciliation_required';receipt.error=String(e?.message||e).slice(0,230);
  try{await checkpoint(receipt)}catch(_){}
  throw e;
 }
}
main().catch(e=>{console.error('::error::BF_VK_FEED '+String(e?.message||e).slice(0,220));process.exitCode=1});
