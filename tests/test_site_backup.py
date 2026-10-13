import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from refresh_snapshot import create_snapshot, read_embedded_data
from validate_site import validate


class SiteBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.image = self.root / 'source.png'
        Image.new('RGB', (3, 2), 'blue').save(self.image)
        self.data = {
            'people': [{'name': 'Alice', 'photo': 'person:1'}],
            'pubs': [{'title': 'A Paper', 'thumb': 'fig:1:0'}],
            'topics': [{'figures': [{'caption': 'A figure', 'img': 'fig:1:0'}]}],
            'photos': [{'caption': 'Lab picnic', 'img': 'photo:0'},
                       {'caption': 'Lab picnic', 'img': 'photo:1'}],
        }
        self.assets = {k: f'img/{k.replace(":", "-")}.png'
                       for k in ('person:1', 'fig:1:0', 'photo:0', 'photo:1')}

    def test_backup_preserves_shared_paper_thumbnail_and_duplicate_caption_aliases(self):
        dest = self.root / 'snapshot'
        create_snapshot(self.data, self.assets, lambda rel: self.image.read_bytes(), dest,
                        metadata={'identities': {'person:1': 'notion-person-id'}})
        manifest = json.loads((dest / 'manifest.json').read_text())
        self.assertEqual(manifest['aliases']['pubthumb']['a paper'], ['fig:1:0'])
        self.assertEqual(manifest['aliases']['photo']['lab picnic'], ['photo:0', 'photo:1'])
        self.assertEqual(manifest['identities']['person:1'], 'notion-person-id')
        self.assertEqual([], validate(self.data, manifest['files'], dest, require_static=False))

    def test_failed_download_does_not_replace_working_snapshot(self):
        dest = self.root / 'snapshot'
        dest.mkdir()
        (dest / 'manifest.json').write_text('{"files": {}}')
        def fail(rel):
            raise OSError('image unavailable')
        with self.assertRaises(OSError):
            create_snapshot(self.data, self.assets, fail, dest)
        self.assertEqual((dest / 'manifest.json').read_text(), '{"files": {}}')

    def test_refresh_keeps_recovery_images_for_hidden_rows(self):
        dest = self.root / 'snapshot'
        create_snapshot(self.data, self.assets, lambda rel: self.image.read_bytes(), dest)
        create_snapshot({}, {}, lambda rel: b'', dest)
        manifest = json.loads((dest / 'manifest.json').read_text())
        archive = manifest['archive']
        key = archive['aliases']['person']['alice'][0]
        self.assertEqual((dest / archive['files'][key]).read_bytes(), self.image.read_bytes())
        self.assertEqual(manifest['files'], {})

    def test_public_refresh_cannot_erase_known_notion_identities(self):
        dest = self.root / 'snapshot'
        create_snapshot(self.data, self.assets, lambda rel: self.image.read_bytes(), dest,
                        metadata={'identities': {'person:1': 'alice-notion-id'}})
        with self.assertRaisesRegex(ValueError, 'from-build'):
            create_snapshot(self.data, self.assets, lambda rel: self.image.read_bytes(), dest)
        self.assertEqual(json.loads((dest / 'manifest.json').read_text())['identities'],
                         {'person:1': 'alice-notion-id'})

    def test_hidden_video_retains_its_stable_lookup_key_across_refreshes(self):
        dest = self.root / 'snapshot'
        create_snapshot({'videos': [{'thumb': 'yt:abc123'}]}, {'yt:abc123': 'img/video.png'},
                        lambda rel: self.image.read_bytes(), dest)
        create_snapshot({}, {}, lambda rel: b'', dest)
        create_snapshot({}, {}, lambda rel: b'', dest)
        archive = json.loads((dest / 'manifest.json').read_text())['archive']
        key = archive['stable_keys']['yt:abc123']
        self.assertEqual((dest / archive['files'][key]).read_bytes(), self.image.read_bytes())

    def test_broken_image_reference_blocks_backup(self):
        with self.assertRaisesRegex(ValueError, 'missing asset'):
            create_snapshot(self.data, {}, lambda rel: b'', self.root / 'snapshot')

    def test_validator_rejects_missing_corrupt_and_remote_images(self):
        cases = [('img/missing.png', 'missing file'),
                 ('img/bad.webp', 'invalid image'),
                 ('https://lh3.googleusercontent.com/sitesv/example', 'local img/ path')]
        (self.root / 'img').mkdir()
        (self.root / 'img/bad.webp').write_text('not an image')
        for rel, message in cases:
            with self.subTest(rel=rel):
                errors = validate({'photos': [{'img': 'photo:0'}]}, {'photo:0': rel},
                                  self.root, require_static=False)
                self.assertTrue(any(message in error for error in errors), errors)

    def test_validator_rejects_path_escape(self):
        errors = validate({}, {'logo': '../source.png'}, self.root, require_static=False)
        self.assertTrue(any('local img/ path' in error for error in errors), errors)

    def test_extracts_json_without_executing_page_scripts(self):
        html = '''<script>throw new Error('do not run');</script>
        <script type="application/json" id="data">{"news":[{"md":"x < y"}]}</script>
        <script id="assets" type="application/json">{"logo":"img/logo.png"}</script>'''
        data, assets = read_embedded_data(html)
        self.assertEqual(data['news'][0]['md'], 'x < y')
        self.assertEqual(assets, {'logo': 'img/logo.png'})


if __name__ == '__main__':
    unittest.main()
