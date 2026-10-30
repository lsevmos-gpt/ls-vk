/* Coach Day VK read-only reconciliation followed by one owner-authorized safe recovery.
 * Original RGB PNG is pixel-identical to user's full-resolution source (alpha=255).
 * Switch to JPEG Q100 4:4:4 only if upload service rejects RGB PNG BEFORE stories.save.
 */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {getGroupId,vkCall,uploadStory} from '../src/vk.js';
const OLD='results/campaigns/coach-day-20261030-vk.json';
const RECEIPT='results/campaigns/coach-day-20261030-vk-recovery.json';
const MEDIA='media/coach-day-20261030-original.png';
const RGB='media/coach-day-20261030-vk-rgb-lossless.png';
const JPG='media/coach-day-20261030-vk-compat-q100.jpg';
const SHA='96fadda082d858c6f40c637263dd11f134236dfb8dc9dcb917e1fc148f05a345';
const RGB_SHA='03717dbab0aafb40e0e2f183adfbc49ec3fa7de217fe42d758cc2a0a6f0dcd7f';
const JPG_SHA='ac25b6436439451838284e2a98339064fc7ab2d228dd6d40a0f4bfc00bcec216';
const GROUP=48198173;
const sleep=ms=>new Promise(ok=>setTimeout(ok,ms));
const stamp=()=>new Date().toISOString();
const git=(...args)=>execFileSync('git',args,{timeout:90000,stdio:'pipe'});
async function checkpoint(o,first=false){
  o.updatedAtUTC=stamp();
  fs.mkdirSync('results/campaigns',{recursive:true});
  fs.writeFileSync(RECEIPT,JSON.stringify(o,null,2)+'\n',first?{flag:'wx'}:undefined);
  git('add','--',RECEIPT);
  git('commit','-m','Coach Day VK photo recovery: '+o.status+' [skip ci]');
  for(let k=0;k<6;k++){
    try{git('pull','--rebase','origin','main');git('push','origin','HEAD:main');return}
    catch(e){if(k===5)throw e;await sleep((k+1)*1000)}
  }
}
async function live(){
  const r=await vkCall('stories.get',{owner_id:-GROUP},process.env.VK_GROUP_TOKEN);
  const items=Array.isArray(r?.items)?r.items:Array.isArray(r)?r:[];
  return items.flatMap(x=>Array.isArray(x?.stories)?x.stories:Array.isArray(x)?x:[x])
    .filter(x=>Number(x?.owner_id)===-GROUP&&Number.isInteger(x?.id));
}
async function main(){
  if(process.env.GITHUB_REPOSITORY!=='lsevmos-gpt/ls-vk'||process.env.GITHUB_ACTOR!=='lsevmos-gpt'||
    process.env.GITHUB_REF!=='refs/heads/main'||process.env.GITHUB_EVENT_NAME!=='push')
    throw Error('Unapproved GitHub invocation');
  if(Date.now()<Date.parse('2026-10-30T00:00:00+03:00')||
    Date.now()>=Date.parse('2026-10-31T00:00:00+03:00'))throw Error('Not 30 Oct MSK');
  if(!process.env.VK_GROUP_TOKEN)throw Error('VK_GROUP_TOKEN absent');
  git('pull','--ff-only','origin','main');
  if(fs.existsSync(RECEIPT)){console.log('Recovery attempted before: stop duplicate');return}
  const prev=JSON.parse(fs.readFileSync(OLD));
  if(prev.status!=='manual_reconciliation_required'||
     prev.error!=='VK story upload attempt 4/4 failed: VK upload error: go upload error'||
     prev.providerAttempts!==1||prev.vkStoryId||
     prev.sourceSha256!==SHA||prev.groupId!==GROUP)
    throw Error('Previous attempt was not provably upload-stage only: STOP');
  for(const [file,expected] of [[MEDIA,SHA],[RGB,RGB_SHA],[JPG,JPG_SHA]]){
    if(crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')!==expected)
      throw Error('Media hash differs: '+file);
  }
  if((await getGroupId())!==GROUP)throw Error('Unexpected VK group');
  const groupResult=await vkCall('groups.getById',{group_id:GROUP},process.env.VK_GROUP_TOKEN);
  const group=Array.isArray(groupResult?.groups)?groupResult.groups[0]:
    Array.isArray(groupResult)?groupResult[0]:groupResult;
  if(Number(group?.id)!==GROUP||group?.screen_name!=='liniya__sporta')
    throw Error('VK group mismatch');
  const baseline=new Set(prev.baselineStoryIds);
  const before=await live();
  const fresh=before.filter(x=>!baseline.has(x.id));
  if(fresh.length)throw Error('NEW VK Stories since original attempt: stop to avoid duplicate. IDs: '+fresh.map(x=>x.id));
  const rgb=fs.readFileSync(RGB);
  if(rgb.subarray(0,8).toString('hex')!=='89504e470d0a1a0a'||
    rgb.readUInt32BE(16)!==1080||rgb.readUInt32BE(20)!==1920||rgb[25]!==2)
    throw Error('RGB lossless PNG metadata invalid');
  const jpg=fs.readFileSync(JPG);
  if(jpg[0]!==255||jpg[1]!==216||jpg[2]!==255)throw Error('JPEG fallback signature invalid');
  git('config','user.name','ls-coach-day-vk-recovery');
  git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com');
  git('pull','--ff-only','origin','main');
  if(fs.existsSync(RECEIPT)){console.log('Concurrent recovery recorded; stop');return}
  const rec={id:'coach-day-20261030-vk-recovery',provider:'vk',groupId:GROUP,
    original:MEDIA,originalSha256:SHA,originalSize:3563841,
    losslessRgbPngSha256:RGB_SHA,
    rgbPixelSha256:'31658ad5b8912774d1557d01f4b5f83e7d295d5575fb442e07aa8dfba68c9682',
    fallbackJpegQuality:100,fallbackJpegSubsampling:'4:4:4',
    previousError:prev.error,preflightVisibleIds:before.map(x=>x.id),
    createdAtUTC:stamp(),status:'reconciled_no_prior_story_reserved',providerAttempts:0,
    note:'No retry after unknown save result. JPEG only after explicitly failed PNG upload.'};
  await checkpoint(rec,true);
  let saved=null;
  for(const candidate of [
    {file:RGB,mime:'image/png',kind:'pixel_identical_rgb_png'},
    {file:JPG,mime:'image/jpeg',kind:'max_quality_jpeg_100_444'}
  ]){
    if(rec.providerAttempts>0){
      const check=await live();
      if(check.some(x=>!baseline.has(x.id)))
        throw Error('New VK Story appeared: stop before fallback');
    }
    rec.status='submitting_'+candidate.kind;
    rec.providerAttempts++;
    rec.attemptedMedia=candidate.file;
    await checkpoint(rec);
    try{
      const result=await uploadStory({path:path.resolve(candidate.file),
        originalname:path.basename(candidate.file),mimetype:candidate.mime},
        {type:'photo',addToNews:true});
      const matches=Array.isArray(result?.items)?result.items:Array.isArray(result)?result:[];
      const s=matches.find(x=>Number(x?.owner_id)===-GROUP&&Number.isInteger(x?.id));
      if(!s)throw Error('VK stories.save returned unknown Story ID: no retry');
      saved=s;
      rec.mediaUsed=candidate.kind;
      rec.vkStoryId=s.id;rec.ownerId=s.owner_id;rec.status='submitted_to_vk';
      await checkpoint(rec);
      break;
    }catch(e){
      const msg=String(e?.message||e);
      rec.errors=rec.errors||[];rec.errors.push({media:candidate.kind,error:msg.slice(0,250)});
      await checkpoint(rec);
      // Only the exact upload-stage failure proves stories.save was never called.
      if(!msg.includes('VK story upload attempt 4/4 failed: VK upload error: go upload error'))
        throw Error('Ambiguous VK outcome, no fallback: '+msg);
      if(candidate.kind==='max_quality_jpeg_100_444')throw Error('Both compatible upload formats rejected: '+msg);
      console.log('VK_REJECTED_RGB_PNG_UPLOAD_BEFORE_SAVE; JPEG_100_FALLBACK_ALLOWED');
    }
  }
  if(!saved)throw Error('No VK Story ID received');
  for(let i=0;i<14;i++){
    const ls=await live();
    if(ls.some(x=>x.id===saved.id)){
      rec.status='published_verified_by_vk';rec.verifiedAtUTC=stamp();
      await checkpoint(rec);break;
    }
    await sleep(3000);
  }
  console.log('VK_COACH_DAY_RECOVERY_RESULT',JSON.stringify({status:rec.status,
    storyId:rec.vkStoryId,mediaUsed:rec.mediaUsed}));
}
main().catch(async e=>{
  console.error('::error::COACH_DAY_VK_RECOVERY',String(e.message).slice(0,500));
  if(fs.existsSync(RECEIPT)){
    try{
      const rec=JSON.parse(fs.readFileSync(RECEIPT));
      rec.recoveryError=String(e.message).slice(0,360);
      rec.status=rec.status==='published_verified_by_vk'?rec.status:'manual_reconciliation_required';
      await checkpoint(rec);
    }catch(inner){console.error('FINAL_RECEIPT_WRITE_ERROR',String(inner.message).slice(0,200))}
  }
  process.exitCode=1;
});
