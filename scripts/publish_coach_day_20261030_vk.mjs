/* User-approved one-shot Coach Day VK photo Story, 30 Oct 2026. */
import fs from 'node:fs';
import crypto from 'node:crypto';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {getGroupId,vkCall,uploadStory} from '../src/vk.js';
const MEDIA='media/coach-day-20261030-original.png';
const SHA='96fadda082d858c6f40c637263dd11f134236dfb8dc9dcb917e1fc148f05a345';
const SIZE=3563841;
const GROUP=48198173;
const RECEIPT='results/campaigns/coach-day-20261030-vk.json';
const pause=ms=>new Promise(ok=>setTimeout(ok,ms));
const stamp=()=>new Date().toISOString();
const git=(...args)=>execFileSync('git',args,{timeout:90000,stdio:'pipe'});
async function checkpoint(rec,first=false){
  rec.updatedAtUTC=stamp();
  fs.mkdirSync('results/campaigns',{recursive:true});
  fs.writeFileSync(RECEIPT,JSON.stringify(rec,null,2)+'\n',first?{flag:'wx'}:undefined);
  git('add','--',RECEIPT);
  git('commit','-m','Coach Day VK Story: '+rec.status+' [skip ci]');
  for(let i=0;i<5;i++){
    try{git('pull','--rebase','origin','main');git('push','origin','HEAD:main');return}
    catch(e){if(i===4)throw e;await pause(1000*(i+1))}
  }
}
async function visible(){
  const r=await vkCall('stories.get',{owner_id:-GROUP},process.env.VK_GROUP_TOKEN);
  const items=Array.isArray(r?.items)?r.items:Array.isArray(r)?r:[];
  return items.flatMap(x=>Array.isArray(x?.stories)?x.stories:Array.isArray(x)?x:[x])
    .filter(x=>Number(x?.owner_id)===-GROUP&&Number.isInteger(x.id));
}
async function main(){
  if(process.env.GITHUB_REPOSITORY!=='lsevmos-gpt/ls-vk'||
    process.env.GITHUB_ACTOR!=='lsevmos-gpt'||process.env.GITHUB_REF!=='refs/heads/main'||
    process.env.GITHUB_EVENT_NAME!=='push')throw Error('Unapproved GitHub context');
  if(Date.now()<Date.parse('2026-10-30T00:00:00+03:00')||
     Date.now()>=Date.parse('2026-10-31T00:00:00+03:00'))throw Error('Only 30 Oct MSK');
  if(!process.env.VK_GROUP_TOKEN)throw Error('VK_GROUP_TOKEN absent');
  git('pull','--ff-only','origin','main');
  if(fs.existsSync(RECEIPT)){console.log('Prior VK attempt, NO DUPLICATE');return}
  if(!fs.existsSync(MEDIA)||fs.statSync(MEDIA).size!==SIZE||
    crypto.createHash('sha256').update(fs.readFileSync(MEDIA)).digest('hex')!==SHA)
    throw Error('Source original bytes not verified');
  if((await getGroupId())!==GROUP)throw Error('Wrong VK group ID');
  const groupResult=await vkCall('groups.getById',{group_id:GROUP},process.env.VK_GROUP_TOKEN);
  const g=Array.isArray(groupResult?.groups)?groupResult.groups[0]:
          Array.isArray(groupResult)?groupResult[0]:groupResult;
  if(Number(g?.id)!==GROUP||g?.screen_name!=='liniya__sporta')
    throw Error('VK group identity mismatch');
  const prior=await visible();const known=new Set(prior.map(x=>x.id));
  git('config','user.name','ls-coach-day-vk-once');
  git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com');
  git('pull','--ff-only','origin','main');
  if(fs.existsSync(RECEIPT)){console.log('Another VK run reserved');return}
  const rec={id:'coach-day-20261030-vk',provider:'vk',groupId:GROUP,
    groupScreenName:'liniya__sporta',runId:process.env.GITHUB_RUN_ID,
    source:MEDIA,sourceSha256:SHA,sourceBytes:SIZE,
    mediaType:'image/png',resolution:'1080x1920',approved:true,withLinks:false,
    createdAtUTC:stamp(),status:'reserved_before_provider_call',providerAttempts:0,
    baselineStoryIds:[...known]};
  await checkpoint(rec,true);
  try{
    rec.status='submitting_to_vk';rec.providerAttempts=1;await checkpoint(rec);
    const result=await uploadStory({path:path.resolve(MEDIA),
      originalname:path.basename(MEDIA),mimetype:'image/png'},
      {type:'photo',addToNews:true});
    const s=Array.isArray(result?.items)?
      result.items.find(x=>Number(x.owner_id)===-GROUP&&Number.isInteger(x.id)):
      Array.isArray(result)?result.find(x=>Number(x.owner_id)===-GROUP&&Number.isInteger(x.id)):null;
    if(!s)throw Error('VK stories.save response missing exact community Story ID');
    rec.vkStoryId=s.id;rec.ownerId=s.owner_id;rec.status='submitted_to_vk';
    await checkpoint(rec);
    for(let i=0;i<15;i++){
      try{
        const current=await visible();
        if(current.some(x=>x.id===rec.vkStoryId&&!known.has(x.id))){
          rec.status='published_verified_by_vk';
          rec.verifiedAtUTC=stamp();await checkpoint(rec);break;
        }
      }catch(e){rec.verificationError=String(e.message).slice(0,160)}
      await pause(3000);
    }
    console.log('COACH_DAY_VK_FINAL',JSON.stringify({status:rec.status,storyId:rec.vkStoryId}));
  }catch(e){
    rec.status='manual_reconciliation_required';rec.error=String(e.message).slice(0,330);
    try{await checkpoint(rec)}catch(ce){console.log('FINAL_RECEIPT_ERROR',String(ce).slice(0,200))}
    throw e;
  }
}
main().catch(e=>{console.error('::error::COACH_DAY_VK',String(e.message).slice(0,360));process.exitCode=1});
