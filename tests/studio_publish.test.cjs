const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

function setup(api=async()=>({})){
  const elements=new Map();
  function $(id){
    if(!elements.has(id))elements.set(id,{value:'',dataset:{},hidden:true,handlers:{},
      addEventListener(type,fn){this.handlers[type]=fn;},focus(){this.focused=true;},scrollIntoView(){},
      replaceChildren(){this.value='';},append(){},getAttribute(){return '';},add(){},showModal(){this.open=true;},close(){this.open=false;}});
    return elements.get(id);
  }
  const platforms=['youtube','instagram','tiktok'].map(value=>({value,checked:false}));
  const context=vm.createContext({$,api,notice(){},refresh:async()=>{},Option:function(){},
    config:{connections:{youtube:true,tiktok:true}},
    document:{querySelectorAll(selector){return selector.includes(':checked')?platforms.filter(p=>p.checked):platforms;}}});
  const source=fs.readFileSync('tech_shorts/static/studio.js','utf8');
  vm.runInContext(source.slice(source.indexOf('let creatorRequest='),source.indexOf('$("create-form").addEventListener')),context);
  vm.runInContext('openPublish({id:"job",title:"Title",inputs:{},artifacts:{},status:"approved"})',context);
  return {$,platforms,submit:()=>$('publish-form').handlers.submit({preventDefault(){}})};
}

test('no platform shows a visible error inside the open dialog without sending',async()=>{
  let requests=0;const ui=setup(async()=>{requests++;});
  await ui.submit();
  assert.equal(requests,0);assert.equal(ui.$('publish-dialog').open,true);
  assert.equal(ui.$('publish-notice').hidden,false);
  assert.match(ui.$('publish-notice').textContent,/플랫폼을 하나 이상/);
});
test('server rejection remains visible and allows retry',async()=>{
  const ui=setup(async()=>{throw Error('인증 실패');});ui.platforms[0].checked=true;
  await ui.submit();
  assert.equal(ui.$('publish-notice').textContent,'인증 실패');
  assert.equal(ui.$('publish-dialog').open,true);assert.equal(ui.$('publish-button').disabled,false);
});
test('pending submission blocks duplicates and successful request closes dialog',async()=>{
  let finish,requests=0;
  const ui=setup(()=>{requests++;return new Promise(resolve=>finish=resolve);});ui.platforms[0].checked=true;
  const pending=ui.submit();await ui.submit();
  assert.equal(requests,1);assert.equal(ui.$('publish-button').disabled,true);
  finish({});await pending;
  assert.equal(ui.$('publish-dialog').open,false);assert.equal(ui.$('publish-button').disabled,false);
});
test('TikTok requires an explicit privacy selection',async()=>{
  let requests=0;const ui=setup(async()=>{requests++;});ui.platforms[2].checked=true;
  await ui.submit();assert.equal(requests,0);
  assert.match(ui.$('publish-notice').textContent,/공개 범위를 선택/);
});
