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
  $("preview-info").textContent=job.error||`${job.duration?job.duration.toFixed(1)+"초 · ":""}${job.stage}${job.duration_note?" · "+job.duration_note:""}${job.subtitle_mode==="script"?" · 자막 시간은 대본 길이 기준 추정":""}`;
  $("preview-script").textContent=job.script||job.inputs.script||"";
  const actions=$("preview-actions");actions.replaceChildren();
  if(hasVideo){const a=node("a","MP4 다운로드 ↓");a.href=artifactURL(job,"video")+"?download=1";actions.append(a);const s=node("a","자막 ↓");s.href=artifactURL(job,"subtitles")+"?download=1";actions.append(s);}
  if(job.artifacts.thumbnail){const a=node("a","썸네일 JPG ↓");a.href=artifactURL(job,"thumbnail")+"?download=1";actions.append(a);}
  if(hasVideo&&!running&&job.status!=="publishing")actions.append(button("제목·썸네일 보기",()=>openPublishAssets(job)));
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
    const row=node("p",`${platform}: ${result.status==="failed"?"게시 실패":labels[result.status]||result.status}${result.error?" — "+result.error:""}`);
    if(result.url&&result.url.startsWith("https://")){const link=node("a"," 게시물 보기 ↗");link.href=result.url;link.target="_blank";link.rel="noopener noreferrer";row.append(link);}results.append(row);
    if(result.warning)results.append(node("p",result.warning,"error"));
  }
  if($("publish-dialog").open&&$("publish-dialog").dataset.jobId===job.id)renderPresentation(job);
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
let creatorRequest=0, creatorLoading=false, publishPending=false;
function renderPresentation(job){
  const panel=$("title-suggestions"), signature=JSON.stringify(job.title_suggestions||[]);
  if(panel.dataset.signature!==signature){
    panel.dataset.signature=signature;panel.replaceChildren();
    for(const title of job.title_suggestions||[]){const b=node("button",title,"title-choice");b.type="button";
      b.addEventListener("click",()=>{$("publish-title").value=title;});panel.append(b);}
  }
  const ready=Boolean(job.artifacts.thumbnail), img=$("publish-thumbnail");img.hidden=!ready;
  const link=$("thumbnail-download");link.hidden=!ready;
  if(ready){const url=artifactURL(job,"thumbnail");if(img.getAttribute("src")!==url)img.src=url;link.href=url+"?download=1";}
  const pending=["queued","running"].includes(job.presentation_status);
  $("prepare-presentation").disabled=pending||job.presentation_status==="ready";
  $("prepare-presentation").textContent=pending?"제목·썸네일 제작 중…":job.presentation_status==="ready"?"제목·썸네일 준비 완료":"추천 제목·썸네일 생성";
  $("presentation-info").textContent=job.presentation_error|| (ready?`썸네일 문구: ${job.thumbnail_title||""}`:"완성된 대본으로 제목 3개와 세로 썸네일을 만듭니다. 제목 생성에는 API 사용료가 발생합니다.");
  $("presentation-info").className=job.presentation_error?"error":"hint";
}
function openPublishAssets(job){openPublish(job);}
$("prepare-presentation").addEventListener("click",async()=>{
  const b=$("prepare-presentation");b.disabled=true;
  try{await api(`/api/jobs/${$("publish-dialog").dataset.jobId}/presentation`,{method:"POST"});b.textContent="제목·썸네일 제작 중…";}
  catch(err){publishNotice(err.message,true);b.disabled=false;}
});
function publishNotice(message,error=false){
  const el=$("publish-notice");el.textContent=message;el.className=error?"error":"";el.hidden=!message;
  if(error){el.focus();el.scrollIntoView({block:"nearest"});}
}
function openPublish(job){
  ++creatorRequest;creatorLoading=false;
  $("publish-dialog").dataset.jobId=job.id;$("publish-title").value=job.title||job.inputs.topic||"오늘의 숏츠";
  $("publish-description").value=(job.script||"")+"\n\nAI 음성을 사용한 영상입니다. #Shorts";
  $("tiktok-account").textContent="";$("tiktok-privacy").replaceChildren(new Option("계정 조회 후 공개 범위 선택",""));
  document.querySelectorAll('input[name="platform"]').forEach(e=>{e.checked=false;e.disabled=!config.connections[e.value];});
  renderPresentation(job);
  $("publish-button").hidden=!["approved","partial","upload_failed","published"].includes(job.status);
  publishNotice("");$("publish-dialog").showModal();
}
$("close-publish").addEventListener("click",()=>{if(!publishPending)$("publish-dialog").close();});
$("publish-dialog").addEventListener("cancel",e=>{if(publishPending)e.preventDefault();});
$("tiktok-check").addEventListener("change",async(e)=>{
  const request=++creatorRequest;creatorLoading=false;
  $("tiktok-privacy").replaceChildren(new Option("계정 조회 후 공개 범위 선택",""));$("tiktok-account").textContent="";
  if(!e.target.checked)return;
  creatorLoading=true;publishNotice("TikTok 계정과 공개 범위를 조회하고 있습니다…");
  try{
    const creator=await api("/api/tiktok/creator");if(request!==creatorRequest)return;
    $("tiktok-account").textContent=`게시 계정: ${creator.creator_nickname||creator.creator_username}`;
    const select=$("tiktok-privacy");select.replaceChildren(new Option("공개 범위를 선택해주세요",""));
    for(const option of creator.privacy_level_options||[])select.add(new Option(option,option));
    publishNotice("TikTok 공개 범위를 선택해주세요.");
  }catch(err){if(request===creatorRequest){e.target.checked=false;publishNotice(err.message,true);}}
  finally{if(request===creatorRequest)creatorLoading=false;}
});
$("publish-form").addEventListener("submit",async(e)=>{
  e.preventDefault();if(publishPending)return;
  const platforms=[...document.querySelectorAll('input[name="platform"]:checked')].map(e=>e.value);
  if(!platforms.length){publishNotice("게시할 플랫폼을 하나 이상 선택해주세요. 회색으로 표시된 플랫폼은 연결 설정이 필요합니다.",true);return;}
  if(platforms.includes("tiktok")&&(creatorLoading||!$("tiktok-privacy").value)){
    publishNotice(creatorLoading?"TikTok 계정 조회가 끝날 때까지 기다려주세요.":"TikTok 공개 범위를 선택해주세요.",true);return;
  }
  const b=$("publish-button");publishPending=true;b.disabled=true;b.textContent="게시 요청 중…";$("close-publish").disabled=true;
  publishNotice("게시 요청을 보내고 있습니다…");
  try{
    await api(`/api/jobs/${$("publish-dialog").dataset.jobId}/publish`,{method:"POST",body:JSON.stringify({platforms,title:$("publish-title").value,description:$("publish-description").value,youtube_privacy:$("youtube-privacy").value,tiktok_privacy:$("tiktok-privacy").value})});
  }catch(err){publishNotice(err.message,true);return;}
  finally{publishPending=false;b.disabled=false;b.textContent="선택한 플랫폼에 게시";$("close-publish").disabled=false;}
  $("publish-dialog").close();notice("게시 작업을 시작했습니다.");
  try{await refresh();}catch(err){notice(`게시 요청은 접수됐지만 상태 조회에 실패했습니다: ${err.message}`,true);}
});
$("create-form").addEventListener("submit",async(e)=>{e.preventDefault();if(!$("automatic").checked&&(!$("script").value.trim()||!$("script-reviewed").checked)){notice("대본을 작성하거나 생성한 뒤 검토 확인란을 체크해주세요.",true);return;}const b=$("create-button");b.disabled=true;try{const job=await api("/api/jobs",{method:"POST",body:JSON.stringify({category:$("category").value,topic:$("topic").value,notes:$("notes").value,script:$("automatic").checked?"":$("script").value,bgm:$("bgm").checked,subtitle_style:$("subtitle-style").value,tts_provider:$("tts-provider").value,voice:$("voice").value,speed:Number($("speed").value),background_queries:$("queries").value.split(",").map(s=>s.trim()).filter(Boolean)})});selected=job.id;notice("제작을 시작했습니다. 진행 상황을 오른쪽에서 확인하세요.");await refresh();}catch(err){notice(err.message,true);}finally{b.disabled=false;}});
$("refresh-button").addEventListener("click",()=>refresh().catch(e=>notice(e.message,true)));
let sourceRequest = 0, trendRequest = 0, chosenSources = [];
async function loadTrends(){
  const requestId=++trendRequest, category=$("category").value;
  const b=$("trend-button");b.disabled=true;b.textContent="주제 수집 중…";
  try{
    const data=await api(`/api/trends?category=${encodeURIComponent(category)}`);if(requestId!==trendRequest)return;const panel=$("trends");panel.replaceChildren();panel.hidden=false;
    panel.append(node("p",`${$("category").selectedOptions[0].textContent} 추천 ${data.topics.length}개 · 선택하면 기사 자료를 불러옵니다.${data.topics.length<10?" 현재 수집 가능한 결과만 표시합니다.":""}`));
    data.topics.forEach((topic,index)=>{
      const item=node("button",undefined,"trend-card");item.type="button";item.dataset.sourceUrl=topic.url;
      item.append(node("strong",`${index+1}. ${topic.title}`),node("small",`${topic.source} · ${topic.ranking_basis||"추천"}${typeof topic.score==="number"?" · 반응 "+topic.score:""}${topic.published_at?" · "+new Date(topic.published_at).toLocaleDateString("ko-KR"):""}`));
      item.addEventListener("click",async()=>{
        const combine=$("combine-sources").checked;
        if(combine&&chosenSources.some(s=>s.url===topic.url)){notice("이미 참고 자료에 포함된 기사입니다.");return;}
        if(combine&&chosenSources.length>=3){notice("최대 3개까지 함께 참고할 수 있습니다. 새로 시작하려면 기사 함께 엮기를 해제하세요.");return;}
        const requestId=++sourceRequest;
        $("create-button").disabled=true;$("draft-button").disabled=true;
        notice("선택한 기사의 본문을 불러오는 중입니다…");
        try{
          const data=await api("/api/source",{method:"POST",body:JSON.stringify({url:topic.url})});
          if(requestId!==sourceRequest)return;
          chosenSources=combine?[...chosenSources,{...topic,notes:data.notes}]:[{...topic,notes:data.notes}];
          $("topic").value=chosenSources.map(s=>s.title).join(" / ").slice(0,200);
          $("notes").value=chosenSources.map((s,i)=>`자료 ${i+1}: ${s.title}\n${s.notes}`).join("\n\n").slice(0,75000);
          $("script").value="";$("script-reviewed").checked=false;
          panel.querySelectorAll("button").forEach(el=>el.setAttribute("aria-pressed",String(chosenSources.some(s=>s.url===el.dataset.sourceUrl))));
          notice(`${chosenSources.length}개 기사 자료를 불러왔습니다. 영상 제작 시작을 누르면 대본부터 영상까지 자동으로 완성합니다.`);
        }catch(e){if(requestId===sourceRequest)notice(`${e.message} 출처: ${topic.url} — 핵심 사실을 직접 입력할 수 있습니다.`,true);}
        finally{if(requestId===sourceRequest){$("create-button").disabled=false;$("draft-button").disabled=false;}}
      });
      panel.append(item);
    });
  }catch(e){if(requestId===trendRequest)notice(e.message,true);}finally{if(requestId===trendRequest){b.disabled=false;b.textContent="추천 주제 10개 새로고침 ↻";}}
}
$("trend-button").addEventListener("click",loadTrends);
function updateVoice(){
  const provider=$("tts-provider").value;
  const eleven=provider==="elevenlabs"||(provider==="auto"&&config.connections.elevenlabs);
  $("voice").disabled=eleven;
  for(const option of $("speed").options)option.disabled=eleven&&(Number(option.value)<0.7||Number(option.value)>1.2);
  if(eleven&&Number($("speed").value)>1.2)$("speed").value="1.2";
}
$("tts-provider").addEventListener("change",updateVoice);
async function init(){try{config=await api("/api/config");csrf=config.csrf;$("category").replaceChildren(...config.categories.map(c=>new Option(c.label,c.id)));$("category").value=config.defaults.category;$("category").disabled=false;$("auto-create-button").disabled=false;const panel=$("connections");for(const [name,ready] of Object.entries(config.connections)){const el=node("div",name==="openai"?"OpenAI":name==="pexels"?"Pexels":name,"connection"+(ready?" ready":""));el.append(node("small",ready?"설정됨":"미설정"));panel.append(el);}$("voice").value=config.defaults.voice;$("speed").value=String(config.defaults.speed);$("tts-provider").value=config.defaults.tts_provider;updateVoice();await refresh();await loadTrends();}catch(e){notice(e.message,true);}}
init();setInterval(()=>{if(!document.hidden)refresh().catch(e=>notice(e.message,true));},4000);

for(const id of ["script","topic","notes"]){$(id).addEventListener("input",()=>{$("script-reviewed").checked=false;});}
$("draft-button").addEventListener("click",async()=>{
  const b=$("draft-button"), original={category:$("category").value,topic:$("topic").value,notes:$("notes").value,script:$("script").value};
  b.disabled=true;$("create-button").disabled=true;$("script-reviewed").checked=false;
  notice("대본 초안을 작성하고 있습니다…");
  try{
    const draft=await api("/api/draft",{method:"POST",body:JSON.stringify({category:original.category,topic:original.topic,notes:original.notes})});
    if(Object.keys(original).some(id=>$(id).value!==original[id])){notice("입력이 변경되어 이전 요청의 대본을 적용하지 않았습니다. 다시 생성해주세요.");return;}
    $("automatic").checked=false;$("script").value=draft.script;$("script-reviewed").checked=false;$("script-details").open=true;$("script").focus();
    notice("초안이 준비되었습니다. 문장·사실·발음을 수정하고 검토 확인 후 영상을 제작하세요.");
  }catch(e){notice(e.message,true);}finally{b.disabled=false;$("create-button").disabled=false;}
});
$("subtitle-style").addEventListener("change",()=>{$("caption-sample").classList.toggle("minimal",$("subtitle-style").value==="minimal");});

$("auto-create-button").addEventListener("click", async()=>{
  const b=$("auto-create-button"); b.disabled=true;
  notice("추천 주제를 선정하고 기사 자료를 수집하고 있습니다…");
  try {
    const job=await api("/api/jobs/auto", {method:"POST",body:JSON.stringify({
      category:$("category").value,tts_provider:$("tts-provider").value,voice:$("voice").value,speed:Number($("speed").value),
      bgm:$("bgm").checked,subtitle_style:$("subtitle-style").value
    })});
    selected=job.id; showJob(job);
    notice(["queued","running"].includes(job.status)?"자동 제작이 진행됩니다. 오른쪽에서 진행 상황을 확인하세요.":"오늘의 자동 제작 작업을 불러왔습니다.");
    await refresh();
  } catch(e) { notice(e.message,true); }
  finally { b.disabled=false; }
});

$("category").addEventListener("change",()=>{
  ++sourceRequest; chosenSources=[];
  for(const id of ["topic","notes","script","queries"])$(id).value="";
  $("script-reviewed").checked=false;
  $("trends").replaceChildren();$("trends").hidden=true;
  $("create-button").disabled=false;
  $("draft-button").disabled=false;
  notice("선택한 분야의 추천 소재를 불러옵니다…");
  loadTrends();
});
