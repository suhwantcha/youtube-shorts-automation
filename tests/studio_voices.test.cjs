const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
function setup(api){
  const elements=new Map();
  const $=id=>{if(!elements.has(id))elements.set(id,{value:'',options:[],addEventListener(){},replaceChildren(...options){this.options=options;this.value=options[0]?.value||'';}});return elements.get(id);};
  const context=vm.createContext({$,api,Option:function(text,value){this.text=text;this.value=value;},config:{defaults:{voice:'onyx'},connections:{elevenlabs:true}}});
  const source=fs.readFileSync('tech_shorts/static/studio.js','utf8');
  vm.runInContext(source.slice(source.indexOf('let voiceRequest='),source.indexOf('async function init')),context);
  return {$,run:code=>vm.runInContext(code,context)};
}
test('provider-specific selected voice is serialized without ignoring ElevenLabs selection',async()=>{
  const ui=setup(async()=>({provider:'elevenlabs',default:'first',voices:[{id:'first',name:'A'},{id:'second',name:'B'}]}));
  ui.$('tts-provider').value='auto';await ui.run('updateVoice()');ui.$('voice').value='second';
  assert.equal(ui.run('voiceOptions().elevenlabs_voice_id'),'second');
  assert.equal(ui.run('voiceOptions().voice'),'onyx');
});
test('stale voice response does not overwrite latest provider',async()=>{
  const done=[];const ui=setup(()=>new Promise(resolve=>done.push(resolve)));
  ui.$('tts-provider').value='elevenlabs';const old=ui.run('updateVoice()');
  ui.$('tts-provider').value='openai';const current=ui.run('updateVoice()');
  done[1]({provider:'openai',default:'coral',voices:[{id:'coral',name:'Coral'}]});await current;
  done[0]({provider:'elevenlabs',default:'first',voices:[{id:'first',name:'A'}]});await old;
  assert.equal(ui.run('voiceOptions().voice'),'coral');assert.equal(ui.run('voiceOptions().elevenlabs_voice_id'),'');
});
test('failed voice lookup blocks generation instead of silently using another voice',async()=>{
  const ui=setup(async()=>{throw Error('조회 실패');});await ui.run('updateVoice()');
  assert.throws(()=>ui.run('voiceOptions()'),/목소리를 선택/);
});
