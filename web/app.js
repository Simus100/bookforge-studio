'use strict';
const $ = (id) => document.getElementById(id);
function applyTheme(value, remember=false) {
  const theme=value==='dark'?'dark':'light';
  document.documentElement.dataset.theme=theme;
  if($('theme-select'))$('theme-select').value=theme;
  if(remember){try{localStorage.setItem('bf-theme',theme);}catch{}}
}
try{applyTheme(localStorage.getItem('bf-theme'));}catch{applyTheme('light');}
let state, token, chapterId, units = [], chapterHash = '', selection = null, filter = 'open';
let voice = localStorage.getItem('bf-voice') || 'paola', voiceInfo, pollVoices, toastTimer;
let autoVoice = localStorage.getItem('bf-auto-voice') !== 'false';
let loadingChapter = 0, pendingRestore = null;
let fontSize = Number(localStorage.getItem('bf-font') || 20);
const player = {ctx:null, active:false, paused:false, generation:0, index:0, sources:[], schedule:[], timer:null, buffers:new Map()};
const labels = {queued:'Da inviare', exported:'In lavorazione', proposed:'Da valutare', applied:'Applicata', rejected:'Archiviata'};
const categories = {generale:'Revisione',voce:'Voce e stile',ritmo:'Ritmo',dialoghi:'Dialoghi',continuita:'Continuità',chiarezza:'Chiarezza',refuso:'Refuso'};

function el(tag, className, text) { const node=document.createElement(tag); if(className) node.className=className; if(text!==undefined)node.textContent=text;return node; }
function words(text) {return (text.match(/\S+/gu)||[]).length;}
function chapter() {return state.chapters.find(x=>x.id===chapterId)||state.chapters[0];}
function toast(message, error=false) {clearTimeout(toastTimer);$('toast').textContent=message;$('toast').className='toast'+(error?' error':'');toastTimer=setTimeout(()=>$('toast').classList.add('hidden'),error?11000:5500);}
async function api(path, data) {
  let response;
  try {response=await fetch(path,data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-BookForge-Token':token},body:JSON.stringify({...data,revision:state?.revision})});}
  catch {throw new Error('Il servizio locale non risponde. Riavvia BookForge Studio: il progetto resta salvato.');}
  const result=await response.json();
  if(!response.ok)throw new Error(result.error||'Operazione non riuscita.');
  return result;
}
async function action(fn) {try{return await fn();}catch(error){toast(error.message,true);}}
function showDialog(id) {hideSelection();$(id).showModal();}
function hideSelection() {$('selection-menu').classList.add('hidden');}
function download(name,data,type='application/json') {const blob=new Blob([typeof data==='string'?data:JSON.stringify(data,null,2)],{type});const url=URL.createObjectURL(blob);const link=el('a');link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),2000);}
function safeName(text) {return text.replace(/[^\p{L}\p{N}_-]+/gu,'-').slice(0,60)||'libro';}

async function init() {
  const result=await api('/api/state');state=result.state;token=result.token;
  chapterId=localStorage.getItem('bf-chapter-'+state.book_id)||state.chapters[0].id;
  if(!state.chapters.some(x=>x.id===chapterId))chapterId=state.chapters[0].id;
  document.documentElement.style.setProperty('--reading-size',fontSize+'px');
  bind();await render(true);await refreshVoices();
}

async function acceptState(result, reloadText=true) {state=result.state;if(!state.chapters.some(x=>x.id===chapterId))chapterId=state.chapters[0].id;await render(reloadText);}
async function render(reloadText=false) {
  $('project-title').textContent=state.title;document.title=state.title+' — BookForge Studio';
  const nav=$('chapter-list');nav.replaceChildren();
  state.chapters.forEach((ch,i)=>{const button=el('button','chapter-item'+(ch.id===chapterId?' active':''));button.setAttribute('aria-current',ch.id===chapterId?'page':'false');button.append(el('span','chapter-index',String(i+1).padStart(2,'0')));const info=el('span');info.append(el('span','chapter-name',ch.title),el('span','chapter-words',words(ch.text).toLocaleString('it-IT')+' parole'));button.append(info);button.onclick=()=>action(()=>selectChapter(ch.id));nav.append(button);});
  const ch=chapter();$('chapter-number').textContent='CAPITOLO '+String(state.chapters.indexOf(ch)+1).padStart(2,'0');
  $('demo-label').classList.toggle('hidden',!ch.title.includes('testo dimostrativo'));
  $('chapter-title').textContent=ch.title.replace(' · testo dimostrativo','');
  $('chapter-meta').textContent='REVISIONE '+ch.revision+'  ·  '+Math.max(1,Math.ceil(words(ch.text)/210))+' MIN DI LETTURA';
  $('word-count').textContent=words(ch.text).toLocaleString('it-IT')+' parole';
  if(reloadText) {
    stopAudio();selection=null;hideSelection();
    const sequence=++loadingChapter;
    const result=await api('/api/sentences?chapter_id='+encodeURIComponent(ch.id));
    if(sequence!==loadingChapter)return;
    units=result.sentences;chapterHash=result.sha256;player.index=0;
    renderProse();$('audio-progress').value=0;$('sentence-count').textContent=units.length?'1 / '+units.length:'0 / 0';
  } else markAnnotations();
  renderRequests();
}

async function selectChapter(id) {if(id===chapterId)return;chapterId=id;localStorage.setItem('bf-chapter-'+state.book_id,id);$('scroll-page').scrollTop=0;await render(true);}

function renderProse() {
  const prose=$('prose');prose.replaceChildren();const text=chapter().text;const chars=Array.from(text);let position=0;
  units.forEach((unit,i)=>{if(unit.start>position)prose.append(document.createTextNode(chars.slice(position,unit.start).join('')));const span=el('span','sentence',unit.text);span.dataset.index=i;span.id='sentence-'+i;span.title='Doppio clic con Alt: ascolta da qui';prose.append(span);position=unit.end;});
  if(position<chars.length)prose.append(document.createTextNode(chars.slice(position).join('')));
  if(!text)prose.append(el('span','muted','Questo capitolo è vuoto. Usa Modifica per iniziare.'));
  markAnnotations();
}
function markAnnotations() {
  const requests=state.requests.filter(x=>x.chapter_id===chapterId&&!['applied','rejected'].includes(x.status)&&!x.conflict);
  document.querySelectorAll('.sentence').forEach((span)=>{const u=units[Number(span.dataset.index)];span.classList.toggle('annotated',requests.some(r=>r.start<u.end&&u.start<r.end));});
}
function captureSelection() {
  if(document.querySelector('dialog[open]'))return;
  const current=window.getSelection();const prose=$('prose');
  if(!current?.rangeCount||current.isCollapsed){hideSelection();return;}
  const range=current.getRangeAt(0);
  if(!prose.contains(range.startContainer)||!prose.contains(range.endContainer)){hideSelection();return;}
  const prefix=document.createRange();prefix.selectNodeContents(prose);prefix.setEnd(range.startContainer,range.startOffset);
  let start=Array.from(prefix.toString()).length;
  let selected=range.toString();const lead=selected.match(/^\s*/u)[0];start+=Array.from(lead).length;selected=selected.trim();
  if(!selected){hideSelection();return;}
  const end=start+Array.from(selected).length;
  if(Array.from(chapter().text).slice(start,end).join('')!==selected){hideSelection();return;}
  selection={start,end,original:selected,chapter_id:chapterId};
  const rect=range.getBoundingClientRect();const menu=$('selection-menu');
  menu.classList.remove('hidden');const x=Math.max(150,Math.min(innerWidth-150,rect.left+rect.width/2));
  menu.style.left=x+'px';menu.style.top=Math.max(80,Math.min(innerHeight-155,rect.top-50))+'px';
  $('selection-length').textContent=words(selected)+' parole';
}
function annotate(selected=selection) {if(!selected)return toast('Seleziona prima un brano del testo.');selection={...selected};$('selected-quote').textContent=selection.original;$('annotation-comment').value='';showDialog('annotation-dialog');setTimeout(()=>$('annotation-comment').focus(),30);}
function locateRequest(item) {
  if(item.chapter_id!==chapterId)return action(async()=>{await selectChapter(item.chapter_id);locateRequest(item);});
  if(item.conflict)return toast('Il brano è cambiato: questa annotazione conserva la versione originale.',true);
  const idx=units.findIndex(x=>x.start<item.end&&item.start<x.end);if(idx<0)return;
  const node=$('sentence-'+idx);node?.scrollIntoView({behavior:'smooth',block:'center'});node?.classList.add('request-focus');setTimeout(()=>node?.classList.remove('request-focus'),2200);
}

function diffParts(original,replacement) {
  const a=Array.from(original),b=Array.from(replacement);let first=0,lastA=a.length,lastB=b.length;
  while(first<lastA&&first<lastB&&a[first]===b[first])first++;
  while(lastA>first&&lastB>first&&a[lastA-1]===b[lastB-1]){lastA--;lastB--;}
  return {prefix:a.slice(0,first).join(''),removed:a.slice(first,lastA).join(''),added:b.slice(first,lastB).join(''),suffix:a.slice(lastA).join('')};
}
function renderRequests() {
  const all=state.requests;const open=all.filter(x=>!['applied','rejected'].includes(x.status));const proposals=open.filter(x=>x.status==='proposed');const queued=open.filter(x=>x.status==='queued'&&!x.conflict);
  $('request-count').textContent=all.length;$('open-count').textContent=open.length;$('proposal-count').textContent=proposals.length;$('export-count').textContent=queued.length;$('export-btn').disabled=!queued.length;
  $('last-batch').classList.toggle('hidden',!state.batches.length);
  document.querySelectorAll('[data-filter]').forEach(x=>{x.classList.toggle('active',x.dataset.filter===filter);x.setAttribute('aria-pressed',String(x.dataset.filter===filter));});
  const items=all.filter(x=>filter==='closed'?['applied','rejected'].includes(x.status):filter==='proposed'?x.status==='proposed':!['applied','rejected'].includes(x.status)).slice().reverse();
  const target=$('review-content');target.replaceChildren();
  if(!items.length){const empty=el('div','empty-state');empty.append(el('div','empty-icon','❧'),el('h3','',filter==='proposed'?'Le proposte arriveranno qui.':filter==='closed'?'Ogni scelta lascia una traccia.':'Il libro comincia dal tuo sguardo.'));empty.append(el('p','',filter==='proposed'?'Importa il file restituito dall’AI per confrontare le riscritture.':filter==='closed'?'Qui troverai le correzioni applicate e le richieste archiviate.':'Seleziona una frase, un dialogo o un passaggio. Scrivi cosa vorresti migliorare.'));if(filter==='open')empty.append(el('div','empty-hint','Se stai ascoltando, usa «Annota qui» per fermare un pensiero senza perdere il punto.'));target.append(empty);return;}
  for(const item of items) {
    const card=el('article','review-card');card.dataset.requestId=item.id;const top=el('div','card-top');top.append(el('span','status '+(item.conflict?'conflict':item.status),item.conflict?'Da riallineare':labels[item.status]),el('span','card-category',categories[item.category]||'Revisione'));card.append(top);
    const quote=el('button','quote-button',item.original);quote.title='Vai al brano';quote.onclick=()=>locateRequest(item);card.append(quote,el('p','card-comment',item.comment));
    if(item.conflict&&!['applied','rejected'].includes(item.status))card.append(el('p','conflict-message',item.conflict));
    if(item.proposal) {
      card.append(el('div','proposal-label',item.status==='applied'?'TESTO APPLICATO':'PROPOSTA DELL’AI'));
      const diff=diffParts(item.original,item.proposal.replacement);const content=el('div','proposal-text');content.append(document.createTextNode(diff.prefix));if(diff.removed)content.append(el('del','',diff.removed));if(diff.added)content.append(el('ins','',diff.added));content.append(document.createTextNode(diff.suffix));if(!item.proposal.replacement)content.append(el('span','muted',' [Eliminazione del brano]'));card.append(content);
      if(item.proposal.reason)card.append(el('p','proposal-reason',item.proposal.reason));
      if(item.status==='proposed') {
        const controls=el('div','proposal-actions');const reject=el('button','button secondary','Archivia');reject.onclick=()=>resolve(item,'reject');const apply=el('button','button primary','Approva e applica');apply.disabled=!!item.conflict;apply.onclick=()=>resolve(item,'apply');controls.append(reject,apply);card.append(controls);
      }
    }
    const ch=state.chapters.find(x=>x.id===item.chapter_id);const footer=el('div','card-footer');footer.append(el('span','',(ch?.title||'Capitolo').replace(' · testo dimostrativo','')));
    if(!['applied','rejected','proposed'].includes(item.status)){const discard=el('button','quiet-link','Archivia');discard.onclick=()=>resolve(item,'reject');footer.append(discard);}
    card.append(footer);target.append(card);
  }
}
function resolve(item, act) {return action(async()=>{const result=await api('/api/request/resolve',{request_id:item.id,action:act});await acceptState(result,act==='apply');toast(act==='apply'?'Correzione applicata. Puoi annullarla dalla barra sotto il testo.':'Richiesta archiviata.');});}

async function refreshVoices() {
  voiceInfo=await api('/api/voices');
  if(autoVoice&&!player.active)voice=voiceInfo.recommendation;
  $('auto-voice').checked=autoVoice;
  if(!voiceInfo.voices.some(x=>x.id===voice))voice='paola';
  const selected=voiceInfo.voices.find(x=>x.id===voice);$('voice-name').textContent=selected.name;$('voice-description').textContent=selected.installed?'Voce locale · '+selected.profile.toLowerCase():'Da scaricare · '+selected.profile.toLowerCase();
  const container=$('voice-list');container.replaceChildren();
  for(const v of voiceInfo.voices){const row=el('div','voice-card'+(voice===v.id?' selected':''));const info=el('div');const title=el('h3','',v.name);title.append(el('span','profile-badge',v.profile));info.append(title,el('p','',v.description));if(!v.installed)info.append(el('p','',v.id==='studio'?'Diversi GB · installazione opzionale':'Circa '+v.download_mb+' MB · scaricati una volta'));
    const controls=el('div');if(v.job?.status==='running'){controls.append(el('div','download-status',v.job.message),Object.assign(el('progress'),{max:100,value:v.job.progress}));}
    else{const button=el('button','button '+(v.installed?'secondary':'primary'),v.installed?(voice===v.id?'Selezionata':'Usa voce'):(v.job?.status==='error'?'Riprova':'Scarica'));button.disabled=v.installed&&voice===v.id;button.onclick=()=>action(async()=>{if(v.installed){stopAudio();autoVoice=false;localStorage.setItem('bf-auto-voice','false');voice=v.id;localStorage.setItem('bf-voice',voice);await refreshVoices();toast('Voce selezionata: '+v.name);}else{await api('/api/voice/install',{voice:v.id});await refreshVoices();}});controls.append(button);if(v.job?.status==='error')info.append(el('p','download-status error',v.job.message.slice(-650)));}
    row.append(info,controls);container.append(row);
  }
  $('benchmark-label').textContent=voiceInfo.last_rtf===null?'La velocità sarà misurata alla prima lettura.':`Ultima generazione: ${voiceInfo.last_rtf} secondi di calcolo per secondo di audio. Sotto 1, la generazione è più veloce dell’ascolto.`;
  clearTimeout(pollVoices);if(voiceInfo.voices.some(v=>v.job?.status==='running'))pollVoices=setTimeout(()=>action(refreshVoices),1500);
}

function stopAudio(reset=false) {
  player.active=false;player.paused=false;player.generation++;clearInterval(player.timer);player.timer=null;
  player.sources.forEach(s=>{try{s.stop();s.disconnect();}catch{}});player.sources=[];player.schedule=[];
  if(reset)player.index=0;
  document.querySelectorAll('.speaking').forEach(x=>x.classList.remove('speaking'));
  $('play-btn').textContent='▶';$('play-btn').setAttribute('aria-label','Avvia lettura');$('play-position').textContent='Pronto all’ascolto';
}
async function getBuffer(index, generation) {
  const key=chapterHash+'|'+voice+'|'+index;
  if(player.buffers.has(key))return player.buffers.get(key);
  const voiceSnapshot=voice, hashSnapshot=chapterHash, ch=chapterId;
  const pending=(async()=>{const result=await api('/api/speech',{chapter_id:ch,sha256:hashSnapshot,index,voice:voiceSnapshot});const response=await fetch(result.url);if(!response.ok)throw new Error('Audio non disponibile. Riavvia la lettura.');const data=await response.arrayBuffer();return player.ctx.decodeAudioData(data);})();
  player.buffers.set(key,pending);try{const buffer=await pending;player.buffers.set(key,buffer);while(player.buffers.size>20)player.buffers.delete(player.buffers.keys().next().value);return buffer;}catch(error){player.buffers.delete(key);throw error;}
}
async function startAudio(index=player.index) {
  if(!units.length)return toast('Aggiungi un testo al capitolo per ascoltarlo.');
  const v=voiceInfo?.voices.find(x=>x.id===voice);if(!v?.installed){showDialog('voices-dialog');return toast('Scarica una voce locale per iniziare.');}
  stopAudio();player.index=Math.max(0,Math.min(units.length-1,index));const generation=player.generation;
  if(!player.ctx)player.ctx=new AudioContext();await player.ctx.resume();player.active=true;player.paused=false;
  $('play-btn').textContent='Ⅱ';$('play-btn').setAttribute('aria-label','Metti in pausa');$('play-position').textContent='Preparo la voce…';
  let next=player.index,endAt=player.ctx.currentTime;
  player.timer=setInterval(()=>updatePlayback(generation),65);
  try {
    while(player.active&&generation===player.generation&&next<units.length){
      const outstanding=player.schedule.filter(x=>x.end>player.ctx.currentTime).length;
      if(outstanding>=3||player.paused){await new Promise(r=>setTimeout(r,100));continue;}
      const buffer=await getBuffer(next,generation);
      if(!player.active||generation!==player.generation)return;
      const source=player.ctx.createBufferSource();source.buffer=buffer;source.playbackRate.value=speed;
      source.connect(player.ctx.destination);const at=Math.max(endAt,player.ctx.currentTime+.035);const duration=buffer.duration/speed;
      source.start(at);player.sources.push(source);player.schedule.push({index:next,start:at,end:at+duration});endAt=at+duration+.035;next++;
      if(player.schedule.length>8)player.schedule=player.schedule.filter(x=>x.end>player.ctx.currentTime-5);
    }
    while(player.active&&generation===player.generation&&player.ctx.currentTime<endAt){await new Promise(r=>setTimeout(r,100));}
    if(generation===player.generation&&player.active){player.index=0;stopAudio();$('play-position').textContent='Capitolo ascoltato';$('audio-progress').value=1;}
  } catch(error){if(generation===player.generation){stopAudio();toast(error.message,true);}}
}
function updatePlayback(generation) {
  if(generation!==player.generation||!player.active)return;
  if(player.paused)return;
  const t=player.ctx.currentTime;const current=player.schedule.find(x=>x.start<=t&&t<x.end);
  if(!current)return;
  if(player.index!==current.index||!$('sentence-'+current.index)?.classList.contains('speaking')){
    player.index=current.index;document.querySelectorAll('.speaking').forEach(x=>x.classList.remove('speaking'));const span=$('sentence-'+current.index);span?.classList.add('speaking');
    if($('follow-check').checked&&span){const r=span.getBoundingClientRect(),bounds=$('scroll-page').getBoundingClientRect();if(r.top<bounds.top+35||r.bottom>bounds.bottom-40)span.scrollIntoView({behavior:'smooth',block:'center'});}
    $('sentence-count').textContent=(current.index+1)+' / '+units.length;$('play-position').textContent='Frase '+(current.index+1)+' di '+units.length;
  }
  $('audio-progress').value=(current.index+(t-current.start)/(current.end-current.start))/units.length;
}
let speed=1;
function notePlaying(){if(!units.length)return;const unit=units[player.index]||units[0];if(player.active&&!player.paused)togglePlay();annotate({...unit,original:unit.text,chapter_id:chapterId});}
async function togglePlay(){if(!player.active)return startAudio();if(player.paused){await player.ctx.resume();player.paused=false;$('play-btn').textContent='Ⅱ';$('play-btn').setAttribute('aria-label','Metti in pausa');}else{await player.ctx.suspend();player.paused=true;$('play-btn').textContent='▶';$('play-btn').setAttribute('aria-label','Riprendi lettura');$('play-position').textContent='In pausa';}}

function bind() {
  $('theme-select').value=document.documentElement.dataset.theme;
  $('theme-select').onchange=()=>applyTheme($('theme-select').value,true);
  document.querySelectorAll('.close-dialog').forEach(button=>button.addEventListener('click',()=>button.closest('dialog').close()));
  document.querySelectorAll('dialog').forEach(d=>d.addEventListener('click',e=>{if(e.target===d){const r=d.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)d.close();}}));
  $('prose').addEventListener('mouseup',()=>setTimeout(captureSelection,20));$('prose').addEventListener('keyup',captureSelection);
  $('scroll-page').addEventListener('scroll',hideSelection);document.addEventListener('mousedown',e=>{if(!e.target.closest('#selection-menu')&&!e.target.closest('#prose'))hideSelection();});
  $('selection-menu').addEventListener('mousedown',e=>e.preventDefault());
  $('annotate-btn').onclick=()=>annotate();$('listen-selection').onclick=()=>action(()=>{const idx=units.findIndex(x=>x.end>selection.start);hideSelection();window.getSelection()?.removeAllRanges();return startAudio(Math.max(0,idx));});
  $('annotation-form').onsubmit=e=>{e.preventDefault();action(async()=>{const comment=$('annotation-comment').value.trim();if(!comment)return;const result=await api('/api/request/add',{...selection,comment,category:$('annotation-category').value});await acceptState(result,false);$('annotation-dialog').close();window.getSelection()?.removeAllRanges();filter='open';renderRequests();toast('Richiesta aggiunta alla coda.');});};
  document.querySelectorAll('[data-filter]').forEach(b=>b.onclick=()=>{filter=b.dataset.filter;renderRequests();});
  $('edit-btn').onclick=()=>{if(player.active)stopAudio();$('edit-title').value=chapter().title;$('edit-text').value=chapter().text;showDialog('edit-dialog');};
  $('edit-form').onsubmit=e=>{e.preventDefault();action(async()=>{const result=await api('/api/chapter/save',{chapter_id:chapterId,title:$('edit-title').value,text:$('edit-text').value});await acceptState(result,true);$('edit-dialog').close();toast('Capitolo salvato.');});};
  const settings=()=>{$('book-title').value=state.title;$('book-brief').value=state.brief;showDialog('settings-dialog');};$('settings-btn').onclick=settings;$('rules-btn').onclick=settings;
  $('settings-form').onsubmit=e=>{e.preventDefault();action(async()=>{await acceptState(await api('/api/settings',{title:$('book-title').value,brief:$('book-brief').value}),false);$('settings-dialog').close();toast('Regole editoriali salvate.');});};
  $('add-chapter').onclick=()=>action(async()=>{const result=await api('/api/chapter/add',{title:'Nuovo capitolo',text:''});state=result.state;chapterId=result.chapter_id;await render(true);$('edit-btn').click();});
  $('import-chapter').onclick=()=>$('chapter-file').click();
  $('chapter-file').onchange=()=>action(async()=>{for(const file of $('chapter-file').files){if(file.size>5_000_000)throw new Error('Il capitolo supera il limite di 5 MB.');const text=await file.text();const result=await api('/api/chapter/add',{title:file.name.replace(/\.(txt|md)$/i,''),text});state=result.state;chapterId=result.chapter_id;}await render(true);$('chapter-file').value='';toast('Testo importato. Puoi iniziare ad annotare.');});
  $('export-btn').onclick=()=>action(async()=>{const result=await api('/api/batch/export',{});await acceptState(result,false);download('BookForge-richieste-'+result.package.batch_id.slice(0,8)+'.json',result.package);showDialog('export-dialog');});
  $('last-batch').onclick=()=>{const b=state.batches.at(-1);download('BookForge-richieste-'+b.id.slice(0,8)+'.json',b.package);showDialog('export-dialog');};
  $('copy-instructions').onclick=()=>action(async()=>{await navigator.clipboard.writeText('Leggi il pacchetto BookForge allegato. Segui il campo instructions e le regole editorial_rules. Revisiona esclusivamente i brani indicati in requests, usando chapters per il contesto. Restituisci un unico JSON valido nello schema response_template, senza segnaposto e senza testo esterno al JSON. Non applicare le modifiche al manoscritto: prepara le proposte per la mia approvazione.');toast('Messaggio copiato. Incollalo insieme al file nella conversazione con l’AI.');});
  $('import-response').onclick=()=>{$('response-text').value='';showDialog('response-dialog');};$('choose-response-file').onclick=()=>$('response-file').click();
  $('response-file').onchange=()=>action(async()=>{const file=$('response-file').files[0];if(file){if(file.size>20_000_000)throw new Error('Risposta troppo grande.');$('response-text').value=await file.text();}$('response-file').value='';});
  $('response-form').onsubmit=e=>{e.preventDefault();action(async()=>{let text=$('response-text').value.trim();if(text.startsWith('```'))text=text.replace(/^```(?:json)?\s*\n?/,'').replace(/\n?```$/,'').trim();let response;try{response=JSON.parse(text);}catch{throw new Error('La risposta non è un JSON valido. Chiedi all’AI di rispettare il formato incluso nel pacchetto.');}const result=await api('/api/response/import',{response});await acceptState(result,false);$('response-dialog').close();filter='proposed';renderRequests();toast(`${result.imported} proposte importate${result.skipped?' · '+result.skipped+' già presenti o chiuse':''}. Il testo attende la tua approvazione.`);});};
  $('backup-btn').onclick=()=>action(async()=>{const result=await api('/api/backup',{});download(safeName(state.title)+'-progetto.json',result.project);toast('Backup completo esportato. Una copia è anche salvata sul computer.');});
  $('restore-btn').onclick=()=>$('project-file').click();$('project-file').onchange=()=>action(async()=>{const file=$('project-file').files[0];if(!file)return;if(file.size>25_000_000)throw new Error('Progetto troppo grande.');try{pendingRestore=JSON.parse(await file.text());}catch{throw new Error('File progetto JSON non valido.');}$('confirm-title').textContent='Aprire questo progetto?';$('confirm-message').textContent='Il progetto corrente viene conservato in un backup locale. Puoi anche annullare il ripristino dalla barra sotto il testo.';$('confirm-action').textContent='Apri progetto';$('confirm-action').onclick=()=>action(async()=>{await acceptState(await api('/api/project/restore',{project:pendingRestore}),true);$('confirm-dialog').close();pendingRestore=null;toast('Progetto aperto.');});showDialog('confirm-dialog');$('project-file').value='';});
  $('undo-btn').onclick=()=>action(async()=>{const result=await api('/api/undo',{});await acceptState(result,true);toast('Annullata: '+result.undone);});
  $('voice-btn').onclick=()=>action(async()=>{await refreshVoices();showDialog('voices-dialog');});
  $('auto-voice').onchange=()=>action(async()=>{stopAudio();autoVoice=$('auto-voice').checked;localStorage.setItem('bf-auto-voice',String(autoVoice));await refreshVoices();});
  $('play-btn').onclick=()=>action(togglePlay);$('previous-btn').onclick=()=>action(()=>startAudio(Math.max(0,player.index-1)));$('next-btn').onclick=()=>action(()=>startAudio(Math.min(units.length-1,player.index+1)));$('note-playing').onclick=notePlaying;
  $('speed-btn').onclick=()=>{const speeds=[.8,1,1.15,1.3,1.5];speed=speeds[(speeds.indexOf(speed)+1)%speeds.length];$('speed-btn').textContent=String(speed).replace('.',',')+'×';if(player.active)action(()=>startAudio(player.index));};
  $('focus-btn').onclick=()=>{document.body.classList.toggle('focus');$('focus-btn').setAttribute('aria-pressed',String(document.body.classList.contains('focus')));};
  $('font-btn').onclick=()=>{fontSize=fontSize>=26?18:fontSize+2;document.documentElement.style.setProperty('--reading-size',fontSize+'px');localStorage.setItem('bf-font',fontSize);};
  $('prose').ondblclick=e=>{if(e.altKey){const span=e.target.closest('.sentence');if(span)action(()=>startAudio(Number(span.dataset.index)));}};
  document.addEventListener('keydown',e=>{if(document.querySelector('dialog[open]')||/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName))return;if(e.key===' '){e.preventDefault();action(togglePlay);}else if(e.key.toLowerCase()==='n'&&player.active){e.preventDefault();notePlaying();}else if(e.key==='Escape')hideSelection();});
  document.addEventListener('visibilitychange',()=>{if(document.hidden)hideSelection();});
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>action(init),{once:true});
else action(init);
