import tempfile
import unittest
from pathlib import Path
from scripts.validate_social import validate_job, validate_directory, safe_public_media_url

class SocialValidationTests(unittest.TestCase):
    def test_accept_valid_vkontakte_story(self):
        job={'id':'new-story01','type':'story','approved':True,'publicContent':True,'storyType':'photo','mediaUrl':'https://static.metricool.com/a.png'}
        self.assertEqual(validate_job('vk','new-story01.json',job),[])

    def test_requires_explicit_approval(self):
        self.assertTrue(validate_job('vk','new-story01.json',{'id':'new-story01','type':'story','storyType':'photo','mediaUrl':'https://cdn.example.com/p.png'}))

    def test_reject_legacy_delete(self):
        self.assertTrue(validate_job('vk','delete001.json',{'id':'delete001','type':'delete-story','approved':True}))

    def test_reject_private_and_signed_urls(self):
        for url in ['https://drive.google.com/file/d/foo/view','https://raw.githubusercontent.com/other/b/main/x.jpg',
                    'https://cdn.example.com/x.jpg?access_token=123','http://cdn.example.com/x.jpg']:
            self.assertFalse(safe_public_media_url(url))

    def test_public_github_media_allowed(self):
        self.assertTrue(safe_public_media_url('https://raw.githubusercontent.com/lsevmos-gpt/ls-vk/main/media/x.png'))

    def test_reject_other_channel_and_bypass(self):
        job={'id':'insta00001','type':'instagram','approved':True,'publicContent':True,'channelId':'other-channel',
             'handle':'wrong','media':[{'type':'image','url':'https://cdn.example.com/x.jpg'}]}
        self.assertTrue(validate_job('buffer','insta00001.json',job))

    def test_valid_buffer_story(self):
        job={'id':'insta00002','type':'instagram','approved':True,'publicContent':True,'handle':'liniya__sporta','postType':'story',
             'media':[{'type':'image','url':'https://cdn.example.com/x.jpg'}]}
        self.assertEqual(validate_job('buffer','insta00002.json',job),[])

    def test_scans_only_new_requests(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'invalid-old01.json').write_text('{broken')
            self.assertTrue(validate_directory('vk',p))
            (p/'invalid-old01.json').unlink()
            self.assertEqual(validate_directory('vk',p),[])