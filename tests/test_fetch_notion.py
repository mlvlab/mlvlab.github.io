import base64
import hashlib
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

    def test_news_display_text_preserves_native_formatting_and_all_extra_links(self):
        module = self.load()
        row = self.row('news-row', **{'News title': 'Original title', 'Date': '2026-10-29',
                                    'Link 1': 'https://example.org/paper', 'Link Label 1': 'Paper',
                                    'Link 2': 'mailto:lab@example.org', 'Link Label 2': 'Contact',
                                    'Link 3': '/details'})
        row['properties']['Display text'] = {'type': 'rich_text', 'rich_text': [
            {'plain_text': 'Seven', 'annotations': {'bold': True, 'color': 'red'},
             'href': 'https://example.org/news'},
            {'plain_text': ' papers accepted.', 'annotations': {'bold': False, 'color': 'default'},
             'href': None},
        ]}
        data, _ = self.run_main(module, {'news': [row]})
        news = data['news'][0]
        self.assertEqual(news['md'], '[**Seven**](https://example.org/news) papers accepted. '
                         '[Paper](https://example.org/paper) [Contact](mailto:lab@example.org) [Link](/details)')
        self.assertEqual(news.get('segments'), [
            {'text': 'Seven', 'bold': True, 'color': 'red', 'href': 'https://example.org/news'},
            {'text': ' papers accepted.', 'bold': False, 'color': 'default', 'href': ''},
            {'text': ' ', 'bold': False, 'color': 'default', 'href': ''},
            {'text': 'Paper', 'bold': False, 'color': 'default', 'href': 'https://example.org/paper'},
            {'text': ' ', 'bold': False, 'color': 'default', 'href': ''},
            {'text': 'Contact', 'bold': False, 'color': 'default', 'href': 'mailto:lab@example.org'},
            {'text': ' ', 'bold': False, 'color': 'default', 'href': ''},
            {'text': 'Link', 'bold': False, 'color': 'default', 'href': '/details'},
        ])

    def test_news_native_title_formatting_works_for_each_existing_alias(self):
        module = self.load()
        for name in ('News title', 'Title', 'News'):
            with self.subTest(name=name):
                row = self.row('news-row')
                row['properties'][name] = {'type': 'title', 'title': [
                    {'plain_text': 'Seven', 'annotations': {'bold': True, 'color': 'blue'},
                     'href': 'https://example.org/news'},
                ]}
                data, _ = self.run_main(module, {'news': [row]})
                self.assertEqual(data['news'][0].get('segments'), [
                    {'text': 'Seven', 'bold': True, 'color': 'blue', 'href': 'https://example.org/news'},
                ])

    def test_news_missing_empty_and_whitespace_display_text_fall_back_to_title(self):
        module = self.load()
        for display in (None, [], [{'plain_text': ''}],
                        [{'plain_text': ' \n ', 'annotations': {'bold': True, 'color': 'red'}}]):
            with self.subTest(display=display):
                row = self.row('news-row', **{'News title': 'Existing **bold** [link](/paper)'})
                if display is not None:
                    row['properties']['Display text'] = {'type': 'rich_text', 'rich_text': display}
                data, _ = self.run_main(module, {'news': [row]})
                self.assertEqual(data['news'][0]['md'], 'Existing **bold** [link](/paper)')
                self.assertNotIn('segments', data['news'][0])

    def test_plain_display_text_keeps_markdown_and_does_not_add_segments(self):
        module = self.load()
        row = self.row('news-row', **{'News title': 'Old title',
                                    'Display text': '**Seven** papers [accepted](/news)',
                                    'Link 1': '/paper', 'Link Label 1': 'Paper'})
        data, _ = self.run_main(module, {'news': [row]})
        self.assertEqual(data['news'][0]['md'], '**Seven** papers [accepted](/news) [Paper](/paper)')
        self.assertNotIn('segments', data['news'][0])

    def test_news_native_link_alone_creates_segments(self):
        module = self.load()
        row = self.row('news-row')
        row['properties']['News title'] = {'type': 'title', 'title': [
            {'plain_text': 'Read the news', 'annotations': {'bold': False, 'color': 'default'},
             'href': 'https://example.org/news'},
        ]}
        data, _ = self.run_main(module, {'news': [row]})
        self.assertEqual(data['news'][0].get('segments'), [
            {'text': 'Read the news', 'bold': False, 'color': 'default',
             'href': 'https://example.org/news'},
        ])

    def test_news_native_bold_or_color_alone_creates_segments(self):
        module = self.load()
        for annotations in ({'bold': True, 'color': 'default'}, {'bold': False, 'color': 'green'},
                            {'bold': False, 'color': 'yellow_background'}):
            with self.subTest(annotations=annotations):
                row = self.row('news-row')
                row['properties']['Display text'] = {'type': 'rich_text', 'rich_text': [
                    {'plain_text': 'Seven', 'annotations': annotations},
                ]}
                data, _ = self.run_main(module, {'news': [row]})
                self.assertEqual(data['news'][0].get('segments'), [
                    {'text': 'Seven', 'bold': annotations['bold'], 'color': annotations['color'], 'href': ''},
                ])

    def test_news_extra_link_labels_keep_native_color_and_bold(self):
        module = self.load()
        row = self.row('news-row', **{'News title': 'Seven', 'Link 1': '/news'})
        row['properties']['Display text'] = {'type': 'rich_text', 'rich_text': [
            {'plain_text': 'Seven', 'annotations': {'bold': True}},
        ]}
        row['properties']['Link Label 1'] = {'type': 'rich_text', 'rich_text': [
            {'plain_text': 'More', 'annotations': {'bold': True, 'color': 'green'}},
        ]}
        data, _ = self.run_main(module, {'news': [row]})
        self.assertEqual(data['news'][0]['md'], '**Seven** [**More**](/news)')
        self.assertEqual(data['news'][0].get('segments', [])[-1:], [
            {'text': 'More', 'bold': True, 'color': 'green', 'href': '/news'},
        ])

    def test_news_label_only_formatting_activates_segments_and_preserves_all_links(self):
        module = self.load()
        cases = [
            (1, 'Paper', 'Seven papers accepted. [**Paper**](/paper) [Project](/project) [Code](/code)'),
            (2, 'Project', 'Seven papers accepted. [Paper](/paper) [**Project**](/project) [Code](/code)'),
            (3, 'Code', 'Seven papers accepted. [Paper](/paper) [Project](/project) [**Code**](/code)'),
        ]
        for slot, label, bold_md in cases:
            for annotations in ({'bold': True, 'color': 'default'}, {'bold': False, 'color': 'green'},
                                {'bold': False, 'color': 'yellow_background'}):
                with self.subTest(slot=slot, annotations=annotations):
                    row = self.row('news-row', **{
                        'News title': 'Seven papers accepted.',
                        'Link 1': '/paper', 'Link Label 1': 'Paper',
                        'Link 2': '/project', 'Link Label 2': 'Project',
                        'Link 3': '/code', 'Link Label 3': 'Code',
                    })
                    row['properties'][f'Link Label {slot}'] = {'type': 'rich_text', 'rich_text': [
                        {'plain_text': label, 'annotations': annotations},
                    ]}
                    data, _ = self.run_main(module, {'news': [row]})
                    news = data['news'][0]
                    self.assertIn('segments', news)
                    segments = news['segments']
                    self.assertEqual(''.join(part['text'] for part in segments),
                                     'Seven papers accepted. Paper Project Code')
                    links = [part for part in segments if part['href']]
                    self.assertEqual([part['href'] for part in links], ['/paper', '/project', '/code'])
                    self.assertEqual(links[slot - 1]['color'], annotations['color'])
                    self.assertEqual(links[slot - 1]['bold'], annotations['bold'])
                    self.assertEqual(news['md'], bold_md if annotations['bold'] else
                                     'Seven papers accepted. [Paper](/paper) [Project](/project) [Code](/code)')

    def test_news_formatted_labels_without_links_do_not_activate_segments(self):
        module = self.load()
        row = self.row('news-row', **{'News title': 'Existing **bold** [link](/paper)'})
        for slot in (1, 2, 3):
            row['properties'][f'Link Label {slot}'] = {'type': 'rich_text', 'rich_text': [
                {'plain_text': 'Unused label', 'annotations': {'bold': True, 'color': 'green'}},
            ]}
        data, _ = self.run_main(module, {'news': [row]})
        self.assertEqual(data['news'][0]['md'], 'Existing **bold** [link](/paper)')
        self.assertNotIn('segments', data['news'][0])

    def test_news_color_names_are_fixed_and_malformed_values_fall_back_safely(self):
        module = self.load()
        colors = ['default', 'gray', 'brown', 'orange', 'yellow', 'green', 'blue', 'purple', 'pink', 'red',
                  'gray_background', 'brown_background', 'orange_background', 'yellow_background',
                  'green_background', 'blue_background', 'purple_background', 'pink_background', 'red_background']
        bad_colors = ['red\" onclick=\"evil()', 'rebeccapurple', None, {}, []]
        row = self.row('news-row')
        row['properties']['Display text'] = {'type': 'rich_text', 'rich_text': [
            {'plain_text': str(index), 'annotations': {'color': color, 'bold': True}}
            for index, color in enumerate(colors + bad_colors)
        ]}
        data, _ = self.run_main(module, {'news': [row]})
        segments = data['news'][0].get('segments', [])
        self.assertEqual([segment['color'] for segment in segments], colors + ['default'] * len(bad_colors))

    def test_news_does_not_change_generic_rich_and_prop_behavior(self):
        module = self.load()
        parts = [{'plain_text': 'Seven', 'annotations': {'bold': True, 'color': 'red'},
                  'href': 'https://example.org/news'}]
        self.assertEqual(module.rich(parts), '[**Seven**](https://example.org/news)')
        self.assertEqual(module.prop({'Title': {'type': 'title', 'title': parts}}, 'Title'),
                         '[Seven](https://example.org/news)')
        self.assertEqual(module.prop({'Text': {'type': 'rich_text', 'rich_text': parts}}, 'Text'),
                         '[**Seven**](https://example.org/news)')

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
        self.assertEqual(result, f'img/{hashlib.sha256(original).hexdigest()}.webp')

    def test_changed_image_at_same_logical_key_gets_a_new_url(self):
        module = self.load()
        if module.Image is None:
            self.skipTest('Pillow is required to verify image encoding')
        source = self.root / 'paper.png'
        module.Image.new('RGB', (4, 4), 'red').save(source)
        first = module.save_image('pubthumb:20', 'fig', [str(source)])
        original = (module.OUT / first).read_bytes()
        module.Image.new('RGB', (4, 4), 'blue').save(source)
        second = module.save_image('pubthumb:20', 'fig', [str(source)])
        self.assertNotEqual(first, second)
        self.assertEqual((module.OUT / first).read_bytes(), original)
        self.assertNotEqual((module.OUT / second).read_bytes(), original)

    def test_reordered_image_keeps_its_url_after_encoding(self):
        module = self.load()
        if module.Image is None:
            self.skipTest('Pillow is required to verify image encoding')
        module.CFG['image_widths']['fig'] = 2
        source = self.root / 'paper.png'
        module.Image.new('RGB', (4, 4), 'red').save(source)
        first = module.save_image('pubthumb:20', 'fig', [str(source)])
        second = module.save_image('pubthumb:21', 'fig', [str(source)])
        self.assertEqual(first, second)
        encoded = (module.OUT / first).read_bytes()
        self.assertEqual(first, f'img/{hashlib.sha256(encoded).hexdigest()}.webp')
        with module.Image.open(io.BytesIO(encoded)) as image:
            self.assertEqual(image.size, (2, 2))

    def test_social_png_stays_transparent_after_resizing(self):
        module = self.load()
        if module.Image is None:
            self.skipTest('Pillow is required to verify image encoding')
        module.CFG['image_widths']['social'] = 2
        source = self.root / 'icon.png'
        module.Image.new('RGBA', (4, 4), (255, 0, 0, 128)).save(source)
        result = module.save_image('social:0', 'social', [str(source)])
        encoded = (module.OUT / result).read_bytes()
        self.assertEqual(result, f'img/{hashlib.sha256(encoded).hexdigest()}.png')
        with module.Image.open(io.BytesIO(encoded)) as image:
            self.assertEqual(image.format, 'PNG')
            self.assertEqual(image.size, (2, 2))
            self.assertEqual(image.getpixel((0, 0)), (255, 0, 0, 128))

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
