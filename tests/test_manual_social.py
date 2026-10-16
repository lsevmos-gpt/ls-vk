import json
import tempfile
import unittest
from pathlib import Path
from scripts.manual_social import reserve, finalize, APPROVAL_PHRASE

class ManualSocialTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name);p=self.root/'requests'/'vk';p.mkdir(parents=True)
        self.job='manualvk0001'
        (p/(self.job+'.json')).write_text(json.dumps({'id':self.job,'approved':True,'type':'story',
            'storyType':'photo','mediaUrl':'https://cdn.example.org/x.png'}),encoding='utf-8')

    def run_reserve(self,**kwargs):
        args=dict(actor='lsevmos-gpt',event='workflow_dispatch',branch='refs/heads/main',run_id='run_1',private=True)
        args.update(kwargs)
        return reserve(self.root,'vk',self.job,APPROVAL_PHRASE,**args)

    def test_public_repository_cannot_publish(self):
        with self.assertRaisesRegex(ValueError,'Private'):
            self.run_reserve(private=False)

    def test_only_owner_main_manual(self):
        for args in ({'actor':'other'},{'event':'push'},{'branch':'refs/heads/test'}):
            with self.assertRaises(ValueError):self.run_reserve(**args)

    def test_replay_is_blocked(self):
        self.run_reserve()
        with self.assertRaisesRegex(ValueError,'earlier attempt'):
            self.run_reserve()

    def test_historical_result_blocks_replay(self):
        r=self.root/'results';r.mkdir(parents=True)
        (r/(self.job+'.json')).write_text('{}')
        with self.assertRaises(ValueError):self.run_reserve()

    def test_accepted_not_equal_published(self):
        self.run_reserve()
        r=self.root/'results';(r/(self.job+'.json')).write_text(json.dumps({'ok':True,'id':self.job,'result':{'id':3}}))
        receipt=finalize(self.root,'vk',self.job,'run_1','0')
        self.assertEqual(json.loads(receipt.read_text())['status'],'submitted_to_provider')
        self.assertNotIn('result',json.loads(receipt.read_text()))

    def test_error_is_not_replayed(self):
        self.run_reserve()
        receipt=finalize(self.root,'vk',self.job,'run_1','1')
        self.assertEqual(json.loads(receipt.read_text())['status'],'manual_review_required')
        with self.assertRaises(ValueError):self.run_reserve()