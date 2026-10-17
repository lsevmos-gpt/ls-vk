import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from scripts.auto_social import at_utc, public_url, validate, candidates, await_target

NOW=datetime(2026,10,17,3,0,0,tzinfo=timezone.utc)
DUE='2026-10-17T10:00:00+03:00'

class TimedPublishingTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        for platform in ('vk','buffer'):
            (self.root/'requests'/'scheduled'/platform).mkdir(parents=True)
        (self.root/'media').mkdir()
        (self.root/'media'/'public.png').write_bytes(b'\x89PNG\r\n\x1a\n' + b'example')
    def manifest(self,platform='vk',**overrides):
        base={'id':'birthday-anna20261017','approved':True,'publicContent':True,
              'publishAt':DUE,'type':'story','storyType':'photo','media':'media/public.png'}
        if platform=='buffer':
            base.update(type='instagram',postType='story',publishNow=False,handle='liniya__sporta',
                       media=[{'type':'image','url':'https://cdn.example.com/anna.png'}],
                       dueAt='2026-10-17T07:00:00Z',isAiGenerated=True,text='')
            base.pop('storyType',None)
        base.update(overrides)
        path=self.root/'requests'/'scheduled'/platform/(base['id']+'.json')
        path.write_text(json.dumps(base),encoding='utf-8')
        return path
    def test_vk_story_valid_public_local(self):
        self.assertEqual(validate('vk',self.manifest(),self.root,now=NOW)[1].hour,7)
    def test_vkbatches_valid(self):
        p=self.manifest(type='story-batch',stories=[{'media':'media/public.png','storyType':'photo'}]);
        self.assertEqual(validate('vk',p,self.root,now=NOW)[0]['type'],'story-batch')
    def test_buffer_story_valid_future(self):
        self.assertEqual(validate('buffer',self.manifest('buffer'),self.root,now=NOW)[1].hour,7)
    def test_public_repo_media_allowed_but_other_github_blocked(self):
        self.assertTrue(public_url('https://raw.githubusercontent.com/lsevmos-gpt/ls-vk/main/media/a.png'))
        self.assertFalse(public_url('https://raw.githubusercontent.com/other/repo/main/media/a.png'))
        self.assertFalse(public_url('https://drive.google.com/file/d/123/view'))
    def test_requires_approval(self):
        with self.assertRaisesRegex(ValueError,'approved'):
            validate('vk',self.manifest(approved=False),self.root,now=NOW)
    def test_rejects_secret_and_wrong_channel(self):
        with self.assertRaisesRegex(ValueError,'Sensitive'):
            validate('vk',self.manifest(secret='NOT_ALLOWED'),self.root,now=NOW)
        with self.assertRaisesRegex(ValueError,'handle'):
            validate('buffer',self.manifest('buffer',handle='wrong'),self.root,now=NOW)
    def test_vk_due_window_and_no_duplicate(self):
        p=self.manifest(publishAt='2026-10-17T03:45:00Z')
        self.assertEqual(len(candidates('vk',self.root,now=NOW)),1)
        target=self.root/'results'/'scheduled'/'vk'/(p.stem+'.json')
        target.parent.mkdir(parents=True);target.write_text('{}')
        self.assertEqual(candidates('vk',self.root,now=NOW),[])
    def test_vk_early_request_waits_for_scheduler(self):
        self.manifest()
        self.assertEqual(candidates('vk',self.root,now=NOW),[])
    def test_buffer_can_be_submitted_early(self):
        self.manifest('buffer')
        self.assertEqual(len(candidates('buffer',self.root,now=NOW)),1)
    def test_expired_never_runs(self):
        self.manifest(publishAt='2026-10-17T05:00:00+03:00')
        self.assertEqual(candidates('vk',self.root,now=datetime(2026,10,17,3,1,tzinfo=timezone.utc)),[])
    def test_vk_late_skips(self):
        with self.assertRaisesRegex(ValueError,'Missed exact'):
            await_target(NOW,sleep=lambda x:None,now_fn=lambda:NOW+timedelta(seconds=6))
    def test_exact_time_utc(self):
        self.assertEqual(at_utc(DUE),datetime(2026,10,17,7,tzinfo=timezone.utc))
    def test_missing_file_blocked(self):
        with self.assertRaisesRegex(ValueError,'publicly accessible'):
            validate('vk',self.manifest(media='media/other.png'),self.root,now=NOW)
    def test_buffer_millisecond_dueat_parses(self):
        self.assertEqual(at_utc('2026-10-17T07:00:00.000Z'),datetime(2026,10,17,7,tzinfo=timezone.utc))

    def test_wrong_buffer_dueat_blocked(self):
        with self.assertRaisesRegex(ValueError,'equal'):
            validate('buffer',self.manifest('buffer',dueAt='2026-10-17T08:00:00Z'),self.root,now=NOW)

if __name__=='__main__':unittest.main()