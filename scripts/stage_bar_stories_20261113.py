"""Stage exact previewed copies through existing Adobe handoff. No social writes."""
import hashlib,json,os,subprocess
from pathlib import Path

ORDER=['intro-bar','berry-smoothie','protein']
MANIFEST=Path('media-prep/bar-stories-20261113.json')
QA=Path('results/verification/bar-stories-20261113-stage.json')

def digest(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def probe(p):
    return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration,size:stream=codec_type,codec_name,width,height,r_frame_rate,bit_rate,sample_rate','-of','json',str(p)]))

def main():
    assert os.environ['GITHUB_REPOSITORY']=='lsevmos-gpt/ls-vk'
    assert os.environ['GITHUB_ACTOR']=='lsevmos-gpt' and os.environ['GITHUB_REF']=='refs/heads/main'
    m=json.loads(MANIFEST.read_text())
    release=json.loads(Path('requests/campaigns/bar-stories-20261113-release.json').read_text())
    assert release['approved'] is True and release['submitNow'] is True and release['stories']==ORDER
    assert m['id']=='bar-stories-20261113' and m['approved'] is True and m['publicContent'] is True
    assert m['instagram']=='liniya__sporta' and m['vkGroupId']==48198173
    assert [x['id'] for x in m['sequence']]==ORDER
    assert not Path('results/campaigns/bar-stories-20261113-instagram.json').exists()
    assert not Path('results/campaigns/bar-stories-20261113-vk.json').exists()
    rows=[]
    for row in m['sequence']:
        out=dict(id=row['id'],sourceDriveFileId=row['driveFileId'],sourceSHA256=row['sourceSHA256'],sourceOriginalVerifiedBeforeHandoff=True,metaVideoStreamUnchanged=row['metaVideoStreamUnchanged'],vkOriginalBytesUnchanged=row['vkOriginalBytesUnchanged'],fps=24)
        assert row['sourceOriginalVerifiedBeforeHandoff'] is True
        for platform in ['meta','vk']:
            p=Path(row[platform+'Path']);url=row[platform+'URL']
            assert str(p).startswith('media/bar-20261113-') and p.suffix=='.mp4'
            assert url.startswith('https://at.adobe.com/')
            p.parent.mkdir(exist_ok=True)
            if not p.exists():
                subprocess.run(['curl','--fail','--location','--silent','--show-error','--retry','2','--max-time','180',url,'--output',str(p)],check=True)
            assert p.stat().st_size==row[platform+'Bytes'] and digest(p)==row[platform+'SHA256']
            data=probe(p)
            v=next(s for s in data['streams'] if s['codec_type']=='video')
            a=next(s for s in data['streams'] if s['codec_type']=='audio')
            resolution=f'{v["width"]}x{v["height"]}'
            assert v['codec_name']=='h264' and v['r_frame_rate']=='24/1'
            assert resolution==row[platform+'Resolution']
            assert abs(float(data['format']['duration'])-row['durationSeconds'])<0.08
            assert a['codec_name']=='aac' and a['sample_rate']=='48000'
            if platform=='meta':assert 0<int(a['bit_rate'])<=128000 and int(v['bit_rate'])<=25000000
            if platform=='vk':assert float(data['format']['duration'])<=15.05
            out.update({platform+'Path':str(p),platform+'Bytes':p.stat().st_size,platform+'SHA256':digest(p),platform+'Resolution':resolution,platform+'Probe':data})
            if platform=='meta':out['metaAudioBitrate']=int(a['bit_rate'])
            print('EXACT_PREVIEWED_ASSET_STAGED',row['id'],platform,p.stat().st_size,flush=True)
        rows.append(out)
    QA.parent.mkdir(parents=True,exist_ok=True)
    QA.write_text(json.dumps(dict(id=m['id'],ok=True,stagingOnly=True,published=False,sourceOriginalsVerified=True,exactPreparedCopiesVerified=True,sequence=rows),ensure_ascii=False,indent=2)+'\n')
    print('SIX_EXACT_PREVIEWED_FILES_STAGED_NO_SOCIAL_WRITES',flush=True)

if __name__=='__main__':main()
