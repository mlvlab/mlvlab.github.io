#!/usr/bin/env python3
"""Make a complete, verified backup from a published site or a fresh Notion build.

  python refresh_snapshot.py --from-site https://mlvlab.github.io/
  python refresh_snapshot.py --from-build --output build/site-backup

The destination is replaced only after every image has been saved and verified.
No Notion token or temporary signed Notion file URLs are stored in the backup.
"""
import argparse
import hashlib
import io
import json
import re
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

from PIL import Image
from validate_site import image_references, local_image_path, validate

HERE = Path(__file__).resolve().parent


def normalize_label(value):
    value = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', str(value or ''))
    return re.sub(r'\s+', ' ', value.replace('\xa0', ' ')).strip().lower()


def read_embedded_data(html):
    class DataParser(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.active = None
            self.parts = {}

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == 'script' and attrs.get('id') in ('data', 'assets'):
                self.active = attrs['id']
                self.parts[self.active] = ''

        def handle_data(self, text):
            if self.active:
                self.parts[self.active] += text

        def handle_endtag(self, tag):
            if tag == 'script':
                self.active = None

    parser = DataParser()
    parser.feed(html)
    try:
        return json.loads(parser.parts['data']), json.loads(parser.parts['assets'])
    except (KeyError, ValueError) as error:
        raise ValueError('Expected an MLV site with embedded data and assets JSON') from error


def metadata_for(data, assets, supplied=None):
    supplied = supplied or {}
    labels, aliases = {}, {}

    def add(category, key, label):
        if key not in assets:
            return
        label = str(label or '')
        if category != 'pubthumb' or key.startswith('pubthumb:'):
            labels[key] = label
        normalized = normalize_label(label)
        if normalized:
            keys = aliases.setdefault(category, {}).setdefault(normalized, [])
            if key not in keys:
                keys.append(key)

    for category, collection, field, label_field in (
            ('person', 'people', 'photo', 'name'), ('photo', 'photos', 'img', 'caption'),
            ('slide', 'highlights', 'img', 'caption'), ('pubthumb', 'pubs', 'thumb', 'title')):
        for row in data.get(collection, []):
            add(category, row.get(field, ''), row.get(label_field, ''))
    for topic in data.get('topics', []):
        for row in topic.get('figures', []):
            add('fig', row.get('img', ''), row.get('caption', ''))
    # Preserve labels for images not rendered directly (e.g. publication-only figures).
    for key, label in supplied.get('labels', {}).items():
        if key in assets and key not in labels:
            add(key.split(':')[0], key, label)
    for category, values in supplied.get('aliases', {}).items():
        for label, keys in values.items():
            normalized = normalize_label(label)
            if not normalized:
                continue
            for key in keys:
                if key in assets:
                    saved = aliases.setdefault(category, {}).setdefault(normalized, [])
                    if key not in saved:
                        saved.append(key)
    identities = {k: v for k, v in supplied.get('identities', {}).items() if k in assets}
    return {'labels': labels, 'aliases': aliases, 'identities': identities}


def preserve_previous(previous, source_root, staged):
    """Keep older fallbacks separate from the currently displayed site data."""
    archive = {'files': {}, 'labels': {}, 'identities': {}, 'aliases': {}, 'stable_keys': {}}
    for collection in (previous, previous.get('archive', {})):
        remap = {}
        for key, rel in collection.get('files', {}).items():
            if not local_image_path(rel):
                raise ValueError(f'Invalid previous backup image path: {rel}')
            content = (source_root / rel).read_bytes()
            digest = hashlib.sha256(content).hexdigest()
            label = collection.get('labels', {}).get(key, '')
            identity = collection.get('identities', {}).get(key, '')
            category = key.split(':')[0]
            stable = hashlib.sha256(json.dumps([category, digest, identity, label, key if not identity else '']).encode()).hexdigest()[:24]
            archived_key = key if ':archived:' in key else f'{category}:archived:{stable}'
            target = f'img/{digest}{Path(rel).suffix}'
            (staged / target).write_bytes(content)
            archive['files'][archived_key] = target
            if label:
                archive['labels'][archived_key] = label
            if identity:
                archive['identities'][archived_key] = identity
            remap[key] = archived_key
            if category not in ('person', 'photo', 'fig', 'slide', 'pubthumb') and ':archived:' not in key:
                archive['stable_keys'].setdefault(key, archived_key)
        for original, key in collection.get('stable_keys', {}).items():
            if key in remap:
                archive['stable_keys'].setdefault(original, remap[key])
        metadata = metadata_for({}, collection.get('files', {}), collection)
        for category, values in metadata['aliases'].items():
            for label, keys in values.items():
                saved = archive['aliases'].setdefault(category, {}).setdefault(label, [])
                for key in keys:
                    if remap[key] not in saved:
                        saved.append(remap[key])
    errors = validate({}, archive['files'], staged, require_static=False)
    if errors:
        raise ValueError('\n'.join(errors))
    return archive


def create_snapshot(data, assets, read_asset, destination, metadata=None, source='', previous_root=None):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    previous_root = Path(previous_root) if previous_root else destination
    manifest_path = previous_root / 'manifest.json'
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    if (previous.get('identities') or previous.get('archive', {}).get('identities')) and metadata is None:
        raise ValueError('This backup has Notion row identities. Use --from-build to preserve them; '
                         'a public-site capture cannot safely replace it.')
    missing = sorted(set(image_references(data)) - assets.keys())
    if missing:
        raise ValueError('missing asset: ' + ', '.join(missing))
    for rel in assets.values():
        if not local_image_path(rel):
            raise ValueError(f'Expected a local img/ path: {rel}')
    with tempfile.TemporaryDirectory(prefix='.snapshot-', dir=destination.parent) as temporary:
        staged = Path(temporary) / 'ready'
        (staged / 'img').mkdir(parents=True)
        files, hashes, by_source = {}, {}, {}
        for key, rel in assets.items():
            if rel not in by_source:
                content = read_asset(rel)
                with Image.open(io.BytesIO(content)) as image:
                    image.load()
                    extension = {'JPEG': 'jpg', 'PNG': 'png', 'WEBP': 'webp', 'GIF': 'gif'}.get(image.format)
                if not extension:
                    raise ValueError(f'Unsupported image format: {rel}')
                digest = hashlib.sha256(content).hexdigest()
                target = f'img/{digest}.{extension}'
                (staged / target).write_bytes(content)
                by_source[rel] = target, digest
            files[key], hashes[key] = by_source[rel]
        errors = validate(data, files, staged, require_static=False)
        if errors:
            raise ValueError('\n'.join(errors))
        manifest = {'captured_at': datetime.now(timezone.utc).isoformat(),
                    'source': source, 'files': files, 'sha256': hashes,
                    **metadata_for(data, assets, metadata)}
        manifest['archive'] = preserve_previous(previous, previous_root, staged)
        for name, payload in (('site_data.json', data), ('manifest.json', manifest)):
            (staged / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        previous = Path(temporary) / 'previous'
        if destination.exists():
            destination.rename(previous)
        try:
            staged.rename(destination)
        except Exception:
            if previous.exists():
                previous.rename(destination)
            raise
    return manifest


def download(url):
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'MLV-site-backup/1.0'})
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except (OSError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--from-site', metavar='URL')
    source.add_argument('--from-build', action='store_true')
    parser.add_argument('--output', type=Path, default=HERE / 'snapshot')
    args = parser.parse_args()
    metadata = None
    if args.from_site:
        parsed = urlparse(args.from_site)
        if parsed.scheme not in ('http', 'https') or not parsed.netloc:
            parser.error('--from-site must be an http(s) site URL')
        base = args.from_site.rstrip('/') + '/'
        data, assets = read_embedded_data(download(base).decode('utf-8'))
        reader = lambda rel: download(urljoin(base, rel))
        source_name = base
    else:
        data = json.loads((HERE / 'build/site_data.json').read_text())
        assets = json.loads((HERE / 'build/assets.json').read_text())
        config = json.loads((HERE / 'config.json').read_text())
        image_root = HERE / config['output_dir']
        reader = lambda rel: (image_root / rel).read_bytes()
        meta_path = HERE / 'build/image_metadata.json'
        if meta_path.exists():
            metadata = json.loads(meta_path.read_text())
        source_name = 'Notion build: ' + data.get('generated', '')
    # A workflow artifact should include the repository's recovery images too.
    previous_root = None if (args.output / 'manifest.json').exists() else HERE / 'snapshot'
    manifest = create_snapshot(data, assets, reader, args.output, metadata, source_name, previous_root)
    print(f'Saved {len(manifest["files"])} image references and site content to {args.output}')


if __name__ == '__main__':
    main()
