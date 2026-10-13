#!/usr/bin/env python3
"""
fetch_notion.py — Notion "MLV Lab homepage DB" → site_data.json (+ images)

Reads the 10 databases under the "MLV Lab homepage DB" page through the official
Notion API and writes:
  build/site_data.json      the data the template renders
  site/img/…                every image the site needs (downloaded/resized)

Usage:
  export NOTION_TOKEN=secret_xxx          # internal integration token
  python fetch_notion.py                  # full fetch
  python fetch_notion.py --no-images      # skip image downloads (fast, text only)

Image priority for every row: "… File" (uploaded to Notion) > "… URL" > snapshot/ copy.
The checked-in image backup keeps the site independent of expired source URLs.
An unavailable image with a configured source or backup stops a full build.
"""
import os, sys, json, re, io, hashlib, time, argparse, urllib.request, urllib.error
from pathlib import Path

HERE = Path(__file__).resolve().parent
CFG = json.loads((HERE / 'config.json').read_text(encoding='utf-8'))
TOKEN = os.environ.get('NOTION_TOKEN', '')
API = 'https://api.notion.com/v1'
HEADERS = {'Authorization': f'Bearer {TOKEN}', 'Notion-Version': CFG['notion_version'], 'Content-Type': 'application/json'}
OUT = HERE / CFG['output_dir']
IMG = OUT / 'img'
BUILD = HERE / 'build'

try:
    from PIL import Image
except ImportError:
    Image = None

# ----------------------------------------------------------------------------- Notion API
def api(method, path, body=None, retries=4):
    for attempt in range(retries):
        req = urllib.request.Request(API + path, method=method, headers=HEADERS,
                                     data=json.dumps(body).encode() if body is not None else None)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                time.sleep(2 ** attempt); continue
            print('Notion API error', e.code, e.read().decode()[:400], file=sys.stderr); raise
    raise RuntimeError('Notion API: too many retries for ' + path)

def query_all(ds_id):
    rows, cursor = [], None
    while True:
        body = {'page_size': 100}
        if cursor: body['start_cursor'] = cursor
        res = api('POST', f'/data_sources/{ds_id}/query', body)
        rows += res.get('results', [])
        if not res.get('has_more'): break
        cursor = res['next_cursor']
    return rows

def blocks(page_id):
    out, cursor = [], None
    while True:
        q = f'/blocks/{page_id}/children?page_size=100' + (f'&start_cursor={cursor}' if cursor else '')
        res = api('GET', q)
        out += res.get('results', [])
        if not res.get('has_more'): break
        cursor = res['next_cursor']
    return out

# ----------------------------------------------------------------------------- property helpers
def rich(arr):
    """rich_text array → markdown (bold + links)."""
    s = ''
    for t in arr or []:
        txt = t.get('plain_text', '')
        if t.get('annotations', {}).get('bold'): txt = f'**{txt}**'
        if t.get('href'): txt = f'[{txt}]({t["href"]})'
        s += txt
    return s

def plain(props, name, default=''):
    """Read a title/rich_text property as plain text (no markdown, no auto-links)."""
    p = props.get(name)
    if not p: return default
    arr = p.get(p['type']) if p['type'] in ('title', 'rich_text') else None
    if arr is None: return prop(props, name, default=default)
    return ''.join(t.get('plain_text', '') for t in arr).strip()

def prop(props, *names, default=''):
    """Read a property by (any of) its name(s), returning a plain Python value."""
    for n in names:
        p = props.get(n)
        if p is None: continue
        t = p['type']
        if t == 'title': return rich(p['title']).replace('**', '')
        if t == 'rich_text': return rich(p['rich_text'])
        if t == 'select': return (p['select'] or {}).get('name', '')
        if t == 'multi_select': return [o['name'] for o in p['multi_select']]
        if t == 'number': return p['number']
        if t == 'checkbox': return bool(p['checkbox'])
        if t in ('url', 'email', 'phone_number'): return p[t] or ''
        if t == 'date': return (p['date'] or {}).get('start', '') or ''
        if t == 'relation': return [r['id'] for r in p['relation']]
        if t == 'files':
            out = []
            for f in p['files']:
                out.append(f.get('file', {}).get('url') or f.get('external', {}).get('url') or '')
            return [u for u in out if u]
        if t == 'formula': return p['formula'].get(p['formula']['type'], '')
    return default

def body_markdown(page_id):
    """Page body → simple markdown (headings, paragraphs, bullets)."""
    lines = []
    for b in blocks(page_id):
        t = b['type']; d = b.get(t, {})
        if t == 'paragraph': lines.append(rich(d.get('rich_text')))
        elif t in ('heading_1', 'heading_2', 'heading_3'): lines.append('\n' + '#' * int(t[-1]) + ' ' + rich(d.get('rich_text')) + '\n')
        elif t == 'bulleted_list_item': lines.append('- ' + rich(d.get('rich_text')))
        elif t == 'numbered_list_item': lines.append('- ' + rich(d.get('rich_text')))
        elif t == 'quote': lines.append('> ' + rich(d.get('rich_text')))
        elif t == 'divider': lines.append('')
    return '\n'.join(lines).strip()

def sort_rows(rows, key='Order', desc=False):
    return sorted(rows, key=lambda r: (prop(r['properties'], key, default=0) or 0), reverse=desc)

def sort_pubs(rows):
    """Newest first: Year desc → Order asc (blank Order = top of its year) → most recently created first.
    So a new paper only needs a Year; leave Order empty and it lands at the top of the site (and of the Notion view)."""
    def key(r):
        p = r['properties']
        year = prop(p, 'Year', default=0) or 0
        order = prop(p, 'Order', default=None)
        created = r.get('created_time', '')            # ISO string: later = lexicographically greater
        return (-year, order if order is not None else float('-inf'), tuple(-ord(c) for c in created))
    return sorted(rows, key=key)

def visible(rows):
    return [r for r in rows if prop(r['properties'], 'Show on Site', default=True) is not False]

# ----------------------------------------------------------------------------- images
SNAP = json.loads((HERE / 'snapshot' / 'manifest.json').read_text(encoding='utf-8'))
SNAP_LAYERS = (SNAP, SNAP.get('archive', {}))
SNAP_FILES = {}
SNAP_IDENTITIES = {}
for layer in SNAP_LAYERS:
    for key, path in layer.get('files', {}).items():
        SNAP_FILES.setdefault(key, path)
    for key, identity in layer.get('identities', {}).items():
        SNAP_IDENTITIES.setdefault(key, identity)
DYNAMIC_IMAGES = {'person', 'photo', 'fig', 'slide', 'pubthumb'}
SNAP_LABEL_QUEUE = {}
SNAP_MATCHES = {}
SNAP_USED = set()
IMAGE_METADATA = {'identities': {}, 'labels': {}, 'aliases': {}}
def _lab(s):
    """Caption/name → comparison key: markdown links stripped, all whitespace (incl. nbsp/newlines) collapsed, lower-case."""
    s = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', str(s or ''))
    return re.sub(r'\s+', ' ', s.replace('\xa0', ' ')).strip().lower()
for layer in SNAP_LAYERS:
    # All active aliases and labels precede archived matches for the same label.
    for category, aliases in layer.get('aliases', {}).items():
        for label, keys in aliases.items():
            queue = SNAP_LABEL_QUEUE.setdefault((category, _lab(label)), [])
            queue.extend(key for key in keys if key not in queue)
    for key, label in layer.get('labels', {}).items():
        queue = SNAP_LABEL_QUEUE.setdefault((key.split(':')[0], _lab(label)), [])
        if key not in queue:
            queue.append(key)

def snapshot_file(key=None, kind=None, label=None, source_id=None):
    """Match a row's identity or semantic label; never reuse its old position."""
    category = key.split(':')[0] if key else kind
    if category not in DYNAMIC_IMAGES:
        candidate = key if key in SNAP.get('files', {}) else SNAP.get('archive', {}).get('stable_keys', {}).get(key)
        return HERE / 'snapshot' / SNAP_FILES[candidate] if candidate in SNAP_FILES else None
    row = (category, source_id or key)
    if row in SNAP_MATCHES:
        return SNAP_MATCHES[row]
    identities = SNAP_IDENTITIES
    def eligible(candidate):
        # A publication may reuse a figure. Its identity belongs to the figure,
        # so only identities in the same row category can conflict.
        same_category = candidate.split(':')[0] == category
        shared_figure = category == 'pubthumb' and candidate.startswith('fig:')
        return (candidate in SNAP_FILES
                and (shared_figure or (category, candidate) not in SNAP_USED)
                and not (source_id and same_category and identities.get(candidate)
                         and identities[candidate] != source_id))
    matches = [k for k, identity in identities.items()
               if source_id and identity == source_id and k.split(':')[0] == category and eligible(k)]
    lab = _lab(label)
    if not matches and lab:
        matches = [k for k in SNAP_LABEL_QUEUE.get((category, lab), []) if eligible(k)]
    if not matches and category == 'photo' and len(lab) >= 12:
        # Preserve the legacy caption-prefix fallback only when unambiguous.
        queues = [[k for k in keys if eligible(k)]
                  for (cat, old_label), keys in SNAP_LABEL_QUEUE.items()
                  if cat == category and len(old_label) >= 12
                  and (lab.startswith(old_label) or old_label.startswith(lab))]
        queues = [q for q in queues if q]
        if len(queues) == 1:
            matches = queues[0]
    chosen = matches[0] if matches else None
    result = HERE / 'snapshot' / SNAP_FILES[chosen] if chosen else None
    SNAP_MATCHES[row] = result
    if chosen:
        SNAP_USED.add((category, chosen))
    return result

def fetch_bytes(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (mlv-site-builder)'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()

def record_image(key, label='', source_id=None, category=None):
    """Keep row identity and alternate publication titles for the next backup."""
    own_category = key.split(':')[0]
    category = category or own_category
    if category == own_category:
        IMAGE_METADATA['labels'][key] = label
        if source_id:
            IMAGE_METADATA['identities'][key] = source_id
    if category in DYNAMIC_IMAGES and _lab(label):
        aliases = IMAGE_METADATA['aliases'].setdefault(category, {}).setdefault(_lab(label), [])
        if key not in aliases:
            aliases.append(key)

def youtube_feed(channel_id):
    """Latest uploads (max 15) of a YouTube channel via its public Atom feed → [{id, title, published}] newest first."""
    import xml.etree.ElementTree as ET
    ns = {'a': 'http://www.w3.org/2005/Atom', 'yt': 'http://www.youtube.com/xml/schemas/2015'}
    root = ET.fromstring(fetch_bytes(f'https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}'))
    out = []
    for e in root.findall('a:entry', ns):
        vid = e.find('yt:videoId', ns); title = e.find('a:title', ns); pub = e.find('a:published', ns)
        if vid is not None and vid.text: out.append({'id': vid.text.strip(), 'title': (title.text or '').strip() if title is not None else '', 'published': (pub.text or '')[:10] if pub is not None else ''})
    return out

def save_image(key, kind, sources, label='', no_images=False, source_id=None):
    """Try each source (Notion file URL, external URL, snapshot path) → site/img/<hash>.webp. Returns relative path or ''."""
    IMG.mkdir(parents=True, exist_ok=True)
    width = CFG['image_widths'].get(kind, 900)
    name = hashlib.sha1(key.encode()).hexdigest()[:12]
    # Google Sites image URLs (lh3.googleusercontent.com/sitesv/...) are re-signed on every page view and
    # always answer 403 outside the site, so they are skipped silently; the bundled snapshot copy is used instead.
    sources = [s for s in sources if s]
    cands = [s for s in sources if 'googleusercontent.com/sitesv/' not in s]
    snap = snapshot_file(key, kind, label, source_id=source_id)
    if snap: cands.append(str(snap))
    errors = []
    for src in cands:
        try:
            if src.startswith('http'):
                if no_images: continue
                data = fetch_bytes(src)
            else:
                data = Path(src).read_bytes()
            ext = 'png' if data[:4] == b'\x89PNG' and kind == 'social' else 'webp'
            out = IMG / f'{name}.{ext}'
            if Image is not None:
                im = Image.open(io.BytesIO(data)); im.load()
                if not src.startswith('http') and (im.format or '').lower() == ext and im.width <= width:
                    # Repeated backup refreshes must not recompress existing WebP images.
                    out.write_bytes(data)
                else:
                    if im.mode not in ('RGB', 'RGBA'): im = im.convert('RGBA' if 'A' in im.mode else 'RGB')
                    if im.width > width: im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
                    if ext == 'webp' and im.mode == 'RGBA':
                        bg = Image.new('RGB', im.size, (255, 255, 255)); bg.paste(im, mask=im.split()[-1]); im = bg
                    im.save(out, quality=82)
            else:
                out.write_bytes(data)
            record_image(key, label, source_id)
            return f'img/{out.name}'
        except Exception as e:  # try the next candidate
            errors.append(f'{str(e)[:60]} ({src[:50]})')
    if not no_images and (sources or snap):
        detail = ' | '.join(errors) or 'source URL is no longer usable and no matching backup exists'
        raise RuntimeError(f'Image unavailable for {key} ({label or kind}): {detail}')
    if errors:
        print(f'  ! no image for {key}: ' + ' | '.join(errors), file=sys.stderr)
    return ''

# ----------------------------------------------------------------------------- main mapping
def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--no-images', action='store_true'); args = ap.parse_args()
    if not TOKEN:
        sys.exit('NOTION_TOKEN is not set. Create an internal integration at notion.so/profile/integrations and share the "MLV Lab homepage DB" page with it.')
    ds = CFG['data_sources']; no_img = args.no_images
    A = {}   # asset key → relative path (the template's image map)
    SNAP_MATCHES.clear(); SNAP_USED.clear()
    for values in IMAGE_METADATA.values():
        values.clear()

    # ---- People
    people, id_to_person = [], {}
    rows = sort_rows(visible(query_all(ds['people'])))
    for i, r in enumerate(rows, 1):
        p = r['properties']; name = prop(p, 'Name')
        key = f'person:{i}'
        photo = save_image(key, 'person', prop(p, 'Photo File', default=[]) + [prop(p, 'Photo', 'Photo URL')], label=name, no_images=no_img, source_id=r['id'])
        if photo: A[key] = photo
        bio = affil = ''; awards = []
        if prop(p, 'Group') == 'Faculty':
            md = body_markdown(r['id'])
            parts = re.split(r'\n## ', '\n' + md)
            for part in parts:
                if part.lower().startswith('about me'):
                    lines = [l for l in part.split('\n')[1:] if l.strip()]
                    # first lines up to the first long paragraph are affiliations
                    aff, rest = [], []
                    for l in lines:
                        (rest if (rest or len(l) > 120) else aff).append(l)
                    affil = '\n'.join(aff); bio = '\n\n'.join(rest)
                elif part.lower().startswith('awards'):
                    awards = [l[2:].strip() for l in part.split('\n')[1:] if l.startswith('- ')]
        person = {
            'id': i, 'name': name, 'ko': prop(p, 'Korean Name'), 'group': prop(p, 'Group'), 'status': prop(p, 'Status'),
            'position': prop(p, 'Position'), 'affiliation': '', 'email': prop(p, 'Email'), 'tel': prop(p, 'Tel'),
            'scholar': prop(p, 'Google Scholar'), 'homepage': prop(p, 'Homepage'), 'cv': prop(p, 'CV'),
            'interests': prop(p, 'Research Interests', default=[]), 'bio': bio, 'affil_detail': affil, 'awards': awards,
            'graduated': prop(p, 'Graduated'), 'after': prop(p, 'After Graduation'), 'photo': key if photo else '',
        }
        people.append(person); id_to_person[r['id']] = i

    # ---- Research figures (needed for publication thumbnails)
    fig_rows = sort_rows(visible(query_all(ds['figures'])))
    fig_by_id, fig_url_to_key = {}, {}
    topic_rows = sort_rows(visible(query_all(ds['topics'])))
    topic_index = {r['id']: n for n, r in enumerate(topic_rows, 1)}
    per_topic_count = {}
    for r in fig_rows:
        p = r['properties']; trel = prop(p, 'Topic', default=[]); t = topic_index.get(trel[0]) if trel else 0
        n = per_topic_count.get(t, 0); per_topic_count[t] = n + 1
        key = f'fig:{t}:{n}'; cap = prop(p, 'Caption')
        files = prop(p, 'Image File', default=[]); url = prop(p, 'Image URL', 'Image')
        path = save_image(key, 'fig', files + [url], label=cap, no_images=no_img, source_id=r['id'])
        if path: A[key] = path
        fig_by_id[r['id']] = {'key': key, 'caption': cap, 'topic': t, 'pub': (prop(p, 'Publication', default=[]) or [None])[0]}
        if url: fig_url_to_key[url] = key

    # ---- Publications
    pubs, pub_index = [], {}
    rows = sort_pubs(visible(query_all(ds['publications'])))
    for i, r in enumerate(rows, 1):
        p = r['properties']; pub_index[r['id']] = i
        links = {}
        for label, names in [('Code', ['Code']), ('Video', ['Video']), ('Slides', ['Slides']), ('Poster', ['Poster']), ('Project page', ['Project Page']), ('Demo', ['Demo']), ('Supp', ['Supplement', 'Supp'])]:
            v = prop(p, *names)
            if v: links[label] = v
        pres = prop(p, 'Presentation'); pl = pres.lower(); badge = ''
        if 'gold star' in pl: badge = 'Gold Star'
        elif 'spotlight' in pl: badge = 'Spotlight'
        elif 'oral' in pl: badge = 'Oral'
        elif 'highlight' in pl: badge = 'Highlight'
        # Resolve each thumbnail once, after all figure relations are known.
        tfiles = prop(p, 'Thumbnail File', default=[]); turl = prop(p, 'Thumbnail', 'Thumbnail URL')
        thumb = fig_url_to_key.get(turl, '')
        if thumb not in A: thumb = ''
        pubs.append({
            'id': i, 'pid': prop(p, 'Paper ID'), 'type': prop(p, 'Type'), 'year': int(prop(p, 'Year', default=0) or 0),
            'title': prop(p, 'Title'), 'url': prop(p, 'Paper Link', 'Paper'), 'authors': prop(p, 'Authors'), 'venue': prop(p, 'Venue'),
            'venue_short': prop(p, 'Venue (short)'), 'presentation': pres, 'badge': badge, 'collab': prop(p, 'Collaboration'),
            'note': prop(p, 'Note'), 'highlight': bool(prop(p, 'Highlight', default=False)), 'links': links,
            'members': [id_to_person[m] for m in prop(p, 'MLV Members', default=[]) if m in id_to_person], 'thumb': thumb,
            '_topics': prop(p, 'Research Topics', default=[]), '_turl': turl,
            '_tfiles': tfiles, '_source_id': r['id'],
        })
    # thumbnails from figure→publication relation (when a figure points at a paper that has no thumbnail yet)
    for f in fig_by_id.values():
        if f['pub'] in pub_index and f['key'] in A:
            pb = pubs[pub_index[f['pub']] - 1]
            if not pb['thumb']: pb['thumb'] = f['key']
    # Uploaded file → usable related figure → URL → title/identity-matched backup.
    for pb in pubs:
        turl = pb.pop('_turl'); tfiles = pb.pop('_tfiles'); source_id = pb.pop('_source_id')
        if pb['thumb'] and not tfiles:
            record_image(pb['thumb'], pb['title'], category='pubthumb')
            continue
        related = [str(OUT / A[pb['thumb']])] if pb['thumb'] else []
        key = f"pubthumb:{pb['id']}"
        path = save_image(key, 'fig', tfiles + related + [turl], label=pb['title'],
                          no_images=no_img, source_id=source_id)
        if path: A[key] = path; pb['thumb'] = key

    # ---- Topics
    topics = []
    for n, r in enumerate(topic_rows, 1):
        p = r['properties']
        figs = [{'img': f['key'], 'caption': f['caption']} for f in fig_by_id.values() if f['topic'] == n and f['key'] in A]
        rel = []
        for pid in prop(p, 'Related Publications', default=[]):
            if pid in pub_index:
                pb = pubs[pub_index[pid] - 1]
                rel.append({'venue': f"{pb['venue_short']} '{str(pb['year'])[2:]}", 'title': pb['title'], 'url': pb['url'], 'note': pb['presentation'], 'pub': pb['id']})
                pb.setdefault('topics', []).append(n)
        rel.sort(key=lambda x: -pubs[x['pub'] - 1]['year'])
        topics.append({'id': n, 'name': prop(p, 'Topic'), 'desc': prop(p, 'Description'), 'figures': figs, 'related': rel})
    for pb in pubs:
        pb['topics'] = sorted(set(pb.get('topics', []) + [topic_index[t] for t in pb.pop('_topics') if t in topic_index]))

    # ---- News
    news = []
    for r in sort_rows(visible(query_all(ds['news'])), desc=True):
        p = r['properties']; md = prop(p, 'News title', 'Title', 'News')
        extras = []
        for k in (1, 2, 3):
            u = prop(p, f'Link {k}'); lab = prop(p, f'Link Label {k}') or 'Link'
            if u: extras.append(f'[{lab}]({u})')
        if extras: md += ' ' + ' '.join(extras)
        news.append({'date': prop(p, 'Date'), 'md': md, 'new': bool(prop(p, 'New', default=False))})
    news.sort(key=lambda n: n['date'], reverse=True)

    # ---- Teaching
    teaching = []
    for r in visible(query_all(ds['teaching'])):
        p = r['properties']
        teaching.append({'semester': prop(p, 'Semester'), 'year': int(prop(p, 'Year', default=0) or 0), 'term': prop(p, 'Term'),
                         'title': prop(p, 'Course'), 'code': prop(p, 'Code'), 'note': prop(p, 'Note'), 'inst': prop(p, 'Institution')})
    teaching.sort(key=lambda t: (-t['year'], t['term'] != 'Fall', t['title']))

    # ---- Photos
    photos = []
    for i, r in enumerate(sort_rows(visible(query_all(ds['photos']))), 0):
        p = r['properties']; cap = prop(p, 'Caption'); key = f'photo:{i}'
        path = save_image(key, 'photo', prop(p, 'Image File', default=[]) + [prop(p, 'Image URL', 'Image')], label=cap, no_images=no_img, source_id=r['id'])
        if path: A[key] = path; photos.append({'img': key, 'caption': cap})

    # ---- Videos
    videos = []
    video_id = lambda p: prop(p, 'YouTube ID') or re.sub(r'.*(?:v=|youtu\.be/)([\w-]{11}).*', r'\1', prop(p, 'YouTube URL'))
    def yt_thumb(vid, source_id=None):
        key = f'yt:{vid}'
        path = save_image(key, 'yt', [f'https://i.ytimg.com/vi/{vid}/hq720.jpg', f'https://i.ytimg.com/vi/{vid}/maxresdefault.jpg', f'https://i.ytimg.com/vi/{vid}/mqdefault.jpg'], no_images=no_img, source_id=source_id)   # 1280px if available, else 320px
        if path: A[key] = path
        return key if path else ''
    all_video_rows = query_all(ds['videos'])
    shown_rows = visible(all_video_rows)
    hidden_video_ids = {video_id(r['properties']) for r in all_video_rows if r not in shown_rows}   # rows with "Show on Site" unchecked also block the auto-sync
    for r in sort_rows(shown_rows):
        p = r['properties']; vid = video_id(p)
        videos.append({'id': vid, 'title': prop(p, 'Title'), 'url': prop(p, 'YouTube URL') or f'https://www.youtube.com/watch?v={vid}', 'thumb': yt_thumb(vid, source_id=r['id'])})

    # ---- Highlights
    highlights = []
    for i, r in enumerate(sort_rows(visible(query_all(ds['highlights']))), 0):
        p = r['properties']; cap = prop(p, 'Caption'); key = f'slide:{i}'
        path = save_image(key, 'slide', prop(p, 'Image File', default=[]) + [prop(p, 'Image URL', 'Image')], label=cap, no_images=no_img, source_id=r['id'])
        if path: A[key] = path; highlights.append({'img': key, 'caption': cap, 'link': prop(p, 'Link')})

    # ---- Site content (key/value + page bodies)
    SC = {}
    for r in visible(query_all(ds['site_content'])):
        p = r['properties']; k = plain(p, 'Key'); v = plain(p, 'Value')   # plain text: Notion auto-links URLs/emails, which would break hrefs/iframes
        if v.startswith('(') or k in ('home_intro', 'contact_address_en', 'contact_address_ko', 'openings_en', 'openings_ko'):
            body = body_markdown(r['id'])
            if body: v = body
        SC[k] = v
    for key, kind in [('hero', 'hero'), ('collab', 'collab')]:
        src = SC.get({'hero': 'home_hero_image_url', 'collab': 'home_collaborators_image_url'}[key], '')
        path = save_image(key, kind, [SC.get(key + '_file', ''), src], no_images=no_img)
        if path: A[key] = path
    for i, k in enumerate(['youtube_icon_url', 'facebook_icon_url', 'x_icon_url']):
        path = save_image(f'social:{i}', 'social', [SC.get(k, '')], no_images=no_img)
        if path: A[f'social:{i}'] = path
    # research_banner / logo / banner_people / banner_photos: optional Site Content rows "<key>_url" override the snapshot copy
    for key in ('research_banner', 'logo', 'banner_people', 'banner_photos'):
        path = save_image(key, key, [SC.get(key + '_url', '')], no_images=no_img)
        if path: A[key] = path
    socials = [{'name': 'YouTube', 'url': SC.get('youtube_url', ''), 'icon': 'social:0'},
               {'name': 'Facebook', 'url': SC.get('facebook_url', ''), 'icon': 'social:1'},
               {'name': 'X', 'url': SC.get('x_url', ''), 'icon': 'social:2'}]
    site = {
        'lab_name': SC.get('lab_name', 'Machine Learning and Vision Lab'), 'lab_short': SC.get('lab_short_name', 'MLV Lab'),
        'site_url': SC.get('site_url', ''), 'pi_email': SC.get('pi_email', ''), 'apply_email': SC.get('apply_email', ''),
        'scholar': SC.get('google_scholar', ''), 'intro': SC.get('home_intro', '').replace('https://mlv.korea.ac.kr/contact/openings', '#/openings'),
        'address_en': SC.get('contact_address_en', ''), 'address_ko': SC.get('contact_address_ko', ''),
        'map_embed': SC.get('contact_map_embed_url', ''), 'calendar_embed': SC.get('contact_calendar_embed_url', ''),
        'map_link': SC.get('contact_map_link', 'https://www.google.com/maps/search/?api=1&query=KRAFTON+SoC+Building+KAIST'),
        'calendar_link': SC.get('contact_calendar_embed_url', ''),
        'openings_title': SC.get('openings_title', 'Openings'), 'openings_open': SC.get('openings_open', 'true').strip().lower() == 'true',
        'openings_en': SC.get('openings_en', ''), 'openings_ko': SC.get('openings_ko', ''),
        'home_news_count': int(SC.get('home_news_count', '10') or 10),
        'home_new_count': int(SC.get('home_new_count', '5') or 5),   # how many newest News items get the NEW badge
    }
    # ---- YouTube auto-sync: newest uploads of the lab channel (RSS, latest 15) that are not in Notion go to the top of MLV TV.
    #      Turn off with a Site Content row youtube_auto_sync = false. Hide one video by adding its URL to the MLV TV DB with "Show on Site" unchecked.
    channel = (SC.get('youtube_channel_id') or CFG.get('youtube_channel_id') or '').strip()
    if channel and SC.get('youtube_auto_sync', 'true').strip().lower() != 'false':
        try:
            known = {v['id'] for v in videos} | hidden_video_ids
            fresh = [f for f in youtube_feed(channel) if f['id'] not in known]
        except Exception as e:
            print(f'  ! youtube feed skipped: {str(e)[:120]}', file=sys.stderr)
        else:
            auto = [{'id': f['id'], 'title': f['title'], 'url': f'https://www.youtube.com/watch?v={f["id"]}', 'thumb': yt_thumb(f['id']), 'date': f['published'], 'auto': True} for f in fresh]
            videos = auto + videos
            print(f'youtube feed: {len(fresh)} new video(s) added automatically')

    data = {'site': site, 'people': people, 'pubs': pubs, 'topics': topics, 'news': news, 'teaching': teaching, 'photos': photos,
            'videos': videos, 'socials': socials, 'highlights': highlights, 'generated': time.strftime('%Y-%m-%d %H:%M')}
    BUILD.mkdir(exist_ok=True)
    for filename, value in [('site_data.json', data), ('assets.json', A), ('image_metadata.json', IMAGE_METADATA)]:
        (BUILD / filename).write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    print(f"people {len(people)} · pubs {len(pubs)} · topics {len(topics)} · news {len(news)} · teaching {len(teaching)} · photos {len(photos)} · videos {len(videos)} · highlights {len(highlights)} · images {len(A)}")

if __name__ == '__main__':
    main()
