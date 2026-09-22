const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

async function setup(read){
  function node(tag,text){return {tag,textContent:text,children:[],dataset:{},attrs:{},handlers:{},
    append(...nodes){this.children.push(...nodes);},replaceChildren(...nodes){this.children=nodes;},
    setAttribute(k,v){this.attrs[k]=v;},addEventListener(k,v){this.handlers[k]=v;},
    querySelectorAll(){return this.children.filter(n=>n.tag==='button');}};}
  const elements=new Map();const $=id=>{if(!elements.has(id))elements.set(id,node('div'));return elements.get(id);};
  $('category').value='ai';$('category').selectedOptions=[{textContent:'AI'}];
  const topics=[{title:'First article',url:'https://example.com/one',source:'Example'},
    {title:'Second article',url:'https://example.com/two',source:'Example'}];
  const context=vm.createContext({$,node,notice(){},AbortController,setTimeout,clearTimeout,
    api:async(path,options)=>path.startsWith('/api/trends')?{topics}:read(options)});
  const source=fs.readFileSync('tech_shorts/static/studio.js','utf8');
  vm.runInContext(source.slice(source.indexOf('let sourceRequest ='),source.indexOf('let voiceRequest=')),context);
  await vm.runInContext('loadTrends()',context);
  return {$,cards:$('trends').querySelectorAll(),statuses:$('trends').children.filter(n=>n.attrs.role==='status')};
}
test('selection immediately shows loading; failure keeps title and original link without stale notes',async()=>{
  let fail;const ui=await setup(()=>new Promise((_,reject)=>fail=reject));
  ui.$('notes').value='Old article';ui.$('script').value='Old script';
  const pending=ui.cards[0].handlers.click();
  assert.equal(ui.$('topic').value,'First article');assert.equal(ui.$('notes').value,'');
  assert.equal(ui.$('script').value,'');assert.equal(ui.cards[0].attrs['aria-busy'],'true');
  assert.equal(ui.statuses[0].hidden,false);
  fail(Error('본문 없음'));await pending;
  assert.match(ui.statuses[0].children[0].textContent,/본문 없음/);
  assert.equal(ui.statuses[0].children[1].href,'https://example.com/one');
  assert.equal(ui.cards[0].disabled,false);assert.equal(ui.$('create-button').disabled,false);
});
test('switching articles cancels old request and ignores a late response',async()=>{
  const calls=[];const ui=await setup(options=>new Promise(resolve=>calls.push({options,resolve})));
  const first=ui.cards[0].handlers.click();const second=ui.cards[1].handlers.click();
  assert.equal(calls[0].options.signal.aborted,true);
  calls[1].resolve({notes:'Second body'});await second;
  calls[0].resolve({notes:'First body'});await first;
  assert.equal(ui.$('topic').value,'Second article');assert.match(ui.$('notes').value,/Second body/);
  assert.doesNotMatch(ui.$('notes').value,/First body/);
});
test('failed additional article preserves successfully collected combined sources',async()=>{
  let count=0;const ui=await setup(async()=>{if(count++)throw Error('본문 없음');return {notes:'First body'};});
  ui.$('combine-sources').checked=true;
  await ui.cards[0].handlers.click();await ui.cards[1].handlers.click();
  assert.equal(ui.$('topic').value,'First article');assert.match(ui.$('notes').value,/First body/);
  assert.match(ui.statuses[1].children[0].textContent,/기존 자료는 유지/);
});
