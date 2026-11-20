import fs from 'node:fs';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {getGroupId,vkCall,uploadWallVideo,publishWallPost} from '../src/vk.js';
const GROUP=48198173;
const REQUEST='requests/campaigns/yulia-20261120-vk.json';
const RECEIPT='results/campaigns/yulia-20261120-vk.json';
const VIDEO='/tmp/yulia-20261120-2k.mp4';
const sha=x=>createHash('sha256').update(fs.readFileSync(x)).digest('hex');
const run=(...args)=>execFileSync('git',args,{encoding:'utf8',stdio:'pipe',timeout:95000}).trim();
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function record(d,first=false){
 d.updatedAtUTC=new Date().toISOString();
 fs.mkdirSync('results/campaigns',{recursive:true});
 fs.writeFileSync(RECEIPT,JSON.stringify(d,null,2)+'\n',first?{flag:'wx'}:{});
 run('add','--',RECEIPT);
 run('commit','-m','Yulia VK clip '+d.status+' [skip ci]');
 for(let i=0;i<6;i++){try{run('pull','--rebase','origin','main');run('push','origin','HEAD:main');return;}catch(e){if(i===5)throw e;await sleep(1000*(i+1));}}
}
async function main(){
 if(process.env.GITHUB_REPOSITORY!=='lsevmos-gpt/ls-vk'||process.env.GITHUB_REF!=='refs/heads/main'||
    process.env.GITHUB_EVENT_NAME!=='push'||process.env.GITHUB_ACTOR!=='lsevmos-gpt')throw Error('Unauthorized workflow');
 run('pull','--ff-only','origin','main');
 if(fs.existsSync(RECEIPT)){console.log('Existing receipt, no repeat');return;}
 const j=JSON.parse(fs.readFileSync(REQUEST,'utf8'));
 if(j.id!=='yulia-20261120-vk'||j.approved!==true||j.submitNow!==true||j.groupId!==GROUP||
    j.videoSHA256!=='d081759644182aab2c8e67e153296a30aef5911f18fab4b217d05d2c920f2fcd'||
    j.description!==j.wallText||j.coauthorInstagram!=='miledi._01'||
    !fs.existsSync(VIDEO)||sha(VIDEO)!==j.videoSHA256||fs.statSync(VIDEO).size!==68849298)throw Error('Yulia source mismatch');
 if(!process.env.VK_USER_TOKEN||!process.env.VK_GROUP_TOKEN)throw Error('Required VK token missing');
 if(Number(await getGroupId())!==GROUP)throw Error('Wrong VK target');
 run('config','user.name','ls-yulia-vk-once');
 run('config','user.email','41898282+github-actions[bot]@users.noreply.github.com');
 const doc={id:j.id,status:'reserved_before_provider_upload',createdAtUTC:new Date().toISOString(),groupId:GROUP,
  videoSHA256:j.videoSHA256,caption:j.description,videoId:null,wallPostId:null,noRetries:true};
 await record(doc,true);
 try{
  doc.status='upload_started';await record(doc);
  const v=await uploadWallVideo({path:VIDEO,originalname:'yulia-20261120-2k.mp4',mimetype:'video/mp4'},
    {name:'Тренер Юлия — Линия спорта',description:j.description});
  const vid=Number(v?.video?.id),oid=Number(v?.video?.owner_id);
  if(!(Number.isInteger(vid)&&vid>0&&oid===-GROUP&&v.attachment))throw Error('VK upload uncertain; do not repeat');
  doc.videoId=vid;doc.videoUrl='https://vk.com/video'+oid+'_'+vid;
  doc.status='video_api_accepted';await record(doc);
  doc.status='wall_post_started';await record(doc);
  const p=await publishWallPost({text:j.wallText,attachments:[v.attachment]});
  const pid=Number(p?.post_id);
  if(!(Number.isInteger(pid)&&pid>0))throw Error('VK wall post uncertain; do not repeat');
  doc.wallPostId=pid;doc.wallUrl='https://vk.com/wall-'+GROUP+'_'+pid;
  doc.status='vk_api_accepted';await record(doc);
  let w=false;
  for(let i=0;i<5;i++){
   try{const r=await vkCall('wall.getById',{posts:'-'+GROUP+'_'+pid},process.env.VK_GROUP_TOKEN);
    const rows=Array.isArray(r?.items)?r.items:Array.isArray(r)?r:[];
    w=rows.some(x=>Number(x.id)===pid&&Number(x.owner_id)===-GROUP);}catch(e){}
   if(w)break;await sleep(3000);
  }
  doc.wallReadbackConfirmed=w;doc.status=w?'published_verified_by_vk':'vk_api_accepted_readback_partial';
  await record(doc);console.log('YULIA_VK_RESULT',JSON.stringify({status:doc.status,url:doc.wallUrl}));
 }catch(e){
  doc.status='manual_reconciliation_required';doc.error=String(e.message||e).slice(0,180);
  try{await record(doc)}catch(x){console.error('Receipt save failed')}
  throw e;
 }
}
main().catch(e=>{console.error('::error::YULIA_VK',String(e.message||e).slice(0,180));process.exitCode=1});
