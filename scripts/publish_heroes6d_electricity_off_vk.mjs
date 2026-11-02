/* One-off original unmodified PNG VK Story for Heroes6D electricity outage. */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {getGroupId,vkCall,uploadStory} from '../src/vk.js';
const ID='ls-heroes6d-electricity-off-20261102';
const PNG='media/'+ID+'.png';
const RELEASE='requests/campaigns/'+ID+'-release.json';
const QA='results/verification/'+ID+'-stage.json';
const RECEIPT='results/campaigns/'+ID+'-vk.json';
const SOURCE_SHA='b49ca56bfee78725407f5172f52d53106c93fca3b9e7cb82eff5999ffd95ecbb';
const pause=ms=>new Promise(r=>setTimeout(r,ms));
function git(...args){
  try{execFileSync('git',args,{stdio:'pipe',timeout:95000})}
  catch(e){throw Error('git '+args.slice(0,2).join(' ')+' failed: '+String(e.stderr||e).slice(-300))}
}
function hash(file){return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')}
async function checkpoint(doc,first=false){
  doc.updatedAtUTC=new Date().toISOString();
  fs.mkdirSync(path.dirname(RECEIPT),{recursive:true});
  fs.writeFileSync(RECEIPT,JSON.stringify(doc,null,2)+'\n',first?{flag:'wx'}:undefined);
  git('add','--',RECEIPT);git('commit','-m','Record Heroes6D outage VK Story '+doc.status+' [skip ci]');
  for(let i=0;i<6;i++){
    try{git('pull','--rebase','origin','main');git('push','origin','HEAD:main');return}
    catch(e){if(i===5)throw e;await pause((i+1)*1000)}
  }
}
async function liveIds(){
  const response=await vkCall('stories.get',{owner_id:-48198173},process.env.VK_GROUP_TOKEN);
  const items=Array.isArray(response?.items)?response.items:Array.isArray(response)?response:[];
  return items.flatMap(x=>Array.isArray(x?.stories)?x.stories:Array.isArray(x)?x:[x])
    .filter(x=>Number(x?.owner_id)===-48198173 && Number.isInteger(x?.id)).map(x=>x.id);
}
function verify(){
  if(process.env.GITHUB_REPOSITORY!=='lsevmos-gpt/ls-vk'||
     process.env.GITHUB_REF!=='refs/heads/main'||
     process.env.GITHUB_EVENT_NAME!=='push'||
     process.env.GITHUB_ACTOR!=='lsevmos-gpt'||
     !/^\d+$/.test(process.env.GITHUB_RUN_ID||''))
    throw Error('Unauthorized publishing context');
  if(!process.env.VK_GROUP_TOKEN)throw Error('VK_GROUP_TOKEN missing');
  git('pull','--ff-only','origin','main');
  if(fs.existsSync(RECEIPT)){console.log('EXISTING_VK_RECEIPT_DO_NOT_REPOST');return false}
  const release=JSON.parse(fs.readFileSync(RELEASE,'utf8'));
  const qa=JSON.parse(fs.readFileSync(QA,'utf8'));
  if(release.id!==ID||qa.id!==ID||!release.approved||!release.publicContent||!release.submitNow||
     release.vkGroupId!==48198173||release.instagram!=='liniya__sporta'||
     JSON.stringify(release.stories)!==JSON.stringify(['electricity-off-heroes6d'])||
     !qa.ok||!qa.stagingOnly||!qa.originalVKUnchanged||
     qa.sourceSha256!==SOURCE_SHA||qa.sourceBytes!==3223258||qa.pngPath!==PNG||
     !fs.existsSync(PNG)||fs.statSync(PNG).size!==qa.sourceBytes||hash(PNG)!==SOURCE_SHA)
    throw Error('VK original PNG or approved release mismatch');
  return true;
}
async function main(){
  if(!verify())return;
  const groupId=await getGroupId();
  if(Number(groupId)!==48198173)throw Error('Unexpected VK group');
  const lookup=await vkCall('groups.getById',{group_id:48198173},process.env.VK_GROUP_TOKEN);
  const group=Array.isArray(lookup?.groups)?lookup.groups[0]:Array.isArray(lookup)?lookup[0]:lookup;
  if(Number(group?.id)!==48198173||group?.screen_name!=='liniya__sporta')throw Error('VK group identity mismatch');
  await liveIds();
  git('config','user.name','ls-story-vk');
  git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com');
  if(fs.existsSync(RECEIPT)){console.log('ALREADY_RESERVED_VK_NO_DUPLICATE');return}
  const doc={id:ID,provider:'vk',groupId:48198173,postType:'photo_story',
    status:'submission_started',sourceSha256:SOURCE_SHA,originalPNGUnchanged:true,submittedOnce:true,
    runId:process.env.GITHUB_RUN_ID};
  await checkpoint(doc,true);
  try{
    const result=await uploadStory({path:path.resolve(PNG),originalname:'LS_geroev_6d_off_1080x1920.png',
      mimetype:'image/png'},{type:'photo',addToNews:true});
    const match=Array.isArray(result?.items)?result.items.find(x=>Number(x?.owner_id)===-48198173&&Number.isInteger(x?.id)):null;
    if(!match)throw Error('VK stories.save returned no matching Story ID; outcome uncertain');
    doc.vkStoryId=match.id;
    doc.status='submitted_to_vk_verify_pending';
    await checkpoint(doc);
    for(let i=0;i<12;i++){
      try{const ids=await liveIds();if(ids.includes(match.id)){
        doc.status='published_verified_by_vk';doc.vkReadbackConfirmed=true;break}}
      catch(e){doc.vkReadbackError=String(e.message||e).slice(0,140)}
      if(i<11)await pause(2500);
    }
    if(!doc.vkReadbackConfirmed)doc.vkReadbackConfirmed=false;
    await checkpoint(doc);
    console.log('HEROES6D_VK_STORY',JSON.stringify({id:doc.vkStoryId,status:doc.status,readback:doc.vkReadbackConfirmed}));
  }catch(e){
    doc.status='manual_review_required';
    doc.error=String(e.message||e).slice(0,260);
    doc.note='Do not retry. VK stories.save outcome may be uncertain.';
    try{await checkpoint(doc)}catch(err){console.error('VK receipt sync failed:',String(err).slice(0,160))}
    throw e;
  }
}
main().catch(e=>{console.error('::error::HEROES6D_VK_STORY '+String(e.message||e).slice(0,350));process.exitCode=1});
