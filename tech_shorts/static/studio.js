"use strict";
const $ = (id) => document.getElementById(id);
let csrf = "", jobs = [], selected = null, config = {}, busy = false;
const labels = {queued:"대기 중",running:"제작 중",failed:"제작 실패",interrupted:"중단됨",pending_approval:"검토 대기",approved:"승인 완료",rejected:"검토 제외",publishing:"게시 중",published:"게시 완료",partial:"일부 완료",processing:"플랫폼 처리 중",upload_failed:"게시 실패",needs_attention:"확인 필요"};
async function api(path, options={}) {
  const headers = {"Content-Type":"application/json", "X-CSRF-Token":csrf, ...(options.headers||{})};
  const response = await fetch(path, {...options, headers});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `요청 실패 (${response.status})`);
  return data;
}
function notice(message, error=false) { $("notice").textContent=message; $("notice").className=error?"error":""; $("notice").hidden=false; }
function node(tag, text, className) {const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(className)el.className=className;return el;}
function badge(status) { return node("span", labels[status]||status, "badge"+(["published","approved"].includes(status)?" good":["failed","upload_failed","needs_attention"].includes(status)?" error":"")); }
function artifactURL(job, key) {return `/api/jobs/${job.id}/artifacts/${key}`;}
function button(text, action, primary=false) { const b=node("button",text,primary?"primary":"secondary");b.type="button";b.addEventListener("click",async()=>{b.disabled=true;try{await action();await refresh();}catch(e){notice(e.message,true);}finally{b.disabled=false;}});return b; }
function showJob(job) {
  selected=job.id;
  const running=["running","queued"].includes(job.status);
  $("preview-status").replaceWith(Object.assign(badge(job.status),{id:"preview-status"}));
  $("preview-empty").hidden=true;$("progress").hidden=!running;$("preview-content").hidden=running;
  $("progress-stage").textContent=job.stage;
  if (running) return;
  const hasVideo=Boolean(job.artifacts.video);$("player").hidden=!hasVideo;
  if(hasVideo){const src=artifactURL(job,"video");if($("player").getAttribute("src")!==src)$("player").src=src;}
  else {$("player").removeAttribute("src");$("player").load();}
  $("preview-title").textContent=job.title||job.inputs.topic||"직접 작성한 대본";
  $("preview-info").textContent=job.error||`${job.duration?job.duration.toFixed(1)+"초 · ":""}${job.stage}${job.subtitle_mode==="script"?" · 자막 시간은 대본 길이 기준 추정":""}`;
  $("preview-script").textContent=job.script||job.inputs.script||"";
  const actions=$("preview-actions");actions.replaceChildren();
  if(hasVideo){const a=node("a","MP4 다운로드 ↓");a.href=artifactURL(job,"video")+"?download=1";actions.append(a);const s=node("a","자막 ↓");s.href=artifactURL(job,"subtitles")+"?download=1";actions.append(s);}
  if(job.status==="pending_approval"){
    actions.append(button("승인",()=>api(`/api/jobs/${job.id}/review`,{method:"POST",body:JSON.stringify({action:"approve"})}),true));
    actions.append(button("거부",()=>api(`/api/jobs/${job.id}/review`,{method:"POST",body:JSON.stringify({action:"reject"})})));
    if(config.connections.gmail)actions.append(button("검토 이메일 보내기",async()=>{await api(`/api/jobs/${job.id}/email`,{method:"POST"});notice("검토 이메일을 보냈습니다.");}));
  }
  if(["failed","interrupted"].includes(job.status))actions.append(button("제작 재시도",()=>api(`/api/jobs/${job.id}/retry`,{method:"POST"}),true));
  if(["approved","partial","upload_failed","published"].includes(job.status))actions.append(button("플랫폼에 게시",()=>openPublish(job),true));
  if(["processing","needs_attention","partial"].includes(job.status))actions.append(button("게시 상태 확인",()=>api(`/api/jobs/${job.id}/refresh-uploads`,{method:"POST"})));
  const results=$("upload-results");results.replaceChildren();
  for(const [platform,result] of Object.entries(job.uploads||{})){
    const row=node("p",`${platform}: ${labels[result.status]||result.status}${result.error?" — "+result.error:""}`);
    if(result.url&&result.url.startsWith("https://")){const link=node("a"," 게시물 보기 ↗");link.href=result.url;link.target="_blank";link.rel="noopener noreferrer";row.append(link);}results.append(row);
  }
  if(job.status==="needs_attention")results.append(node("p","응답이 끊긴 업로드는 실제 게시되었을 수 있습니다. 계정에서 결과를 확인하기 전에는 다시 업로드하지 않습니다."));
}
function renderJobs(){const list=$("job-list");list.replaceChildren();$("job-count").textContent=jobs.length;
  if(!jobs.length){list.append(node("div","아직 제작한 영상이 없습니다. 첫 번째 이야기를 시작해보세요.","empty-library"));return;}
  for(const job of jobs){const row=node("button",undefined,"job-row"+(selected===job.id?" selected":""));row.type="button";
    row.append(node("span","▶","job-icon"));const title=node("span");title.append(node("span",job.title||job.inputs.topic||"직접 작성한 대본","job-title"));
    title.append(node("span",new Date(job.created_at).toLocaleString("ko-KR"),"job-time"));row.append(title,node("span",job.stage,"job-stage"),badge(job.status));
    row.addEventListener("click",()=>{showJob(job);renderJobs();});list.append(row);}
}
async function refresh(){if(busy)return;busy=true;try{jobs=(await api("/api/jobs")).jobs;const current=jobs.find(j=>j.id===selected);if(current)showJob(current);else if(jobs.length&&!selected)showJob(jobs[0]);renderJobs();}finally{busy=false;}}
function openPublish(job){$("publish-dialog").dataset.jobId=job.id;$("publish-title").value=job.title||job.inputs.topic||"테크 숏츠";$("publish-description").value=(job.script||"")+"\n\nAI 음성을 사용한 영상입니다. #Shorts #테크";
  document.querySelectorAll('input[name="platform"]').forEach(e=>{e.checked=false;e.disabled=!config.connections[e.value];});$("publish-dialog").showModal();}
$("close-publish").addEventListener("click",()=>$("publish-dialog").close());
$("tiktok-check").addEventListener("change",async(e)=>{if(!e.target.checked)return;try{const creator=await api("/api/tiktok/creator");$("tiktok-account").textContent=`게시 계정: ${creator.creator_nickname||creator.creator_username}`;const select=$("tiktok-privacy");select.replaceChildren(new Option("공개 범위를 선택해주세요",""));for(const option of creator.privacy_level_options||[])select.add(new Option(option,option));}catch(err){e.target.checked=false;notice(err.message,true);}});
$("publish-form").addEventListener("submit",async(e)=>{e.preventDefault();const b=e.submitter;b.disabled=true;try{const platforms=[...document.querySelectorAll('input[name="platform"]:checked')].map(e=>e.value);await api(`/api/jobs/${$("publish-dialog").dataset.jobId}/publish`,{method:"POST",body:JSON.stringify({platforms,title:$("publish-title").value,description:$("publish-description").value,youtube_privacy:$("youtube-privacy").value,tiktok_privacy:$("tiktok-privacy").value})});$("publish-dialog").close();notice("게시 작업을 시작했습니다.");await refresh();}catch(err){notice(err.message,true);}finally{b.disabled=false;}});
$("create-form").addEventListener("submit",async(e)=>{e.preventDefault();const b=$("create-button");b.disabled=true;try{const job=await api("/api/jobs",{method:"POST",body:JSON.stringify({topic:$("topic").value,notes:$("notes").value,script:$("script").value,tts_provider:$("tts-provider").value,voice:$("voice").value,speed:Number($("speed").value),background_queries:$("queries").value.split(",").map(s=>s.trim()).filter(Boolean)})});selected=job.id;notice("제작을 시작했습니다. 진행 상황을 오른쪽에서 확인하세요.");await refresh();}catch(err){notice(err.message,true);}finally{b.disabled=false;}});
$("refresh-button").addEventListener("click",()=>refresh().catch(e=>notice(e.message,true)));
let sourceRequest = 0;
async function loadTrends(){
  const b=$("trend-button");b.disabled=true;b.textContent="주제 수집 중…";
  try{
    const data=await api("/api/trends");const panel=$("trends");panel.replaceChildren();panel.hidden=false;
    panel.append(node("p",`추천 주제 ${data.topics.length}개 · 선택하면 기사 자료를 불러옵니다.`));
    data.topics.forEach((topic,index)=>{
      const item=node("button",undefined,"trend-card");item.type="button";
      item.append(node("strong",`${index+1}. ${topic.title}`),node("small",`${topic.source} · 반응 ${topic.score}`));
      item.addEventListener("click",async()=>{
        const requestId=++sourceRequest;
        panel.querySelectorAll("button").forEach(el=>el.setAttribute("aria-pressed",String(el===item)));
        $("topic").value=topic.title.slice(0,200);$("notes").value="";$("script").value="";
        $("create-button").disabled=true;notice("선택한 기사의 본문을 불러오는 중입니다…");
        try{
          const data=await api("/api/source",{method:"POST",body:JSON.stringify({url:topic.url})});
          if(requestId!==sourceRequest)return;
          $("notes").value=data.notes;notice("자료를 불러왔습니다. 확인 후 ‘선택한 주제로 영상 제작’을 누르세요.");
        }catch(e){if(requestId===sourceRequest){$("notes").value="";notice(`${e.message} 출처: ${topic.url} — 참고 자료에 핵심 사실을 직접 입력해주세요.`,true);}}
        finally{if(requestId===sourceRequest)$("create-button").disabled=false;}
      });
      panel.append(item);
    });
  }catch(e){notice(e.message,true);}finally{b.disabled=false;b.textContent="추천 주제 10개 새로고침 ↻";}
}
$("trend-button").addEventListener("click",loadTrends);
function updateVoice(){
  const provider=$("tts-provider").value;
  const eleven=provider==="elevenlabs"||(provider==="auto"&&config.connections.elevenlabs);
  $("voice").disabled=eleven;
  for(const option of $("speed").options)option.disabled=eleven&&(Number(option.value)<0.7||Number(option.value)>1.2);
  if(eleven&&Number($("speed").value)>1.2)$("speed").value="1.1";
}
$("tts-provider").addEventListener("change",updateVoice);
async function init(){try{config=await api("/api/config");csrf=config.csrf;const panel=$("connections");for(const [name,ready] of Object.entries(config.connections)){const el=node("div",name==="openai"?"OpenAI":name==="pexels"?"Pexels":name,"connection"+(ready?" ready":""));el.append(node("small",ready?"설정됨":"미설정"));panel.append(el);}$("voice").value=config.defaults.voice;$("speed").value=String(config.defaults.speed);$("tts-provider").value=config.defaults.tts_provider;updateVoice();await refresh();await loadTrends();}catch(e){notice(e.message,true);}}
init();setInterval(()=>{if(!document.hidden)refresh().catch(e=>notice(e.message,true));},4000);
