const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const template = fs.readFileSync(path.join(root, 'template.html'), 'utf8');
const script = template.match(/<script>\s*([\s\S]*?)<\/script>/)[1];
// Load the real renderers without starting browser routing.
const definitions = script.slice(0, script.indexOf("\ndocument.getElementById('tabs')"));
const snapshot = JSON.parse(fs.readFileSync(path.join(root, 'snapshot/site_data.json'), 'utf8'));

function setup({site = {}, highlights = []} = {}) {
  const data = structuredClone(snapshot);
  data.highlights = highlights;
  data.news = [
    {date: '2026-10-13', md: 'First'},
    {date: '2026-10-12', md: 'Second'},
    {date: '2026-10-11', md: 'Third'},
  ];
  Object.assign(data.site, {home_news_count: 1}, site);
  const nodes = {
    assets: {textContent: '{}'}, data: {textContent: JSON.stringify(data)},
    morenews: {}, newslist: {innerHTML: ''}, cidx: {}, ccap: {}, cprev: {}, cnext: {},
  };
  // Only the DOM boundary is replaced; the production renderers and handlers run unchanged.
  const images = highlights.map(() => ({classList: {toggle() {}}}));
  const timers = [];
  const context = vm.createContext({
    document: {getElementById: id => nodes[id], querySelectorAll: () => images},
    window: {}, setInterval: callback => {timers.push(callback); return timers.length;}, clearInterval() {},
  });
  vm.runInContext(definitions, context);
  return {context, nodes, timers};
}

function routeSetup({reduced = false, animation = true, highlights = []} = {}) {
  const state = setup({highlights});
  const {context, nodes} = state;
  const element = () => {
    const classes = new Set();
    return {
      attributes: {}, style: {}, focuses: [],
      classList: {
        add: (...names) => names.forEach(name => classes.add(name)),
        remove: (...names) => names.forEach(name => classes.delete(name)),
        contains: name => classes.has(name),
        toggle(name, force = !classes.has(name)) { force ? classes.add(name) : classes.delete(name); },
      },
      setAttribute(name, value) { this.attributes[name] = value; },
      removeAttribute(name) { delete this.attributes[name]; },
      focus(options) { this.focuses.push(options); },
      getBoundingClientRect: () => ({top: 0, bottom: 100}),
    };
  };
  const header = element();
  const links = Array.from(vm.runInContext('TABS', context), ([page]) => ({...element(), dataset: {p: page}}));
  const animations = [], observers = [], clearedIntervals = [], scrolls = [];
  const pending = new Map(), scheduled = [];
  const main = element();
  let content = '', revealNodes = [];
  Object.defineProperty(main, 'innerHTML', {
    get: () => content,
    set(value) { content = value; revealNodes = [element()]; },
  });
  if (animation) main.animate = (frames, options) => {
    const entry = {frames, options, cancelled: false, cancel() { this.cancelled = true; }};
    animations.push(entry);
    return entry;
  };
  Object.assign(nodes, {main, tabs: element(), menubtn: element(), plist: element(), pnote: element(), pq: element()});
  const originalQuery = context.document.querySelectorAll;
  const revealSelector = vm.runInContext('REVEAL_SEL', context);
  context.document.querySelector = selector => selector === '.top' ? header
    : selector === '.toolbar' ? nodes.toolbar || null : null;
  context.document.querySelectorAll = selector => selector === 'nav.tabs a' ? links
    : selector === '#carousel .frame img' ? originalQuery(selector)
    : selector === revealSelector ? revealNodes : [];
  context.window.matchMedia = () => ({matches: reduced});
  context.window.scrollY = 0;
  context.window.scrollTo = options => scrolls.push(options);
  context.location = {hash: '#/home'};
  context.URLSearchParams = URLSearchParams;
  context.innerHeight = 800;
  context.requestAnimationFrame = callback => callback();
  context.clearInterval = id => clearedIntervals.push(id);
  context.setTimeout = callback => { const id = scheduled.push(callback); pending.set(id, callback); return id; };
  context.clearTimeout = id => pending.delete(id);
  context.IntersectionObserver = context.window.IntersectionObserver = class {
    constructor() { this.disconnected = false; this.unobserved = []; observers.push(this); }
    observe() {}
    unobserve(node) { this.unobserved.push(node); }
    disconnect() { this.disconnected = true; }
  };
  return {...state, header, links, animations, observers, clearedIntervals, scrolls, pending, scheduled,
    navigate(hash) { context.location.hash = hash; vm.runInContext('route()', context); },
    target(id) { const calls = []; nodes[id] = {...element(), scrollIntoView: options => calls.push(options)}; return calls; },
  };
}

test('rapid navigation replaces content immediately and cancels the prior entry animation', () => {
  const app = routeSetup();
  app.navigate('#/home');
  assert.equal(app.animations.length, 0);
  assert.equal(app.nodes.main.focuses.length, 0);
  app.nodes.tabs.classList.add('open');
  app.navigate('#/people');
  assert.match(app.nodes.main.innerHTML, /<h1>People<\/h1>/);
  assert.equal(app.animations.length, 1);
  app.navigate('#/teaching');
  assert.match(app.nodes.main.innerHTML, /<h1>Teaching<\/h1>/);
  assert.equal(app.animations[0].cancelled, true);
  assert.equal(app.animations[1].cancelled, false);
  assert.equal(app.nodes.main.focuses.at(-1).preventScroll, true);
  assert.equal(app.nodes.tabs.classList.contains('open'), false);
  assert.equal(app.nodes.menubtn.attributes['aria-expanded'], 'false');
  assert.equal(app.links.find(a => a.dataset.p === 'teaching').attributes['aria-current'], 'page');
  assert.equal(app.links.find(a => a.dataset.p === 'people').attributes['aria-current'], undefined);
});

test('leaving a page clears its carousel timer and detaches its reveal observer', () => {
  const app = routeSetup({highlights: [{img: 'slide:0', caption: 'First'}, {img: 'slide:1', caption: 'Second'}]});
  app.navigate('#/home');
  assert.equal(app.timers.length, 1);
  const observer = app.observers[0];
  app.navigate('#/people');
  assert.deepEqual(app.clearedIntervals, [1]);
  assert.equal(observer.disconnected, true);
  assert.equal(app.context.window.__ctimer, null);
});

test('a superseded deep-link callback cannot scroll away from the newest route', () => {
  const app = routeSetup();
  const previous = app.target('old-target'), current = app.target('new-target');
  app.navigate('#/people?t=old-target');
  const staleCallback = app.scheduled[0];
  app.navigate('#/teaching?t=new-target');
  assert.equal(app.pending.size, 1);
  staleCallback();
  for (const callback of app.pending.values()) callback();
  assert.equal(previous.length, 0);
  assert.equal(current.length, 1);
  assert.equal(current[0].block, 'start');
});

test('deep-linked papers clear the header and toolbar without competing entry motion', () => {
  const app = routeSetup();
  app.navigate('#/home');
  const calls = app.target('pub19');
  const target = app.nodes.pub19;
  target.classList.add('rv', 'in');
  app.nodes.toolbar = {getBoundingClientRect: () => ({height: 120})};
  app.navigate('#/publications?t=pub19');
  for (const callback of app.pending.values()) callback();
  assert.equal(target.style.scrollMarginTop, '212px');
  assert.equal(target.classList.contains('rv'), false);
  assert.equal(target.classList.contains('in'), false);
  assert.equal(app.observers.at(-1).unobserved.includes(target), true);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].block, 'start');
  assert.equal(app.animations.length, 0);
});

test('reduced-motion navigation skips animation and smooth target scrolling', () => {
  const app = routeSetup({reduced: true});
  const target = app.target('selected-paper');
  app.navigate('#/home');
  app.navigate('#/people?t=selected-paper');
  for (const callback of app.pending.values()) callback();
  assert.match(app.nodes.main.innerHTML, /<h1>People<\/h1>/);
  assert.equal(app.animations.length, 0);
  assert.equal(app.observers.length, 0);
  assert.equal(target[0].behavior, 'instant');
  assert.equal(app.nodes['selected-paper'].style.scrollMarginTop, '92px');
  assert.equal(app.nodes.main.focuses.at(-1).preventScroll, true);
});

test('unsupported animations and unknown routes still render synchronously', () => {
  const app = routeSetup({animation: false});
  app.navigate('#/people');
  app.navigate('#/unknown');
  assert.match(app.nodes.main.innerHTML, /<h2>About<\/h2>/);
  assert.equal(app.animations.length, 0);
  assert.equal(app.links.find(a => a.dataset.p === 'home').attributes['aria-current'], 'page');
});

test('choosing the current mobile page restores focus after closing its menu', () => {
  const app = routeSetup();
  app.navigate('#/home');
  app.nodes.tabs.classList.add('open');
  app.context.navEvent = {target: {closest: () => ({hash: '#/home'})}};
  vm.runInContext('onNavClick(navEvent)', app.context);
  assert.equal(app.nodes.tabs.classList.contains('open'), false);
  assert.equal(app.nodes.menubtn.focuses.length, 1);
  vm.runInContext('onNavClick(navEvent)', app.context);
  assert.equal(app.nodes.menubtn.focuses.length, 1, 'desktop clicks must not focus the hidden menu button');
});

test('empty Highlights still renders News without a carousel', () => {
  const {context} = setup();
  const output = vm.runInContext('homePage()', context);
  assert.match(output, />News</);
  assert.doesNotMatch(output, /id="carousel"/);
});

test('Show all displays every news item even without Highlights', () => {
  const {context, nodes, timers} = setup();
  vm.runInContext('homeAfter()', context);
  assert.equal(timers.length, 0);
  assert.equal(typeof nodes.morenews.onclick, 'function');
  let removed = false;
  nodes.morenews.onclick({target: {remove: () => {removed = true;}}});
  assert.match(nodes.newslist.innerHTML, /Third/);
  assert.equal(removed, true);
});

test('a populated carousel still advances and wraps its caption', () => {
  const {context, nodes, timers} = setup({highlights: [
    {img: 'slide:0', caption: 'First slide'}, {img: 'slide:1', caption: 'Second slide'},
  ]});
  assert.match(vm.runInContext('homePage()', context), /First slide/);
  vm.runInContext('homeAfter()', context);
  assert.equal(timers.length, 1);
  nodes.cnext.onclick();
  assert.equal(nodes.ccap.textContent, 'Second slide');
  assert.equal(nodes.cidx.textContent, '2 / 2');
  nodes.cnext.onclick();
  assert.equal(nodes.ccap.textContent, 'First slide');
});

test('zero NEW count hides all badges', () => {
  const {context} = setup({site: {home_new_count: 0}});
  assert.doesNotMatch(vm.runInContext('D.news.map(newsRow).join("")', context), />NEW</);
});

test('positive NEW count limits badges to the newest items', () => {
  const {context} = setup({site: {home_new_count: 2}});
  const output = vm.runInContext('D.news.map(newsRow).join("")', context);
  assert.equal((output.match(/>NEW</g) || []).length, 2);
  assert.doesNotMatch(output, /Third<span/);
});

test('News segments render native color, bold, links, line breaks and appended links', () => {
  const {context} = setup({site: {home_new_count: 0}});
  context.news = {date: '2026-10-29', md: 'Legacy search text', segments: [
    {text: 'Seven', bold: true, color: 'red', href: 'https://example.org/news'},
    {text: ' papers accepted.\n', bold: false, color: 'default', href: ''},
    {text: 'Paper', bold: false, color: 'blue_background', href: '/paper'},
    {text: ' Contact', bold: false, color: 'default', href: 'mailto:lab@example.org'},
    {text: ' Details', bold: false, color: 'default', href: '#/news'},
  ]};
  const output = vm.runInContext('newsRow(news, 0)', context);
  assert.match(output, /<span class="notion-color-red"><strong>Seven<\/strong><\/span>/);
  assert.match(output, /href="https:\/\/example.org\/news"/);
  assert.match(output, /papers accepted\.<br>/);
  assert.match(output, /notion-color-blue_background/);
  assert.match(output, /href="\/paper"/);
  assert.match(output, /href="mailto:lab@example.org"/);
  assert.match(output, /href="#\/news"/);
  assert.doesNotMatch(output, /Legacy search text|>NEW</);
});

test('NeurIPS announcement emphasizes only Seven without mutating source styles or links', () => {
  const {context} = setup();
  const sentence = 'Seven papers (5 main, 1 eval&dataset track, 1 workshop) got accepted at NeurIPS 2026. Congrats to all the coauthors!';
  context.news = {date: '2026-09-26', md: sentence, segments: [
    {text: 'Seven papers', bold: false, color: 'red', href: '/announcement'},
    {text: sentence.slice(12), bold: false, color: 'default', href: ''},
  ]};
  const before = JSON.stringify(context.news);
  const output = vm.runInContext('newsText(news)', context);
  assert.match(output, /<a href="\/announcement"><span class="notion-color-blue"><strong>Seven<\/strong><\/span><\/a>/);
  assert.match(output, /<a href="\/announcement"><span class="notion-color-red"> papers<\/span><\/a>/);
  assert.equal(output.replace(/<[^>]*>/g, '').replace(/&amp;/g, '&'), sentence);
  assert.equal(JSON.stringify(context.news), before);
  context.news.date = '2025-09-26';
  assert.doesNotMatch(vm.runInContext('newsText(news)', context), /<strong>|notion-color-blue/);
  context.news.date = '2026-09-26';
  context.news.segments[1].text = ' accepted elsewhere.';
  assert.doesNotMatch(vm.runInContext('newsText(news)', context), /<strong>|notion-color-blue/);
  context.news = {date: '2026-09-26', md: sentence};
  assert.match(vm.runInContext('newsText(news)', context), /^<span class="notion-color-blue"><strong>Seven<\/strong><\/span> papers/);
});

test('News preserves existing Markdown rendering for old snapshots and empty segments', () => {
  const {context} = setup({site: {home_new_count: 0}});
  for (const segments of [undefined, [], null]) {
    context.news = {date: '2026-10-29', md: '**Seven** papers [accepted](/news)\nNext line', segments};
    assert.equal(vm.runInContext('newsRow(news, 0)', context),
      '<li><time>2026-10-29</time><p><strong>Seven</strong> papers <a href="/news" target="_blank" rel="noopener">accepted</a><br>Next line</p></li>');
  }
});

test('News allows only safe structured hrefs and escapes their attribute contents', () => {
  const {context} = setup({site: {home_new_count: 0}});
  const safe = ['https://example.org/a?x=1&y=2', 'HTTP://example.org', 'mailto:lab@example.org',
    '/news', './news', '../news', 'news/paper', '#/news', '?year=2026',
    'https://example.org/\" onmouseover=\"evil()'];
  const unsafe = ['javascript:alert(1)', 'JaVaScRiPt:alert(1)', 'data:text/html,<script>evil()</script>',
    'vbscript:evil()', 'file:///etc/passwd', '//evil.example/path', '\\\\evil.example', '/\\evil.example',
    'java\nscript:alert(1)', '\u0000javascript:evil()', 'https://example.org/\u0001',
    {href: 'https://example.org'}];
  for (const href of safe) {
    context.news = {date: '', md: '', segments: [{text: 'Link', bold: false, color: 'default', href}]};
    const output = vm.runInContext('newsRow(news, 0)', context);
    assert.match(output, /<a href="/, String(href));
    assert.doesNotMatch(output, /" onmouseover="/);
    if (href.includes('&')) assert.match(output, /x=1&amp;y=2/);
  }
  for (const href of unsafe) {
    context.news = {date: '', md: '', segments: [{text: 'Link', bold: false, color: 'default', href}]};
    const output = vm.runInContext('newsRow(news, 0)', context);
    assert.match(output, />Link</, String(href));
    assert.doesNotMatch(output, /<a\b/, String(href));
  }
});

test('News escapes markup and ignores injected or malformed color and bold values', () => {
  const {context} = setup({site: {home_new_count: 0}});
  context.news = {date: '2026-10-29', md: '', segments: [
    {text: '<img src=x onerror="evil()"> & text', bold: true,
      color: 'red\" style=\"color:transparent', href: 'javascript:evil()'},
    {text: 'plain', bold: 'false', color: {value: 'red'}, href: ''},
  ]};
  const output = vm.runInContext('newsRow(news, 0)', context);
  assert.match(output, /<strong>&lt;img src=x onerror=&quot;evil\(\)&quot;&gt; &amp; text<\/strong>/);
  assert.doesNotMatch(output, /<img|style=|<a\b|<strong>plain|notion-color-\[object/);
});

test('News renders every supported Notion text and background color through a fixed class', () => {
  const {context} = setup({site: {home_new_count: 0}});
  const names = ['gray', 'brown', 'orange', 'yellow', 'green', 'blue', 'purple', 'pink', 'red'];
  for (const color of [...names, ...names.map(name => name + '_background')]) {
    context.news = {date: '', md: '', segments: [{text: 'Color', bold: false, color, href: ''}]};
    const output = vm.runInContext('newsRow(news, 0)', context);
    assert.match(output, new RegExp(`<span class="notion-color-${color}">Color</span>`));
    const rule = template.match(new RegExp(`\\.news \\.notion-color-${color}\\{([^}]+)\\}`));
    assert.ok(rule, `Rendered color ${color} needs a stylesheet rule`);
    assert.match(rule[1], color.endsWith('_background') ? /background:/ : /color:/);
  }
});

test('Collaboration colors mixed institution names while preserving source text and separators', () => {
  const {context} = setup();
  const collab = 'Google / MICROSOFT, Amazon & University of Wisconsin–Madison';
  context.paper = {...snapshot.pubs[0], collab};
  const output = vm.runInContext('pubRow(paper)', context);
  const line = output.match(/<div class="note">Collaboration with ([\s\S]*?)<\/div>/)[1];
  assert.match(line, /class="collab-name collab-google"/);
  assert.match(line, /class="collab-name collab-microsoft"/);
  assert.match(line, /class="collab-name collab-amazon">Amazon<\/span>/);
  assert.match(line, /class="collab-name collab-wisconsin">University of Wisconsin–Madison<\/span>/);
  assert.equal(line.replace(/<[^>]*>/g, '').replace(/&amp;/g, '&'), collab);
});

test('Google and Microsoft have multiple text colors and an accessible full-word name', () => {
  const {context} = setup();
  for (const [word, groups] of [['Google', ['G', 'o', 'o', 'g', 'l', 'e']],
                               ['MICROSOFT', ['MIC', 'RO', 'SO', 'FT']]]) {
    context.paper = {...snapshot.pubs[0], collab: word};
    const output = vm.runInContext('pubRow(paper)', context);
    const line = output.match(/<div class="note">Collaboration with ([\s\S]*?)<\/div>/)[1];
    assert.ok(line.includes(`aria-label="${word}"`), 'Assistive technology needs the unsplit source name');
    assert.match(line, /role="img"/);
    const coloredParts = [...line.matchAll(/<span class="([^\"]+)">([^<]+)<\/span>/g)];
    assert.deepEqual(coloredParts.map(part => part[2]), groups);
    assert.equal(new Set(coloredParts.map(part => part[1])).size, 4);
    if (word === 'Google') {
      assert.equal(coloredParts[0][1], coloredParts[3][1]);
      assert.equal(coloredParts[1][1], coloredParts[5][1]);
    }
    assert.equal(line.replace(/<[^>]*>/g, ''), word);
  }
});

test('Collaboration colors the institutions and complete phrases from the prior-site examples', () => {
  const {context} = setup();
  const cases = [
    ['Meta', 'meta'], ['UNIST', 'unist'], ['Korea Univ.', 'korea'], ['Korea University', 'korea'],
    ['TwelveLabs', 'twelvelabs'], ['Adobe', 'adobe'], ['Seoul National Univ.', 'seoul'],
    ['Seoul National University', 'seoul'], ['Snapchat', 'snapchat'],
    ['Amazon AGI team', 'amazon'], ['Amazon Inc', 'amazon'],
  ];
  context.paper = {...snapshot.pubs[0], collab: cases.map(([name]) => name).join(' / ')};
  const output = vm.runInContext('pubRow(paper)', context);
  for (const [name, color] of cases) {
    assert.ok(output.includes(`class="collab-name collab-${color}">${name}</span>`), name);
  }
  context.paper = {...snapshot.pubs[0], collab: 'Google Cloud AI'};
  const google = vm.runInContext('pubRow(paper)', context);
  assert.match(google, /class="collab-name collab-charcoal"> Cloud AI<\/span>/);
  const line = google.match(/<div class="note">Collaboration with ([\s\S]*?)<\/div>/)[1];
  assert.equal(line.replace(/<[^>]*>/g, ''), 'Google Cloud AI');
});

test('Collaboration recognizes Wisconsin aliases and avoids unrelated word substrings', () => {
  const {context} = setup();
  const aliases = ['University of Wisconsin-Madison', 'University of Wisconsin–Madison',
    'Univ. of Wisconsin-Madison', 'Univ. of Wisconsin–Madison', 'Wisconsin-Madison',
    'Wisconsin–Madison', 'UW-Madison', 'uw–madison'];
  context.paper = {...snapshot.pubs[0], collab: aliases.join('; ')};
  const output = vm.runInContext('pubRow(paper)', context);
  assert.equal((output.match(/class="collab-name collab-wisconsin"/g) || []).length, aliases.length);
  for (const alias of aliases) assert.ok(output.includes('>' + alias + '</span>'), alias);
  context.paper = {...snapshot.pubs[0], collab: 'Googleplex Microsoft365 Amazonia XUW-Madison UW-Madisonian _Google Google_ éAmazon Amazoné 한국Google Google한국 Metadata UNISTed Korea Universitypress TwelveLabsX AdobeX Snapchatters'};
  assert.doesNotMatch(vm.runInContext('pubRow(paper)', context), /class="collab-name/);
});

test('Institution aliases include new collaborators and optional Univ punctuation', () => {
  const {context} = setup();
  const cases = [['KIST','kist'],['Univ. of Florida','florida'],['University of Florida','florida'],
    ['KT','kt'],['NUIST','nuist'],['Seoul National Univ','seoul'],['Seoul National Univ.','seoul']];
  context.value = cases.map(([name])=>name).join(', ');
  const output = vm.runInContext('collaborationText(value)', context);
  for(const [name,color] of cases) assert.ok(output.includes(`class="collab-name collab-${color}">${name}</span>`),name);
  assert.equal(output.replace(/<[^>]*>/g,''),context.value);
  context.value = 'KISTI KTX NUISTed University of FloridaX Seoul National Universitypress Meta+foo@example.com Google@example.com';
  assert.doesNotMatch(vm.runInContext('collaborationText(value)',context),/collab-name/);
});

test('News colors every current corporate alias while preserving Markdown links and literal markup', () => {
  const {context} = setup();
  context.news = {md:'**Snap Inc.** / Adobe Research / Meta / [Google](https://google.com/a?x=1&y=2) / NEC Lab America / Naver AI Lab / Amazon / KakaoBrain / DeepMind / Facebook. Amazonian <img alt="Google"> https://Google.com'};
  const output = vm.runInContext('newsText(news)',context);
  for(const color of ['snapchat','adobe','meta','google','nec','naver','amazon','kakao','deepmind','facebook']) {
    assert.match(output,new RegExp(`class="collab-name collab-${color}"`));
  }
  assert.match(output, /href="https:\/\/google.com\/a\?x=1&amp;y=2"/);
  assert.match(output, /Amazonian &lt;img alt=&quot;Google&quot;&gt;/);
  assert.doesNotMatch(output, /<img|collab-amazon">Amazonian/);
  assert.match(output, /href="https:\/\/Google.com"[^>]*>Google.com<\/a>/);
});

test('News recognizes a company across Notion segments without losing links or surrounding styles', () => {
  const {context} = setup();
  context.news = {segments:[
    {text:'At ',color:'red',bold:true},
    {text:'Goo',color:'red',href:'https://google.com'},
    {text:'gle',color:'green_background',href:'https://google.com'},
    {text:' & Meta',color:'purple',bold:false},
  ]};
  const before=JSON.stringify(context.news);
  const output=vm.runInContext('newsText(news)',context);
  assert.match(output, /notion-color-red"><strong>At <\/strong>/);
  assert.match(output, /notion-color-green_background/);
  assert.match(output, /collab-google-gold">o<\/span>/);
  assert.match(output, /collab-google-green">l<\/span>/);
  assert.match(output, /collab-name collab-meta">Meta<\/span>/);
  assert.equal((output.match(/href="https:\/\/google.com"/g)||[]).length,2);
  assert.equal(output.replace(/<[^>]*>/g,'').replace(/&amp;/g,'&'),'At Google & Meta');
  assert.equal(JSON.stringify(context.news),before);
  context.news={md:'Goo\ngle'};
  assert.doesNotMatch(vm.runInContext('newsText(news)',context), /collab-name/);
});

test('Collaboration escapes HTML and applies colors only to collaboration text', () => {
  const {context} = setup();
  context.paper = {...snapshot.pubs[0], title: 'Google Microsoft Amazon UW-Madison',
    authors: 'Google, Amazon', venue: 'Microsoft', note: 'UW-Madison',
    collab: '<img alt="Google" src=x onerror="evil()"> Amazon & Other Lab'};
  const output = vm.runInContext('pubRow(paper)', context);
  const line = output.match(/<div class="note">Collaboration with ([\s\S]*?)<\/div>/)[1];
  assert.match(line, /&lt;img alt=&quot;Google&quot; src=x onerror=&quot;evil\(\)&quot;&gt;/);
  assert.match(line, /class="collab-name collab-amazon">Amazon<\/span> &amp; Other Lab/);
  assert.doesNotMatch(output.replace(/<div class="note">Collaboration with [\s\S]*?<\/div>/, ''), /class="collab-name/);
  assert.doesNotMatch(line, /<img|collab-google/);
});

test('Collaboration colors define every group and retain contrast outside the requested vivid accents', () => {
  const {context} = setup();
  context.paper = {...snapshot.pubs[0], collab: 'Google Cloud AI Microsoft Amazon UW-Madison Meta UNIST Korea Univ. TwelveLabs Adobe Seoul National Univ. Snapchat KIST Univ. of Florida KT NUIST NEC Naver KakaoBrain DeepMind Facebook'};
  const output = vm.runInContext('pubRow(paper)', context);
  const line = output.match(/<div class="note">Collaboration with ([\s\S]*?)<\/div>/)[1];
  const names = [...line.matchAll(/<span class="(?:collab-name )?(collab-[a-z-]+)">[^<]+<\/span>/g)].map(match => match[1]);
  assert.ok(names.length >= 20, 'Every single-color name and multicolor group should receive a color');
  // Preserve vivid brand accents; the remaining palette retains the existing contrast floor.
  const vividAccents = new Set(['collab-google-gold', 'collab-microsoft-gold', 'collab-amazon', 'collab-snapchat', 'collab-kist', 'collab-kt', 'collab-naver', 'collab-kakao']);
  for (const name of names) {
    const rule = template.match(new RegExp(`\\.pub \\.${name}\\{color:(#[0-9a-f]{6})\\}`, 'i'));
    assert.ok(rule, `${name} must define a text color`);
    if (vividAccents.has(name)) continue;
    const channels = rule[1].slice(1).match(/../g).map(hex => parseInt(hex, 16) / 255)
      .map(value => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4);
    const luminance = channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
    assert.ok(1.05 / (luminance + 0.05) >= 4.5, `${name} must be readable on white`);
  }
});

test('editable lab and contact values reach the banners as escaped text', () => {
  const {context} = setup({site: {lab_name: 'Example <Lab>', address_en: 'New <Building>\nStreet'}});
  assert.match(vm.runInContext('homePage()', context), /Example &lt;Lab&gt;/);
  assert.match(vm.runInContext('contactPage()', context), /New &lt;Building&gt;/);
});

test('publication citation does not repeat presentation details it already contains', () => {
  const {context} = setup();
  context.paper = {...snapshot.pubs.find(p => p.id === 19),
    venue: 'AAAI, 2026. (Oral presentation, ~top 5%)',
    presentation: 'Oral presentation, ~top 5%', badge: 'Oral'};
  const output = vm.runInContext('pubRow(paper)', context).replace(/<[^>]*>/g, '');
  assert.equal((output.match(/Oral presentation, ~top 5%/g) || []).length, 1);
});

test('publication citation retains presentation details absent from the venue', () => {
  const {context} = setup();
  context.paper = {...snapshot.pubs.find(p => p.id === 19),
    venue: 'AAAI, 2026.', presentation: 'Oral presentation, ~top 5%', badge: 'Oral'};
  const output = vm.runInContext('pubRow(paper)', context).replace(/<[^>]*>/g, '');
  assert.match(output, /AAAI, 2026\./);
  assert.equal((output.match(/Oral presentation, ~top 5%/g) || []).length, 1);
});
