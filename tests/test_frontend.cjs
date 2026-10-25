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
