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
