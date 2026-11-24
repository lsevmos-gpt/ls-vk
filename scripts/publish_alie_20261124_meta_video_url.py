"""One approved Alie Instagram Reel via the proven GitHub video_url route.
No Cloudflare publication, no rupload, no new credentials, no VK mutation.
"""
from __future__ import annotations
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
from datetime import datetime,timezone
from urllib.request import Request,urlopen
from scripts.instagram_collab import MetaClient

ROOT=Path(__file__).resolve().parents[1]
ID='alie-20261124-github-video-url'
REQ=ROOT/'requests/instagram-meta'/(ID+'.json')
RECEIPT=ROOT/'results/instagram-meta'/(ID+'.json')
VIDEO=ROOT/'media/alie-20261124-meta-reel.mp4'
COVER=ROOT/'media/alie-20261124-meta-cover.jpg'
ORIGINAL=Path('/tmp/alie-ig-source.mp4')
PNG=Path('/tmp/alie-ig-source.png')
RAW='https://raw.githubusercontent.com/lsevmos-gpt/ls-vk/main/'
V_SHA='fd6801bdac28abf8f6223c3b72a64d0db8eb373f1d758563916be1c53e2b6999'
C_SHA='c75a3ac911db2ad4c675350bef8bf459ee7e9f9917c91fd4240d44a375e9b7e2'
OLD=['18025363934949669','18025365167949669','18025371152949669']
ACCOUNT='liniya__sporta'
COLLAB=['_alie_13_']
def now():return datetime.now(timezone.utc).isoformat()
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def git(*args):
    r=subprocess.run(['git',*args],cwd=ROOT,capture_output=True,text=True,timeout=250)
    if r.returncode:raise RuntimeError('GIT_'+args[0]+'_FAILED '+(r.stderr or r.stdout)[-200:])
    return r.stdout.strip()
def push():
    for i in range(6):
        try:git('pull','--rebase','origin','main');git('push','origin','HEAD:main');return
        except RuntimeError:
            if i==5:raise
            time.sleep(2+i)
def record(d,first=False):
    d['updatedAtUTC']=now()
    RECEIPT.parent.mkdir(parents=True,exist_ok=True)
    with RECEIPT.open('x' if first else 'w',encoding='utf8') as f:json.dump(d,f,ensure_ascii=False,indent=2);f.write('\n')
    git('add','--',str(RECEIPT.relative_to(ROOT)));git('commit','-m','Alie Meta video_url '+d['status']+' [skip ci]');push()
def public_check(p):
    u=RAW+str(p.relative_to(ROOT))
    for i in range(8):
        try:
            with urlopen(Request(u,headers={'User-Agent':'Liniya-Sporta-Publication/1','Accept-Encoding':'identity'}),timeout=150) as r:
                h=hashlib.sha256();n=0
                if r.status!=200:raise RuntimeError('HTTP_'+str(r.status))
                while True:
                    chunk=r.read(1024*1024)
                    if not chunk:break
                    h.update(chunk);n+=len(chunk)
            if n!=p.stat().st_size or h.hexdigest()!=sha(p):raise RuntimeError('PUBLIC_BYTES_OR_HASH_MISMATCH')
            return u
        except Exception:
            if i==7:raise
            time.sleep(5)
def main():
    if os.getenv('GITHUB_REPOSITORY')!='lsevmos-gpt/ls-vk' or os.getenv('GITHUB_REF')!='refs/heads/main' or os.getenv('GITHUB_EVENT_NAME')!='push' or os.getenv('GITHUB_ACTOR')!='lsevmos-gpt' or not (os.getenv('GITHUB_RUN_ID') or '').isdigit():raise RuntimeError('UNAUTHORIZED_CONTEXT')
    git('pull','--ff-only','origin','main')
    if RECEIPT.exists():print('EXISTING_RECEIPT_NO_REPLAY',flush=True);return
    req=json.loads(REQ.read_text('utf8'))
    oldreq=json.loads((ROOT/'requests/campaigns/alie-20261124-vk.json').read_text('utf8'))
    if not (req.get('id')==ID and req.get('approved') is True and req.get('publicContent') is True and req.get('publishNow') is True and req.get('route')=='GITHUB_ACTIONS_META_VIDEO_URL' and req.get('handle')==ACCOUNT and req.get('collaborators')==COLLAB and req.get('shouldShareToFeed') is True and req.get('oldContainers')==OLD and req.get('text')==oldreq.get('caption') and req.get('sourceVideoSHA256')==V_SHA and req.get('sourceCoverSHA256')==C_SHA and req.get('media')==[{'type':'video','url':RAW+str(VIDEO.relative_to(ROOT))}] and req.get('coverUrl')==RAW+str(COVER.relative_to(ROOT))):raise RuntimeError('APPROVAL_MISMATCH')
    if sha(ORIGINAL)!=V_SHA or sha(PNG)!=C_SHA:raise RuntimeError('ORIGINAL_SHA256_MISMATCH')
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(VIDEO)],timeout=45))
    v=next(x for x in info['streams'] if x['codec_type']=='video');a=next(x for x in info['streams'] if x['codec_type']=='audio')
    if not(v['codec_name']=='h264' and v['pix_fmt']=='yuv420p' and (v['width'],v['height'])==(1920,3114) and v['avg_frame_rate']=='25/1' and int(v.get('nb_frames',0))==1085 and a['codec_name']=='aac' and a['sample_rate']=='48000' and a['channels']==2 and int(v.get('bit_rate',0))<=25000000 and int(a.get('bit_rate',0))<=135000 and abs(float(info['format']['duration'])-43.477333)<0.15 and 1000000<VIDEO.stat().st_size<95000000):raise RuntimeError('MEDIA_CONFORMANCE_FAILED')
    token=os.environ['META_IG_ACCESS_TOKEN']
    client=MetaClient(token,os.environ['META_IG_USER_ID'],graph_version='v26.0')
    client.verify_account()
    def check_feed():
        res=client._api('GET',client.ig_user_id+'/media',{'fields':'id,caption,permalink,media_type,media_product_type,timestamp','limit':'100'})
        if not isinstance(res.get('data'),list):raise RuntimeError('IG_FEED_READBACK_UNAVAILABLE')
        return next((r for r in res['data'] if 'Боджек Алие' in str(r.get('caption',''))),None)
    existing=check_feed()
    if existing:
        print('ALREADY_PUBLISHED_NO_DUPLICATE',json.dumps({'id':existing.get('id'),'permalink':existing.get('permalink')},ensure_ascii=False),flush=True);return
    oldstates={}
    for cid in OLD:
        o=client._api('GET',cid,{'fields':'status_code,status'})
        state=str(o.get('status_code','')).upper()
        oldstates[cid]=state
        if state not in ('ERROR','EXPIRED','FINISHED','IN_PROGRESS'):raise RuntimeError('OLD_CONTAINER_UNRECONCILED_'+cid+'_'+state)
    git('config','user.name','ls-alie-meta-video-url');git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
    git('add','--',str(VIDEO.relative_to(ROOT)),str(COVER.relative_to(ROOT)))
    if git('diff','--cached','--name-only'):
        git('commit','-m','Stage verified Alie MP4 and original cover for Meta video_url [skip ci]');push()
    vu=public_check(VIDEO);cu=public_check(COVER)
    git('pull','--ff-only','origin','main')
    if RECEIPT.exists():raise RuntimeError('EXISTING_RESERVATION')
    if check_feed():raise RuntimeError('REEL_ALREADY_PRESENT_NO_DUPLICATE')
    job={'video_url':vu,'cover_url':cu,'caption':req['text'],'collaborators':COLLAB,'share_to_feed':True}
    fields=MetaClient.create_fields(job)
    if 'upload_type' in fields or fields.get('video_url')!=vu or fields.get('cover_url')!=cu or fields.get('caption')!=req['text'] or json.loads(fields['collaborators'])!=COLLAB:raise RuntimeError('META_VIDEO_URL_FIELDS_MISMATCH')
    d={'id':ID,'status':'reserved_before_meta_mutation','route':'GITHUB_ACTIONS_META_VIDEO_URL','account':ACCOUNT,'collaborator':COLLAB[0],'collaboratorAcceptance':'not_confirmed','videoSourceSHA256':V_SHA,'originalCoverSHA256':C_SHA,'videoSHA256':sha(VIDEO),'coverSHA256':sha(COVER),'videoResolution':'1920x3114','videoBytes':VIDEO.stat().st_size,'videoUrl':vu,'coverUrl':cu,'oldContainers':oldstates,'creationId':None,'publishedMediaId':None,'runId':os.environ['GITHUB_RUN_ID'],'noAutomaticRetries':True,'createdAtUTC':now()}
    record(d,True)
    try:
        d['status']='container_create_call_started';record(d)
        r=client._api('POST',client.ig_user_id+'/media',fields)
        cid=str(r.get('id',''))
        if not cid.isdecimal():raise RuntimeError('META_CONTAINER_ID_MISSING')
        d.update(status='container_created',creationId=cid);record(d)
        for i in range(60):
            st=client._api('GET',cid,{'fields':'status_code,status'})
            state=str(st.get('status_code','')).upper()
            if state=='FINISHED':break
            if state in ('ERROR','EXPIRED','PUBLISHED'):
                d['metaContainerStatus']=str(st.get('status','')).replace(token,'[REDACTED]')[:900]
                raise RuntimeError('META_CONTAINER_'+state+' '+d['metaContainerStatus'])
            if i<59:time.sleep(10)
        else:raise RuntimeError('META_PROCESSING_TIMEOUT')
        d['status']='ready_to_publish';record(d)
        if check_feed():raise RuntimeError('REEL_ALREADY_PRESENT_BEFORE_RELEASE')
        d['status']='publish_call_started';record(d)
        p=client._api('POST',client.ig_user_id+'/media_publish',{'creation_id':cid})
        mid=str(p.get('id',''))
        if not mid.isdecimal():raise RuntimeError('PUBLISHED_ID_UNCONFIRMED')
        d.update(status='meta_api_publish_accepted',publishedMediaId=mid,collaboratorAcceptance='invitation_requested_not_accepted');record(d)
        for i in range(10):
            try:
                m=client._api('GET',mid,{'fields':'id,permalink,username,media_type,media_product_type,timestamp,caption'})
                if str(m.get('id',''))==mid and m.get('username')==ACCOUNT and m.get('permalink'):
                    d.update(status='published_readback_confirmed',permalink=m['permalink'],mediaType=m.get('media_type'),mediaProductType=m.get('media_product_type'),captionConfirmed=m.get('caption')==req['text'])
                    break
            except Exception:pass
            if i<9:time.sleep(5)
        record(d)
        print('ALIE_INSTAGRAM_RESULT',json.dumps({k:d.get(k) for k in ('status','publishedMediaId','permalink','collaborator','captionConfirmed')},ensure_ascii=False),flush=True)
    except Exception as e:
        d['status']='manual_reconciliation_required';d['error']=str(e).replace(token,'[REDACTED]')[:900]
        try:record(d)
        except Exception:pass
        raise
if __name__=='__main__':
    try:main()
    except Exception as e:
        print('::error::ALIE_IG '+str(e).replace(os.getenv('META_IG_ACCESS_TOKEN','UNSETTOKEN'),'[REDACTED]')[:900],file=sys.stderr)
        sys.exit(1)
