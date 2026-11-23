// 23 Nov 2026 user-approved three separate VK photo Stories in fixed order.
// Provider called once per Story. No automatic repeats of uncertain stories.save.
import fs from 'node:fs';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
const ID='fitness-heroes6d-20261123-1815-vk';
const REQ='requests/campaigns/fitness-heroes6d-20261123-vk-stories.json';
const RECEIPT='results/campaigns/fitness-heroes6d-20261123-vk-stories.json';
const SOURCES=[
  {file:'/tmp/fitness-story-01.jpg',sha:'f7e974e12f8520a1cc7d35054d07473157526a95bfab7c6e1d285453fcbbfb3a',bytes:723966},
  {file:'/tmp/fitness-story-02.jpg',sha:'92e07e0972b653a49d3bd2399fdc9386e647352f7e04313a1f3b36f787c1ae9d',bytes:774307},
  {file:'/tmp/fitness-story-03.jpg',sha:'f70febe5cb5a6c59853783e9858a59bf50f8ccca19c0443b9c076a3a0fdb247a',bytes:700878}
];
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
function git(...args){return execFileSync('git',args,{encoding:'utf8',stdio:'pipe',timeout:100000}).trim()}
function sha(path){return createHash('sha256').update(fs.readFileSync(path)).digest('hex')}
async function record(d,initial=false){
 d.updatedAtUTC=new Date().toISOString();fs.mkdirSync('results/campaigns',{recursive:true});
 fs.writeFileSync(RECEIPT,JSON.stringify(d,null,2)+'\n',initial?{flag:'wx'}:{});
 git('add','--',RECEIPT);git('commit','-m',`VK fitness stories ${d.status} [skip ci]`);
 for(let i=0;i<6;i++){try{git('pull','--rebase','origin','main');git('push','origin','HEAD:main');return}catch(e){if(i===5)throw e;await sleep((i+1)*1000)}}
}
async function main(){
 if(process.env.GITHUB_REPOSITORY!=='lsevmos-gpt/ls-vk'||process.env.GITHUB_REF!=='refs/heads/main'||process.env.GITHUB_EVENT_NAME!=='push'||process.env.GITHUB_ACTOR!=='lsevmos-gpt')throw Error('wrong_runner');
 git('pull','--ff-only','origin','main');
 if(fs.existsSync(RECEIPT))return console.log('EXISTING_VK_RECEIPT_NO_REPEAT');
 const req=JSON.parse(fs.readFileSync(REQ,'utf8'));
 if(req.id!==ID||req.approved!==true||req.authorizedByUser!==true||req.groupId!==48198173||req.positionOrder.join(',')!=='directions,groups,personal'||req.publishAt!=='2026-11-23T18:15:00+03:00')throw Error('approval_mismatch');
 if(Date.now()<Date.parse(req.publishAt))await sleep(Math.min(60000,Date.parse(req.publishAt)-Date.now()));
 if(Date.now()>Date.parse(req.publishAt)+30*60000)throw Error('too_late_to_publish');
 for(const s of SOURCES){if(!fs.existsSync(s.file)||fs.statSync(s.file).size!==s.bytes||sha(s.file)!==s.sha)throw Error('source_mismatch_'+s.file)}
 if(!process.env.VK_GROUP_TOKEN)throw Error('missing_vkgrouptoken');
 const {getGroupId,uploadStory}=await import('../src/vk.js');
 if(Number(await getGroupId())!==48198173)throw Error('wrong_vk_group');
 git('config','user.name','ls-fitness-stories-vk');
 git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com');
 git('pull','--ff-only','origin','main');if(fs.existsSync(RECEIPT))return;
 const d={id:ID,provider:'vk',status:'reserved',createdAtUTC:new Date().toISOString(),groupId:48198173,requestedAt:req.publishAt,approved:true,stories:[],noRetry:true};
 await record(d,true);
 for(let i=0;i<SOURCES.length;i++){
  const s=SOURCES[i]; const story={position:i+1,label:req.positionOrder[i],status:'upload_started',sourceSha256:s.sha};
  d.stories.push(story);d.status='upload_in_progress';await record(d);
  try{
   const res=await uploadStory({path:s.file,originalname:'fitness-heroes6d-'+String(i+1).padStart(2,'0')+'.jpg',mimetype:'image/jpeg'},{type:'photo',addToNews:true});
   const items=Array.isArray(res?.items)?res.items:Array.isArray(res)?res:res?.response?.items||[];
   const id=items?.[0]?.id||items?.[0]?.story_id||res?.id||null;
   story.status='vk_api_accepted';story.storyId=id==null?null:String(id);story.providerReceipt=Boolean(res);story.confirmedAtUTC=new Date().toISOString();
   d.status='partial_or_complete_vk_api_accepted';await record(d);
  }catch(e){story.status='manual_reconciliation_required';story.error=String(e.message||e).slice(0,180);d.status='manual_reconciliation_required';await record(d);throw e}
 }
 d.status='all_three_vk_story_api_accepted';await record(d);
 console.log('VK_FITNESS_STORIES_RECEIPT',JSON.stringify({status:d.status,storyIds:d.stories.map(x=>x.storyId),count:d.stories.length}));
}
main().catch(e=>{console.error('::error::VK_FITNESS_STORIES '+String(e.message||e).slice(0,230));process.exitCode=1});
