/* One-shot VK album post from six byte-verified original PNG assets. */
import fs from 'node:fs';
import crypto from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {getGroupId,vkCall,uploadWallPhoto,publishWallPost} from '../src/vk.js';
const ID='bar-menu-20261105';
const RELEASE='requests/campaigns/'+ID+'-release.json';
const QA='results/verification/'+ID+'-stage.json';
const OUT='results/campaigns/'+ID+'-vk.json';
const delay=ms=>new Promise(r=>setTimeout(r,ms));
function git(...args){
  try{execFileSync('git',args,{encoding:'utf8',stdio:'pipe',timeout:100000})}
  catch(e){throw Error('Git '+args.slice(0,2).join(' ')+' failed: '+String(e.stderr||e).slice(-250))}
}
function hash(path){return crypto.createHash('sha256').update(fs.readFileSync(path)).digest('hex')}
async function checkpoint(doc,first=false){
  doc.checkedAtUTC=new Date().toISOString();
  fs.mkdirSync('results/campaigns',{recursive:true});
  fs.writeFileSync(OUT,JSON.stringify(doc,null,2)+'\n',first?{flag:'wx'}:undefined);
  git('add',OUT);git('commit','-m','Bar menu VK '+doc.status+' [skip ci]');
  for(let n=0;n<5;n++){
    try{git('pull','--rebase','origin','main');git('push','origin','HEAD:main');return}
    catch(e){if(n===4)throw e;await delay((n+1)*1200)}
  }
}
async function main(){
  if(process.env.GITHUB_REPOSITORY!=='lsevmos-gpt/ls-vk'||process.env.GITHUB_REF!=='refs/heads/main'||process.env.GITHUB_ACTOR!=='lsevmos-gpt')throw Error('Wrong GitHub publishing context');
  git('pull','--ff-only','origin','main');
  if(fs.existsSync(OUT)){console.log('VK_ALREADY_RESERVED_NO_RETRY');return}
  const r=JSON.parse(fs.readFileSync(RELEASE,'utf8'));
  const q=JSON.parse(fs.readFileSync(QA,'utf8'));
  if(r.id!==ID||q.id!==ID||r.approved!==true||r.publicContent!==true||r.submitNow!==true||r.vkGroupId!==48198173||r.instagram!=='liniya__sporta'||q.ok!==true||q.images.length!==6)throw Error('Manifest or QA mismatch');
  const paths=q.images.map((row,i)=>{
    if(row.order!==i+1||row.original!==r.mediaOrder[i]||hash(row.original)!==row.sha256)throw Error('Wrong source PNG '+i);
    return row.original;
  });
  if(Number(await getGroupId())!==48198173)throw Error('Wrong VK community ID');
  // VK disallows wall.get with a community token. Prior workflow failed before any upload;
  // this recovery is permitted only while the immutable provider receipt does not exist.
  console.log('VK_RECOVERY_PREFLIGHT: no prior receipt; previous run failed before upload');
  git('config','user.name','ls-social-bot');
  git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com');
  const doc={id:ID,network:'vk',status:'submission_started',groupId:48198173,runId:process.env.GITHUB_RUN_ID,sourceCount:6,originalPNGUnchanged:true};
  await checkpoint(doc,true);
  try{
    const attachments=[];
    for(let i=0;i<paths.length;i++){
      const path=paths[i];
      const photo=await uploadWallPhoto({path,originalname:'bar-menu-'+String(i+1).padStart(2,'0')+'.png',mimetype:'image/png'});
      attachments.push(photo.attachment);
      console.log('VK_ORIGINAL_UPLOADED',i+1,photo.photo.id);
    }
    doc.attachments=attachments;
    doc.status='six_photos_uploaded_wall_pending';
    await checkpoint(doc);
    const post=await publishWallPost({text:r.text,attachments});
    if(!post?.post_id)throw Error('VK wall.post returned no post_id: outcome uncertain');
    doc.wallPostId=post.post_id;
    doc.wallUrl='https://vk.com/wall-48198173_'+post.post_id;
    doc.status='posted_readback_pending';
    await checkpoint(doc);
    try{
      const observed=await vkCall('wall.getById',{posts:'-48198173_'+post.post_id},process.env.VK_GROUP_TOKEN);
      const row=Array.isArray(observed)?observed[0]:observed?.items?.[0];
      doc.readbackConfirmed=Number(row?.id)===Number(post.post_id);
      doc.readbackPhotoCount=(row?.attachments||[]).filter(x=>x.type==='photo').length;
      doc.status=doc.readbackConfirmed&&doc.readbackPhotoCount===6?'published_verified_by_vk':'posted_readback_pending';
    }catch(e){doc.readbackError=String(e.message||e).slice(0,220);doc.readbackConfirmed=false}
    await checkpoint(doc);
    console.log('VK_CAROUSEL_RESULT',JSON.stringify(doc));
  }catch(e){
    doc.status='manual_review_required';doc.error=String(e.message||e).slice(0,300);
    doc.note='Never blindly re-run; six uploads or wall.post may have partially succeeded';
    try{await checkpoint(doc)}catch(x){console.error('VK_RECEIPT_ERROR',String(x).slice(0,160))}
    throw e;
  }
}
main().catch(e=>{console.error('VK_CAROUSEL_ERROR',String(e.message||e).slice(0,380));process.exitCode=1});
