// One-time user-approved 27 Oct 2026 19:00 MSK VK Clip + wall post.
// Uses VK ID refresh on the SAME runner immediately before video.save.
// No duplicate retries after an uncertain VK provider mutation.
import fs from 'node:fs';
import {execFileSync,spawnSync} from 'node:child_process';
import {randomBytes,createHash} from 'node:crypto';
import {
  buildVkRefreshRequest,parseVkRefreshResponse,readOnlyVkTokenCheck
} from './vk-refresh-lib.mjs';

const ID='20261027-shpagat-1900';
const REPO='lsevmos-gpt/ls-vk';
const REQ='requests/vk/'+ID+'.json';
const RECEIPT='results/manual/vk/'+ID+'.json';
const START=Date.parse('2026-10-27T18:51:00+03:00');
const RELEASE=Date.parse('2026-10-27T19:00:00+03:00');
const DEADLINE=Date.parse('2026-10-27T19:15:00+03:00');
const VIDEO_URL='https://static.metricool.com/planner/202610/7014498-file-3201710570030047514.mp4';
const FILE='/tmp/ls-shpagat-reel-20261027.mp4';

function now(){return Date.now()}
function iso(){return new Date().toISOString()}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function until(t){while(now()<t)await sleep(Math.min(30000,t-now()))}
function git(...args){return execFileSync('git',args,{encoding:'utf8',timeout:90000}).trim()}
async function persist(rec,first=false){
  rec.updatedAt=iso();
  fs.mkdirSync('results/manual/vk',{recursive:true});
  fs.writeFileSync(RECEIPT,JSON.stringify(rec,null,2)+'\n',first?{flag:'wx'}:{});
  git('add','--',RECEIPT);
  git('commit','-m','Record 2026-10-27 19:00 approved shpagat VK one-shot state [skip ci]');
  for(let k=0;k<6;k++){
    try{git('pull','--rebase','origin','main');git('push','origin','HEAD:main');return}
    catch(e){if(k===5)throw Error('GIT_RESULT_PERSIST_FAILED');await sleep(1000*(k+1))}
  }
}
function required(k){const v=process.env[k];if(!v||!v.trim())throw Error('MISSING_'+k);return v.trim()}
function ghSecret(args,value,pat){
  const p=spawnSync('gh',args,{input:value,encoding:'utf8',timeout:30000,
    env:{PATH:process.env.PATH||'',HOME:process.env.HOME||'',GH_TOKEN:pat,GH_HOST:'github.com',CI:'true'}});
  if(p.status!==0)throw Error('GH_SECRET_WRITE_FAILED');
}
async function getFreshVkToken(){
  const pat=required('VK_SECRETS_WRITE_PAT');
  const canary='VK_SHPAGAT_WRITE_PROBE_20261027';
  ghSecret(['secret','set',canary,'--repo',REPO],randomBytes(25).toString('base64url'),pat);
  try{ghSecret(['secret','delete',canary,'--repo',REPO],'',pat)}catch{}
  const state=randomBytes(24).toString('base64url');
  const built=buildVkRefreshRequest({clientId:'54806879',redirectUri:'https://vk.liniyasporta.ru/oauth/callback',
    deviceId:required('VK_DEVICE_ID'),refreshToken:required('VK_REFRESH_TOKEN'),state});
  let res,payload;
  try{res=await fetch(built.url,built.options);payload=await res.json()}catch{throw Error('VK_REFRESH_TRANSPORT')}
  if(!res.ok)throw Error('VK_REFRESH_HTTP_'+res.status);
  const token=parseVkRefreshResponse(payload,state);
  // Persist rotating token before any VK read/write.
  ghSecret(['secret','set','VK_REFRESH_TOKEN','--repo',REPO],token.refreshToken,pat);
  const checked=await readOnlyVkTokenCheck(token.accessToken,'54806879');
  if(checked.vkId!=='OK'||!checked.vkApiAllowed)throw Error('VK_REFRESHED_TOKEN_NOT_AUTHORIZED');
  console.log('VK_ID_REFRESH_PERSIST_OK; VIDEO_PERMISSION_YES; SECRETS_HIDDEN');
  return token.accessToken;
}
async function main(){
  if(process.env.GITHUB_REPOSITORY!==REPO||process.env.GITHUB_REF!=='refs/heads/main'||
     process.env.GITHUB_EVENT_NAME!=='push')throw Error('UNAUTHORIZED_RUN');
  git('pull','--ff-only','origin','main');
  if(fs.existsSync(RECEIPT))throw Error('ALREADY_RESERVED_NO_DUPLICATES');
  const req=JSON.parse(fs.readFileSync(REQ,'utf8'));
  if(req.id!==ID||req.type!=='clip'||req.approved!==true||req.publicContent!==true||
    req.groupId!==48198173||req.videoUrl!==VIDEO_URL||
    req.publishAt!=='2026-10-27T19:00:00+03:00'||req.postToWall!==true||
    typeof req.text!=='string'||req.text.length<600||req.text.length>2200)
       throw Error('APPROVED_REQUEST_INVALID');
  if(now()>DEADLINE)throw Error('APPROVED_WINDOW_CLOSED');
  if(!required('VK_GROUP_TOKEN'))throw Error('NO_VK_GROUP_TOKEN');
  git('config','user.name','ls-vk-shpagat-publisher');
  git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com');
  // Stage the exact 1080x1920 prepared MP4; never reencode.
  const down=spawnSync('curl',['--fail','--location','--silent','--show-error','--retry','2',
     '--connect-timeout','25','--max-time','180',VIDEO_URL,'--output',FILE],{timeout:195000,encoding:'utf8'});
  if(down.status!==0)throw Error('PUBLIC_VIDEO_DOWNLOAD_FAILED');
  const media=fs.readFileSync(FILE);
  if(media.length<15000000||media.length>110000000||media.subarray(4,8).toString()!=='ftyp')
     throw Error('VIDEO_SIGNATURE_OR_SIZE_INVALID');
  const probe=spawnSync('ffprobe',['-v','error','-select_streams','v:0','-show_entries','stream=width,height',
      '-of','csv=p=0',FILE],{encoding:'utf8',timeout:15000});
  const widthHeight=(probe.stdout||'').trim();
  if(probe.status!==0||!['1080,1920','2160,3840'].includes(widthHeight))
    throw Error('NOT_APPROVED_VERTICAL_VIDEO_'+widthHeight);
  console.log('VK_PREPARED_VIDEO',media.length,widthHeight,createHash('sha256').update(media).digest('hex'));
  await until(START);
  if(now()>DEADLINE)throw Error('APPROVED_WINDOW_CLOSED');
  const userToken=await getFreshVkToken();
  process.env.VK_USER_TOKEN=userToken; // config must be imported AFTER token refresh.
  const {getGroupId,vkCall,uploadWallVideo,publishWallPost}=await import('../src/vk.js');
  const group=await getGroupId();
  if(group!==48198173)throw Error('WRONG_GROUP_ID');
  const validUser=await vkCall('users.get',{},userToken);
  if(!Array.isArray(validUser)||validUser.length===0)throw Error('VK_USER_NOT_VALID');
  let record={id:ID,status:'reserved',platform:'vk',groupId:group,runId:process.env.GITHUB_RUN_ID,
    scheduledFor:req.publishAt,sourceUrl:VIDEO_URL,videoSha256:createHash('sha256').update(media).digest('hex'),
    note:'Only one approved video upload and wall submission. No automatic retries'};
  await persist(record,true);
  try{
    record.status='video_save_and_upload_started';await persist(record);
    const uploaded=await uploadWallVideo({path:FILE,originalname:'shpagat-20261027.mp4',mimetype:'video/mp4'},
       {name:req.name,description:req.text});
    if(!uploaded?.video?.id||!uploaded?.attachment)throw Error('VK_VIDEO_UPLOAD_OUTCOME_UNCERTAIN');
    record.status='video_uploaded';
    record.videoId=uploaded.video.id;record.videoOwnerId=uploaded.video.owner_id;
    record.attachment=uploaded.attachment;await persist(record);
    if(now()>DEADLINE)throw Error('APPROVED_WINDOW_CLOSED_AFTER_UPLOAD');
    record.status='wall_post_call_started';await persist(record);
    const scheduled=now()<RELEASE;
    const response=await publishWallPost({text:req.text,attachments:[uploaded.attachment],
       publishAt:scheduled?req.publishAt:undefined});
    const postId=response?.post_id;
    if(!Number.isInteger(postId))throw Error('WALL_POST_OUTCOME_UNCERTAIN');
    record.status=scheduled?'wall_scheduled_1900':'published';
    record.postId=postId;record.scheduled=scheduled;record.submittedAt=iso();
    await persist(record);
    if(scheduled)await until(RELEASE+10000);
    try{
      const check=await vkCall('wall.getById',{posts:'-48198173_'+postId},process.env.VK_GROUP_TOKEN);
      const posts=Array.isArray(check?.items)?check.items:Array.isArray(check)?check:[];
      record.readbackConfirmed=posts.some(p=>Number(p?.id)===postId&&Number(p?.owner_id)===-48198173);
    }catch{record.readbackConfirmed=false}
    record.status='published_or_scheduled_confirmed';
    record.checkedAt=iso();await persist(record);
    console.log('VK_SHAPAGAT_CLIP_SUBMITTED',JSON.stringify({postId,videoId:record.videoId,scheduled:record.scheduled,readbackConfirmed:record.readbackConfirmed}));
  }catch(err){
    if(record.status!=='published_or_scheduled_confirmed'){
      record.status='manual_review_required';record.error=String(err?.message||err).slice(0,250);
      try{await persist(record)}catch{}
    }
    throw err;
  }
}
main().catch(e=>{console.error('::error::SHPAGAT_VK '+String(e?.message||e).slice(0,260));process.exitCode=1});
