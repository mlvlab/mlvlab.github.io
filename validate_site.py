#!/usr/bin/env python3
"""Reject incomplete image bundles before they replace the published site."""
import argparse
import json
from pathlib import Path, PurePosixPath

from PIL import Image

HERE = Path(__file__).resolve().parent
STATIC_IMAGES = ('logo', 'hero', 'collab', 'research_banner', 'banner_people', 'banner_photos')


def local_image_path(rel):
    path = PurePosixPath(str(rel))
    return (str(rel).startswith('img/') and not path.is_absolute()
            and '..' not in path.parts and '\\' not in str(rel)
            and '?' not in str(rel) and '#' not in str(rel))


def image_references(data):
    for collection, field in (('people', 'photo'), ('pubs', 'thumb'), ('photos', 'img'),
                              ('highlights', 'img'), ('videos', 'thumb'), ('socials', 'icon')):
        for row in data.get(collection, []):
            if row.get(field):
                yield row[field]
    for topic in data.get('topics', []):
        for figure in topic.get('figures', []):
            if figure.get('img'):
                yield figure['img']


def validate(data, assets, root, require_static=True):
    errors = []
    required = set(image_references(data))
    if require_static:
        required.update(STATIC_IMAGES)
    for key in sorted(required - assets.keys()):
        errors.append(f'missing asset: {key}')
    checked = set()
    for key, rel in assets.items():
        if not local_image_path(rel):
            errors.append(f'{key}: expected a local img/ path, got {rel}')
            continue
        if rel in checked:
            continue
        checked.add(rel)
        path = Path(root) / rel
        if not path.is_file():
            errors.append(f'{key}: missing file {rel}')
            continue
        try:
            with Image.open(path) as im:
                im.verify()
            with Image.open(path) as im:
                im.load()
        except Exception as error:
            errors.append(f'{key}: invalid image {rel}: {error}')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', action='store_true', help='validate the repository backup')
    args = parser.parse_args()
    if args.snapshot:
        root = HERE / 'snapshot'
        data = json.loads((root / 'site_data.json').read_text())
        manifest = json.loads((root / 'manifest.json').read_text())
        assets = manifest['files']
    else:
        config = json.loads((HERE / 'config.json').read_text())
        root = HERE / config['output_dir']
        data = json.loads((HERE / 'build/site_data.json').read_text())
        assets = json.loads((HERE / 'build/assets.json').read_text())
    errors = validate(data, assets, root)
    if args.snapshot:
        errors += validate({}, manifest.get('archive', {}).get('files', {}), root, require_static=False)
    if errors:
        raise SystemExit('Image validation failed:\n' + '\n'.join(errors))
    print(f'Validated {len(assets)} image references and all local image files.')


if __name__ == '__main__':
    main()
