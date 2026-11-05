"""One-shot bar menu carousel via direct Meta API; one durable attempt."""
import hashlib,json,os,subprocess,time
from pathlib import Path
from datetime import datetime,timezone
from scripts.instagram_collab import MetaClient
from scripts.instagram_meta_calendar import publish_via_meta

ID='bar-menu-20261105'
RELEASE=Path('requests/campaigns/'+ID+'-release.json')
QA=Path('results/verification/'+ID+'-stage.json')
RECEIPT=Path('results/campaigns/'+ID+'-instagram.json')
PREFIX='https://raw.githubusercontent.com/lsevmos-gpt/ls-vk/main/media/'

def git(*args):
    x=subprocess.run(['git',*args],capture_output=True,text=True,timeout=100)
    if x.returncode:raise RuntimeError('git '+ ' '.join(args[:2])+' failed: '+x.stderr[-350:])

def save(doc,first=False):
    doc['checkedAtUTC']=datetime.now(timezone.utc).isoformat()
    RECEIPT.parent.mkdir(parents=True,exist_ok=True)
    with RECEIPT.open('x' if first else 'w') as f:json.dump(doc,f,ensure_ascii=False,indent=2);f.write('\n')
    git('add',str(RECEIPT));git('commit','-m','Bar menu Instagram '+doc['status']+' [skip ci]')
    for n in range(5):
        try:git('pull','--rebase','origin','main');git('push','origin','HEAD:main');return
        except RuntimeError:
            if n==4:raise
            time.sleep(n+1)

def main():
    assert os.environ.get('GITHUB_REPOSITORY')=='lsevmos-gpt/ls-vk'
    assert os.environ.get('GITHUB_REF')=='refs/heads/main'
    assert os.environ.get('GITHUB_ACTOR')=='lsevmos-gpt'
    git('pull','--ff-only','origin','main')
    if RECEIPT.exists():print('INSTAGRAM_ALREADY_RESERVED_NO_RETRY');return
    r=json.loads(RELEASE.read_text());q=json.loads(QA.read_text())
    assert r['id']==q['id']==ID and r['approved'] and r['publicContent'] and r['submitNow']
    assert r['instagram']=='liniya__sporta' and r['vkGroupId']==48198173
    assert q['ok'] and len(q['images'])==6 and len(r['mediaOrder'])==6
    assert [v['order'] for v in q['images']]==list(range(1,7))
    assert r['mediaOrder']==[v['original'] for v in q['images']]
    for row in q['images']:
        for key,hashkey in [('original','sha256'),('metaJPEG','metaSHA256')]:
            with open(row[key],'rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==row[hashkey]
    token=os.environ['META_IG_ACCESS_TOKEN'];ig_id=os.environ['META_IG_USER_ID']
    client=MetaClient(token,ig_id,graph_version='v26.0')
    client.verify_account()
    # Check already-published public feed before any provider mutation.
    items=client._api('GET',ig_id+'/media',{'fields':'id,caption,permalink','limit':'50'}).get('data',[])
    for p in items:
        if 'ТВОЯ ВКУСНАЯ ПАУЗА' in (p.get('caption') or ''):
            print('INSTAGRAM_DUPLICATE_FOUND',p.get('id'),p.get('permalink'));return
    git('config','user.name','ls-social-bot')
    git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
    doc={'id':ID,'network':'instagram','postType':'carousel','status':'submission_started','runId':os.environ['GITHUB_RUN_ID'],'sourceCount':6}
    save(doc,True)
    job={'postType':'carousel','text':r['text'],'media':[{'type':'image','url':PREFIX+row['metaJPEG']} for row in q['images']]}
    try:
        ident=str(publish_via_meta(client,job))
        doc['instagramMediaId']=ident;doc['status']='published_readback_pending';save(doc)
        try:
            detail=client._api('GET',ident,{'fields':'id,media_type,permalink,timestamp'})
            doc['permalink']=detail.get('permalink');doc['mediaType']=detail.get('media_type')
            doc['readbackConfirmed']=str(detail.get('id'))==ident and detail.get('media_type')=='CAROUSEL_ALBUM'
            doc['status']='published_verified_by_meta' if doc['readbackConfirmed'] else 'published_readback_pending'
        except Exception as e:
            doc['readbackConfirmed']=False;doc['readbackError']=type(e).__name__
        save(doc)
        print('META_CAROUSEL_RESULT',json.dumps(doc,ensure_ascii=False))
    except Exception as e:
        doc['status']='manual_review_required';doc['error']=str(e)[:260]
        doc['note']='Do not retry: Meta outcome may be uncertain'
        try:save(doc)
        except Exception as x:print('RECEIPT_SAVE_ERROR',type(x).__name__)
        raise
if __name__=='__main__':main()
