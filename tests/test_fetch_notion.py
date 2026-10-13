import base64
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout, redirect_stderr


ROOT = Path(__file__).resolve().parents[1]
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a1XkAAAAASUVORK5CYII=')


class ImageFallbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.snapshot = self.root / 'snapshot'
        self.snapshot.mkdir()

    def load(self, files=None, labels=None, identities=None, aliases=None, archive=None):
        manifest = {'files': files or {}, 'labels': labels or {},
                    'identities': identities or {}, 'aliases': aliases or {},
                    'archive': archive or {}}
        (self.snapshot / 'manifest.json').write_text(json.dumps(manifest))
        config = json.loads((ROOT / 'config.json').read_text())
        config['youtube_channel_id'] = ''
        (self.root / 'config.json').write_text(json.dumps(config))
        source = self.root / 'fetch_notion.py'
        source.write_text((ROOT / 'fetch_notion.py').read_text())
        spec = importlib.util.spec_from_file_location('fetch_under_test', source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_reordered_figure_uses_caption_instead_of_previous_row_number(self):
        module = self.load({'fig:1:0': 'old.webp', 'fig:2:0': 'wanted.webp'},
                           {'fig:1:0': 'Another paper', 'fig:2:0': 'Target paper'})
        self.assertEqual(module.snapshot_file('fig:1:0', 'fig', 'Target paper'),
                         self.snapshot / 'wanted.webp')

    def test_new_slide_does_not_take_unrelated_positional_image(self):
        module = self.load({'slide:0': 'old.webp'}, {'slide:0': 'Previous event'})
        self.assertIsNone(module.snapshot_file('slide:0', 'slide', 'New event'))

    def test_publication_title_alias_can_reuse_a_figure(self):
        module = self.load({'fig:3:0': 'paper.webp'}, {'fig:3:0': 'Figure caption'},
                           aliases={'pubthumb': {'paper title': ['fig:3:0']}})
        self.assertEqual(module.snapshot_file('pubthumb:1', 'fig', 'Paper title'),
                         self.snapshot / 'paper.webp')

    def test_repeated_lookup_does_not_consume_next_duplicate_photo(self):
        module = self.load({'photo:0': 'first.webp', 'photo:1': 'second.webp'},
                           {'photo:0': 'Lab picnic', 'photo:1': 'Lab picnic'})
        self.assertEqual(module.snapshot_file('photo:8', 'photo', 'Lab picnic'),
                         self.snapshot / 'first.webp')
        self.assertEqual(module.snapshot_file('photo:8', 'photo', 'Lab picnic'),
                         self.snapshot / 'first.webp')
        self.assertEqual(module.snapshot_file('photo:9', 'photo', 'Lab picnic'),
                         self.snapshot / 'second.webp')

    def test_known_but_missing_snapshot_file_fails_the_build(self):
        module = self.load({'hero': 'missing.webp'})
        with self.assertRaises(RuntimeError):
            module.save_image('hero', 'hero', [])

    def test_expired_google_sites_source_without_backup_fails_the_build(self):
        module = self.load()
        with self.assertRaises(RuntimeError):
            module.save_image('person:1', 'person',
                              ['https://lh3.googleusercontent.com/sitesv/expired'], label='New person')

    def test_intentionally_absent_optional_photo_is_allowed(self):
        module = self.load()
        self.assertEqual(module.save_image('person:1', 'person', [], label='New person'), '')

    def test_text_preview_tolerates_unavailable_images(self):
        module = self.load({'hero': 'missing.webp'})
        with redirect_stderr(io.StringIO()):
            self.assertEqual(module.save_image('hero', 'hero', [], no_images=True), '')

    def test_row_identity_survives_both_caption_edit_and_reordering(self):
        module = self.load({'fig:1:0': 'other.webp', 'fig:2:0': 'wanted.webp'},
                           {'fig:1:0': 'Renamed caption', 'fig:2:0': 'Old caption'},
                           identities={'fig:1:0': 'other-row', 'fig:2:0': 'same-row'})
        self.assertEqual(module.snapshot_file('fig:1:0', 'fig', 'Renamed caption', source_id='same-row'),
                         self.snapshot / 'wanted.webp')

    def test_caption_match_cannot_override_conflicting_known_row_identity(self):
        module = self.load({'photo:0': 'other.webp'}, {'photo:0': 'Lab picnic'},
                           identities={'photo:0': 'other-row'})
        self.assertIsNone(module.snapshot_file('photo:9', 'photo', 'Lab picnic', source_id='new-row'))

    def test_publication_alias_accepts_the_reused_figures_own_identity(self):
        module = self.load({'fig:1:0': 'paper.webp'}, {'fig:1:0': 'Caption'},
                           identities={'fig:1:0': 'figure-row'},
                           aliases={'pubthumb': {'paper title': ['fig:1:0']}})
        self.assertEqual(module.snapshot_file('pubthumb:1', 'fig', 'Paper title', source_id='paper-row'),
                         self.snapshot / 'paper.webp')

    def test_two_publications_can_share_an_explicitly_aliased_figure_backup(self):
        module = self.load({'fig:1:0': 'paper.webp'}, {'fig:1:0': 'Figure caption'},
                           aliases={'pubthumb': {'first paper': ['fig:1:0'],
                                                'second paper': ['fig:1:0']}})
        self.assertEqual(module.snapshot_file('pubthumb:1', 'fig', 'First paper'),
                         self.snapshot / 'paper.webp')
        self.assertEqual(module.snapshot_file('pubthumb:2', 'fig', 'Second paper'),
                         self.snapshot / 'paper.webp')

    def row(self, identity, **values):
        props = {}
        for key, value in values.items():
            if isinstance(value, list):
                props[key] = {'type': 'relation', 'relation': [{'id': v} for v in value]}
            elif isinstance(value, int):
                props[key] = {'type': 'number', 'number': value}
            else:
                props[key] = {'type': 'rich_text', 'rich_text': [{'plain_text': value}]}
        return {'id': identity, 'created_time': '2026-10-13T00:00:00Z', 'properties': props}

    def run_main(self, module, tables, argv=None, download=None):
        sources = {module.CFG['data_sources'][name]: rows for name, rows in tables.items()}
        with patch.object(module, 'TOKEN', 'test-token'), \
                patch.object(module, 'query_all', side_effect=lambda source: sources.get(source, [])), \
                patch.object(module, 'fetch_bytes', side_effect=download or OSError('offline')), \
                patch('sys.argv', ['fetch_notion.py'] + (argv or [])), \
                redirect_stdout(io.StringIO()):
            module.main()
        return json.loads((self.root / 'build' / 'site_data.json').read_text()), \
            json.loads((self.root / 'build' / 'assets.json').read_text())

    def test_main_preserves_row_ids_and_shared_publication_alias_in_backup_metadata(self):
        module = self.load({'person:5': 'person.png', 'photo:5': 'photo.png',
                            'slide:5': 'slide.png', 'fig:5:0': 'figure.png'},
                           {'person:5': 'Old name', 'photo:5': 'Old photo',
                            'slide:5': 'Old highlight', 'fig:5:0': 'Old figure'},
                           identities={'person:5': 'person-row', 'photo:5': 'photo-row',
                                       'slide:5': 'slide-row', 'fig:5:0': 'figure-row'})
        for name in ['person.png', 'photo.png', 'slide.png', 'figure.png']:
            (self.snapshot / name).write_bytes(PNG)
        data, assets = self.run_main(module, {
            'people': [self.row('person-row', Name='Renamed person')],
            'photos': [self.row('photo-row', Caption='Renamed photo')],
            'highlights': [self.row('slide-row', Caption='Renamed highlight')],
            'figures': [self.row('figure-row', Caption='Renamed figure', Publication=['paper-row'])],
            'publications': [self.row('paper-row', Title='Paper title')],
        })
        self.assertEqual(data['people'][0]['photo'], 'person:1')
        self.assertEqual(data['photos'][0]['img'], 'photo:0')
        self.assertEqual(data['highlights'][0]['img'], 'slide:0')
        self.assertEqual(data['pubs'][0]['thumb'], 'fig:0:0')
        metadata = json.loads((self.root / 'build' / 'image_metadata.json').read_text())
        self.assertEqual(metadata['identities'], {'person:1': 'person-row', 'photo:0': 'photo-row',
                                                  'slide:0': 'slide-row', 'fig:0:0': 'figure-row'})
        self.assertEqual(metadata['aliases']['pubthumb']['paper title'], ['fig:0:0'])
        self.assertEqual(metadata['labels']['fig:0:0'], 'Renamed figure')
        self.assertEqual(set(assets), {'person:1', 'photo:0', 'slide:0', 'fig:0:0'})

    def test_failed_upload_uses_valid_related_figure_before_losing_thumbnail(self):
        module = self.load({'fig:0:0': 'figure.png'}, {'fig:0:0': 'Figure caption'})
        (self.snapshot / 'figure.png').write_bytes(PNG)
        paper = self.row('paper-row', Title='Paper title')
        paper['properties']['Thumbnail File'] = {'type': 'files', 'files': [
            {'external': {'url': 'https://example.invalid/expired.png'}}]}
        data, assets = self.run_main(module, {
            'figures': [self.row('figure-row', Caption='Figure caption', Publication=['paper-row'])],
            'publications': [paper],
        })
        self.assertTrue(data['pubs'][0]['thumb'])
        self.assertIn(data['pubs'][0]['thumb'], assets)

    def test_unavailable_figure_relation_does_not_mask_valid_publication_thumbnail(self):
        module = self.load()
        data, assets = self.run_main(module, {
            'figures': [self.row('figure-row', Caption='Empty figure', Publication=['paper-row'])],
            'publications': [self.row('paper-row', Title='Paper title',
                                      **{'Thumbnail URL': 'https://example.invalid/paper.png'})],
        }, download=lambda url: PNG)
        self.assertEqual(data['pubs'][0]['thumb'], 'pubthumb:1')
        self.assertIn('pubthumb:1', assets)

    def test_publication_without_current_source_recovers_title_matched_backup(self):
        module = self.load({'pubthumb:9': 'paper.png'}, {'pubthumb:9': 'Paper title'})
        (self.snapshot / 'paper.png').write_bytes(PNG)
        data, assets = self.run_main(module, {'publications': [self.row('paper-row', Title='Paper title')]})
        self.assertEqual(data['pubs'][0]['thumb'], 'pubthumb:1')
        self.assertIn('pubthumb:1', assets)

    def test_auto_video_thumbnail_failure_is_not_misreported_as_optional_feed_failure(self):
        module = self.load()
        module.CFG['youtube_channel_id'] = 'channel'
        with patch.object(module, 'youtube_feed', return_value=[
                {'id': 'abc123def45', 'title': 'New video', 'published': '2026-10-13'}]), \
                redirect_stderr(io.StringIO()), self.assertRaises(RuntimeError):
            self.run_main(module, {})

    def test_local_webp_backup_is_copied_without_repeated_lossy_encoding(self):
        module = self.load({'photo:0': 'photo.webp'}, {'photo:0': 'Lab picnic'})
        if module.Image is None:
            self.skipTest('Pillow is required to verify image encoding')
        buffer = io.BytesIO()
        module.Image.new('RGB', (4, 4), (123, 57, 211)).save(buffer, format='WEBP', lossless=True)
        original = buffer.getvalue()
        (self.snapshot / 'photo.webp').write_bytes(original)
        result = module.save_image('photo:2', 'photo', [], label='Lab picnic')
        self.assertEqual((self.root / 'site' / result).read_bytes(), original)

    def test_restored_hidden_row_recovers_archived_image_by_identity_after_rename(self):
        module = self.load(archive={
            'files': {'photo:archived:abcd': 'hidden.png'},
            'labels': {'photo:archived:abcd': 'Old caption'},
            'identities': {'photo:archived:abcd': 'hidden-row'},
            'aliases': {'photo': {'old caption': ['photo:archived:abcd']}},
        })
        (self.snapshot / 'hidden.png').write_bytes(PNG)
        data, assets = self.run_main(module, {
            'photos': [self.row('hidden-row', Caption='Restored and renamed photo')],
        })
        self.assertEqual(data['photos'], [{'img': 'photo:0', 'caption': 'Restored and renamed photo'}])
        self.assertIn('photo:0', assets)

    def test_archive_publication_alias_can_recover_hidden_shared_figure(self):
        module = self.load(archive={
            'files': {'fig:archived:abcd': 'hidden.webp'},
            'labels': {'fig:archived:abcd': 'Old caption'},
            'identities': {'fig:archived:abcd': 'figure-row'},
            'aliases': {'pubthumb': {'hidden paper': ['fig:archived:abcd']}},
        })
        self.assertEqual(module.snapshot_file('pubthumb:1', 'fig', 'Hidden paper', source_id='paper-row'),
                         self.snapshot / 'hidden.webp')

    def test_active_backup_wins_over_archived_copy_of_same_row(self):
        module = self.load({'photo:1': 'current.webp'}, {'photo:1': 'Current caption'},
                           identities={'photo:1': 'same-row'}, archive={
                               'files': {'photo:archived:abcd': 'old.webp'},
                               'labels': {'photo:archived:abcd': 'Old caption'},
                               'identities': {'photo:archived:abcd': 'same-row'},
                           })
        self.assertEqual(module.snapshot_file('photo:9', 'photo', 'Old caption', source_id='same-row'),
                         self.snapshot / 'current.webp')

    def test_active_semantic_label_wins_over_archive_alias(self):
        module = self.load({'photo:1': 'current.webp'}, {'photo:1': 'Lab picnic'}, archive={
            'files': {'photo:archived:abcd': 'old.webp'},
            'aliases': {'photo': {'lab picnic': ['photo:archived:abcd']}},
        })
        self.assertEqual(module.snapshot_file('photo:9', 'photo', 'Lab picnic'),
                         self.snapshot / 'current.webp')

    def test_hidden_youtube_thumbnail_recovers_archived_stable_key_when_urls_fail(self):
        module = self.load(archive={
            'files': {'yt:archived:abcd': 'hidden-video.png'},
            'stable_keys': {'yt:abc123def45': 'yt:archived:abcd'},
        })
        (self.snapshot / 'hidden-video.png').write_bytes(PNG)
        with patch.object(module, 'fetch_bytes', side_effect=OSError('offline')):
            result = module.save_image('yt:abc123def45', 'yt',
                                       ['https://i.ytimg.com/vi/abc123def45/hq720.jpg'])
        self.assertTrue(result)
        self.assertTrue((self.root / 'site' / result).is_file())

    def test_active_youtube_thumbnail_wins_over_archived_stable_key(self):
        module = self.load({'yt:abc123def45': 'current.webp'}, archive={
            'files': {'yt:archived:abcd': 'old.webp'},
            'stable_keys': {'yt:abc123def45': 'yt:archived:abcd'},
        })
        self.assertEqual(module.snapshot_file('yt:abc123def45', 'yt'),
                         self.snapshot / 'current.webp')


if __name__ == '__main__':
    unittest.main()
