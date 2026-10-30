#!/usr/bin/env python3
"""
render.py — build/site_data.json + build/assets.json + template.html → site/index.html

  python render.py               # render what fetch_notion.py produced
  python render.py --snapshot    # render the verified repository backup (no Notion token needed)
"""
import json, shutil, argparse, sys
from pathlib import Path
from validate_site import validate

HERE = Path(__file__).resolve().parent
CFG = json.load(open(HERE / 'config.json'))
OUT = HERE / CFG['output_dir']

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--snapshot', action='store_true'); args = ap.parse_args()
    if args.snapshot:
        data = json.load(open(HERE / 'snapshot' / 'site_data.json'))
        man = json.load(open(HERE / 'snapshot' / 'manifest.json'))
        errors = validate(data, man['files'], HERE / 'snapshot')
        if errors:
            sys.exit('Snapshot validation failed:\n' + '\n'.join(errors))
        assets = {}
        for key, rel in man['files'].items():
            src = HERE / 'snapshot' / rel; dst = OUT / rel
            dst.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(src, dst)
            assets[key] = rel
    else:
        try:
            data = json.load(open(HERE / 'build' / 'site_data.json'))
            assets = json.load(open(HERE / 'build' / 'assets.json'))
        except FileNotFoundError:
            sys.exit('build/site_data.json not found — run fetch_notion.py first (or use --snapshot).')
        errors = validate(data, assets, OUT)
        if errors:
            sys.exit('Image validation failed:\n' + '\n'.join(errors))
    tpl = open(HERE / 'template.html', encoding='utf-8').read()
    # Crawlers read the initial HTML, including the legacy /home entry point.
    social_meta = (HERE / 'social-meta.html').read_text(encoding='utf-8')
    j = lambda x: json.dumps(x, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    html = tpl.replace('__SOCIAL_META__', social_meta).replace('__ASSETS__', j(assets)).replace('__DATA__', j(data)).replace('__MODE__', 'local')
    head, body = html.split('</style>', 1)
    full = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n' + head + '</style>\n</head>\n<body>\n' + body + '\n</body>\n</html>\n')
    OUT.mkdir(parents=True, exist_ok=True)
    # Always publish the share card, for both live Notion and snapshot builds.
    social_target = OUT / 'assets' / 'social'
    social_target.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(HERE / 'assets' / 'social' / 'mlv-lab-20261030.png',
                    social_target / 'mlv-lab-20261030.png')
    # Repository-owned venue marks are independent of Notion's expiring asset URLs.
    venue_assets = HERE / 'assets' / 'venues'
    if venue_assets.exists():
        target = OUT / 'assets' / 'venues'
        target.mkdir(parents=True, exist_ok=True)
        for asset in venue_assets.iterdir():
            if asset.suffix.lower() in {'.svg', '.png', '.webp'}:
                shutil.copyfile(asset, target / asset.name)
    (OUT / 'index.html').write_text(full, encoding='utf-8')
    # Keep the old Google Sites /home URL working, including on custom domains.
    home = OUT / 'home'
    home.mkdir(exist_ok=True)
    (home / 'index.html').write_text(
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<title>MLV Lab — Redirecting</title>\n' + social_meta + '\n'
        '<script>window.location.replace("/#/home");</script>\n'
        '<meta http-equiv="refresh" content="0; url=/#/home">\n'
        '</head>\n<body>\n'
        '<p><a href="/#/home">Continue to the MLV Lab homepage</a></p>\n'
        '</body>\n</html>\n', encoding='utf-8')
    (OUT / '.nojekyll').write_text('')
    cname = HERE / 'CNAME'
    if cname.exists(): shutil.copyfile(cname, OUT / 'CNAME')
    fav = HERE / 'favicon.png'          # browser-tab icon; replace this file to change it
    if fav.exists(): shutil.copyfile(fav, OUT / 'favicon.png')
    print('wrote', OUT / 'index.html', f'({len(full)/1e6:.2f} MB html, {len(assets)} images)')

if __name__ == '__main__':
    main()
