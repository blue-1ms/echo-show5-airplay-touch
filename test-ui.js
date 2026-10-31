// Dependency-free UI state regression checks. Run with node test-ui.js.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const html = fs.readFileSync(__dirname + '/index.html', 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements = new Map();
for (const match of html.matchAll(/\bid="([^"]+)"/g)) {
  assert(!elements.has(match[1]), 'Duplicate id: ' + match[1]);
  elements.set(match[1], {hidden: false, style: {}, textContent: '', value: '',
    setAttribute(name, value) {this[name] = value;}});
}
const context = vm.createContext({
  document: {hidden: false, getElementById: id => {
    assert(elements.has(id), 'Unknown element: ' + id); return elements.get(id);
  }, addEventListener() {}}, window: {}, fetch: () => new Promise(() => {}),
  setInterval() {}, setTimeout() {}, clearTimeout() {}, location: {reload() {}},
});
vm.runInContext(script, context);
const single = {name:'Living Room', active:true, state:'Playing', title:'A song',
  artist:'Artist', album:'Album', duration:120, position:30, volume:40, art:'',
  can_toggle:true, can_next:true, can_previous:true, paired:false, linked:false};
function render(state) {context.snapshot=state;vm.runInContext('render(snapshot)',context);}
render(single);
assert.equal(elements.get('pairHelp').hidden,true,'Single receiver must hide pair guidance');
assert.equal(elements.get('toggle').disabled,false,'Single receiver keeps playback controls');
assert.equal(elements.get('hint').textContent,'Volume for this Echo only');
render({...single, paired:true, linked:true, peer_name:'Kitchen', peer_online:true, peer_volume:40});
assert.equal(elements.get('pairHelp').hidden,false);
assert.match(elements.get('hint').textContent,/Kitchen 40%/);
render({...single, paired:true, linked:true, peer_online:false});
assert.match(elements.get('hint').textContent,/Peer offline/);
render({...single, active:false, can_toggle:false, can_next:false, can_previous:false});
assert.equal(elements.get('volume').disabled,true);
assert.equal(elements.get('toggle').disabled,true);
assert.equal(elements.get('pairHelp').hidden,true);
assert(!/left channel|right channel/i.test(script));
console.log('PASS: unique IDs, single receiver, paired volume, missing peer, idle controls, no fixed L/R labels');
