// Offline, always-editable review. All source changes are handed back through the clipboard.
(() => {
  const state = editableManifest;
  const zh = document.documentElement.lang.startsWith('zh');
  const t = (cn, en) => zh ? cn : en;
  const clone = value => value === undefined ? undefined : JSON.parse(JSON.stringify(value));
  const storage = `ppt-master-edit-drafts::${state.project_id}`;
  const history = [];
  const fresh = () => ({format:2, project_id:state.project_id, base_revision:state.revision,
    counter:0, edits:{}, copies:{}, legacy_comments:[], migrated_comments:false});
  let draft, copying = false, active = null, storageOK = true;
  try { draft = JSON.parse(localStorage.getItem(storage) || 'null'); } catch (_) {}
  if (!draft || draft.project_id !== state.project_id) draft = fresh();
  if (draft.format !== 2) {
    const old = draft; draft = fresh(); draft.base_revision = old.base_revision || state.revision;
    for (const c of old.changes || []) {
      const s = state.slides.find(s => s.id === c.slide_id); if (!s) continue;
      const e = draft.edits[s.id] = {fields:{}};
      for (const [id,value] of Object.entries(c.fields || {})) {
        const f=s.fields.find(f=>f.id===id), b=old.base_values?.[s.id]?.fields?.[id];
        e.fields[id]={value,before:b?.value??f?.value??'',field:b?.field??f?.field,seq:++draft.counter};
      }
      if ('notes' in c) e.notes={value:c.notes,before:old.base_values?.[s.id]?.notes??s.notes,seq:++draft.counter};
    }
  }
  const slide = () => state.slides.find(s => s.key === entries[current].key);
  const entry = s => draft.edits[s.id] || (draft.edits[s.id]={fields:{}});
  const pendingCopy = (uid, kind, id, seq) => Object.values(draft.copies).some(c => {
    if (kind === 'comment') return !c.comments_done && c.versions.comments?.[uid] !== undefined && (seq===undefined || c.versions.comments[uid]!==seq);
    return !c.content_done && (kind==='notes' ? c.versions.notes?.[uid] : c.versions.fields?.[uid]?.[id]) !== undefined &&
      (seq===undefined || (kind==='notes' ? c.versions.notes[uid] : c.versions.fields[uid][id])!==seq);
  });
  function prune() {
    for (const [uid,e] of Object.entries(draft.edits)) {
      for (const [id,f] of Object.entries(e.fields)) if (f.value===f.before && !pendingCopy(uid,'field',id)) delete e.fields[id];
      if (e.notes && e.notes.value===e.notes.before && !pendingCopy(uid,'notes')) delete e.notes;
      if (e.comment && !e.comment.text.trim() && !pendingCopy(uid,'comment')) delete e.comment;
      if (!Object.keys(e.fields).length && !e.notes && !e.comment) delete draft.edits[uid];
    }
  }
  // Only explicit receipts clear snapshots. Edits made after copying have a newer sequence.
  for (const receipt of state.receipts || []) {
    const copied = draft.copies[receipt.packet_id]; if (!copied) continue;
    if (receipt.content_applied && !copied.content_done) {
      for (const [uid,fields] of Object.entries(copied.versions.fields)) for (const [id,seq] of Object.entries(fields)) {
        const f=draft.edits[uid]?.fields[id], s=state.slides.find(s=>s.id===uid), latest=s?.fields.find(f=>f.id===id);
        if (!f) continue;
        if (f.seq===seq) delete draft.edits[uid].fields[id];
        else if (latest && latest.field===f.field) f.before=latest.value;
      }
      for (const [uid,seq] of Object.entries(copied.versions.notes)) {
        const n=draft.edits[uid]?.notes, s=state.slides.find(s=>s.id===uid); if(!n)continue;
        if(n.seq===seq)delete draft.edits[uid].notes;else if(s?.notes_available)n.before=s.notes;
      }
      copied.content_done=true;
    }
    if (receipt.comments_processed && !copied.comments_done) {
      for (const [uid,seq] of Object.entries(copied.versions.comments)) if(draft.edits[uid]?.comment?.seq===seq)delete draft.edits[uid].comment;
      draft.legacy_comments=draft.legacy_comments.filter(c=>copied.versions.legacy?.[c.id]!==c.seq);
      copied.comments_done=true;
    }
  }
  prune();
  if (!Object.keys(draft.edits).length) draft.base_revision=state.revision;
  // Retain legacy comment-only rounds as explicitly unassigned feedback rather than guessing new slide IDs.
  if (!draft.migrated_comments) {
    try {
      const rounds=Object.keys(localStorage).filter(k=>k.startsWith(storagePrefix)).sort((a,b)=>b.localeCompare(a,undefined,{numeric:true}));
      if(rounds.length)for(const [key,text] of Object.entries(JSON.parse(localStorage.getItem(rounds[0])||'{}'))) {
        if(typeof text==='string' && text.trim())draft.legacy_comments.push({id:`legacy-${key}`,key,text,source_round:rounds[0],seq:++draft.counter});
      }
    } catch (_) {}
    draft.migrated_comments=true;
  }
  const $ = id => document.getElementById(id);
  const panel=$('commentsPanel'); panel.querySelector('.panel-title').textContent=t('修改与批注','Changes and comments');
  panel.querySelector('.panel-text').textContent=t('点击页面文字或直接修改备注；意见写在批注里。完成后复制所有修改给 Codex。','Click slide text or edit notes directly. Add comments below, then copy all changes to Codex.');
  commentBox.placeholder=t('当前页批注：例如希望怎样调整内容、结构或版式。','Comments for this slide: describe changes to content, structure or layout.');
  const oldButton=$('copyAllCommentsBtn'); oldButton.removeEventListener('click',copyAllComments);
  oldButton.id='copyAllChangesBtn'; oldButton.textContent=t('复制所有修改','Copy all changes');
  const copyButton=oldButton;
  const undo=document.createElement('button'); undo.id='undoEdit';undo.className='small-button';undo.textContent=t('撤销','Undo');copyButton.after(undo);
  saveState.id='editStatus';const status=message=>{saveState.textContent=message;};
  const warning=document.createElement('div');warning.id='editOverflow';warning.setAttribute('role','status');panel.append(warning);
  const notesInput=document.createElement('textarea');notesInput.id='editNotes';notesInput.setAttribute('aria-label',t('演讲备注 Markdown，含要点与时长','Speaker notes Markdown, including key points and duration'));
  $('notesPanel').append(notesInput);$('notesPanel').querySelector('.panel-title').textContent=t('演讲备注','Speaker notes');
  notesScript.hidden=true;notesMeta.hidden=true;
  const overlay=document.createElement('textarea');overlay.id='editOverlay';overlay.hidden=true;overlay.setAttribute('aria-label',t('修改页面文字','Edit slide text'));document.body.append(overlay);
  const manual=document.createElement('dialog');manual.id='manualCopyDialog';
  manual.innerHTML=`<p>${t('自动复制不可用。请全选下面的文字，按 Ctrl+C 或 ⌘C，再粘贴给 Codex。','Automatic copy is unavailable. Select all below, press Ctrl+C or ⌘C, then paste into Codex.')}</p><textarea id="manualCopyText" readonly aria-label="${t('所有修改记录','All changes')}"></textarea><button id="closeManualCopy">${t('关闭','Close')}</button>`;
  document.body.append(manual);$('closeManualCopy').onclick=()=>manual.close();
  function persist() {
    try { localStorage.setItem(storage,JSON.stringify(draft));storageOK=true; }
    catch (_) { storageOK=false; }
    return storageOK;
  }
  function packageData() {
    const changes=[],base_values={},feedback=[],versions={fields:{},notes:{},comments:{},legacy:{}};
    for(const [uid,e] of Object.entries(draft.edits)) {
      const s=state.slides.find(s=>s.id===uid),c={slide_id:uid,key:s?.key,title:s?.title,fields:{}},b={fields:{}};
      for(const [id,f] of Object.entries(e.fields))if(f.value!==f.before || pendingCopy(uid,'field',id,f.seq)) {
        c.fields[id]=f.value;b.fields[id]={value:f.before,field:f.field};(versions.fields[uid]??={})[id]=f.seq;
      }
      if(e.notes && (e.notes.value!==e.notes.before || pendingCopy(uid,'notes',null,e.notes.seq))) {
        c.notes=e.notes.value;b.notes=e.notes.before;versions.notes[uid]=e.notes.seq;
      }
      if(Object.keys(c.fields).length || 'notes'in c){changes.push(c);base_values[uid]=b;}
      if(e.comment?.text.trim()){feedback.push({slide_id:uid,key:s?.key,title:s?.title,text:e.comment.text});versions.comments[uid]=e.comment.seq;}
    }
    for(const c of draft.legacy_comments){feedback.push({slide_id:null,key:c.key,text:c.text,source_round:c.source_round});versions.legacy[c.id]=c.seq;}
    return {changes,base_values,comments:feedback,versions};
  }
  function updateUI(message) {
    const data=packageData();copyButton.disabled=copying || (!data.changes.length&&!data.comments.length);undo.disabled=!history.length;
    if(message)status(message);
    else if(!storageOK)status(t('浏览器暂存不可用，请及时复制所有修改。','Browser storage is unavailable. Copy all changes before leaving.'));
    else if(data.changes.length||data.comments.length)status(t('修改已暂存在此浏览器。','Changes are stored in this browser.')+(draft.base_revision!==state.revision?t(' 新草稿已更新，保留的修改会交给 Codex 核对。',' The preview has a newer revision; Codex will check retained changes.'):''));
    else status(t('可直接编辑。完成后复制所有修改给 Codex。','Edit directly, then copy all changes to Codex.'));
  }
  const valueOf=(s,f)=>draft.edits[s.id]?.fields[f.id]?.value??f.value;
  const notesOf=s=>draft.edits[s.id]?.notes?.value??s.notes;
  function remember(s,kind,id) {
    const e=draft.edits[s.id];history.push({uid:s.id,kind,id,previous:clone(kind==='field'?e?.fields[id]:e?.[kind])});
    if(history.length>100)history.shift();
  }
  function record(s,kind,id,value,rememberEdit=true) {
    if(rememberEdit)remember(s,kind,id);
    const e=entry(s),seq=++draft.counter;
    if(kind==='field') {
      const f=s.fields.find(f=>f.id===id);e.fields[id]={before:e.fields[id]?.before??f.value,field:f.field,value,seq};
    } else if(kind==='notes')e.notes={before:e.notes?.before??s.notes,value,seq};
    else e.comment={text:value,seq};
    prune();persist();updateUI();
  }
  // Keep the existing comment input and navigation, but store feedback with stable slide identities.
  saveComments=function(){record(slide(),'comment',null,commentBox.value);syncComments();};
  function syncComments(){comments={};for(const s of state.slides)comments[s.key]=draft.edits[s.id]?.comment?.text||'';updateCommentDots();}
  function setNodeText(node,value) {
    const lines=value.split('\n');node.textContent=lines[0];
    lines.slice(1).forEach(line=>{const span=node.ownerDocument.createElementNS('http://www.w3.org/2000/svg','tspan');span.setAttribute('x',node.getAttribute('x')||'0');span.setAttribute('dy','1.4em');span.textContent=line;node.append(span);});
  }
  function paint() {
    const s=slide(),doc=viewer.contentDocument;if(!s||!doc)return;
    for(const f of s.fields){const node=doc.getElementById(f.id);if(node)setNodeText(node,valueOf(s,f));}
    requestAnimationFrame(checkOverflow);
  }
  function checkOverflow() {
    const doc=viewer.contentDocument,svg=doc?.querySelector('svg');if(!svg)return;
    const box=svg.getBoundingClientRect(),items=[...doc.querySelectorAll('text')].map(n=>({n,b:n.getBoundingClientRect()}));
    let issue=items.some(({b})=>b.left<box.left-1||b.top<box.top-1||b.right>box.right+1||b.bottom>box.bottom+1);
    for(let i=0;i<items.length&&!issue;i++)for(let j=i+1;j<items.length;j++){
      const a=items[i].b,b=items[j].b;if(a.width&&b.width&&a.left<b.right-1&&a.right>b.left+1&&a.top<b.bottom-1&&a.bottom>b.top+1){issue=true;break;}
    }
    warning.textContent=issue?t('文字可能超出页面或重叠，可调整换行，或在批注里说明需要重排。','Text may overflow or overlap. Adjust line breaks or add a layout comment.'):'';
  }
  function closeOverlay(){overlay.hidden=true;active=null;}
  function openField(id) {
    const s=slide(),f=s.fields.find(f=>f.id===id),node=viewer.contentDocument?.getElementById(id);if(!f||!node)return;
    active={s,f};overlay.value=valueOf(s,f);overlay.hidden=false;
    const b=node.getBoundingClientRect(),frame=viewer.getBoundingClientRect(),scale=frame.width/Number(viewer.width),width=Math.min(innerWidth-24,Math.max(280,b.width*scale+24));
    overlay.style.width=width+'px';overlay.style.height=Math.max(80,Math.min(220,b.height*scale+32))+'px';
    overlay.style.left=Math.max(12,Math.min(innerWidth-width-12,frame.left+b.left*scale-8))+'px';
    overlay.style.top=Math.max(12,Math.min(innerHeight-240,frame.top+b.top*scale-8))+'px';
    const style=viewer.contentWindow.getComputedStyle(node);overlay.style.fontFamily=style.fontFamily;overlay.style.fontSize=Math.max(16,Math.min(32,parseFloat(style.fontSize)*scale))+'px';
    overlay.focus();overlay.select();
  }
  overlay.addEventListener('input',()=>{if(active){record(active.s,'field',active.f.id,overlay.value);paint();}});
  overlay.addEventListener('keydown',e=>{if(e.key==='Escape'||(e.key==='Enter'&&(e.metaKey||e.ctrlKey))){e.preventDefault();closeOverlay();}});
  overlay.addEventListener('blur',closeOverlay);
  notesInput.addEventListener('input',()=>record(slide(),'notes',null,notesInput.value));
  function selectEditorSlide() {
    closeOverlay();const s=slide();if(!s)return;
    notesInput.value=notesOf(s);notesInput.disabled=!s.notes_available;notesScript.hidden=true;notesMeta.hidden=true;
    syncComments();commentBox.value=comments[s.key]||'';
    viewer.setAttribute('sandbox','allow-same-origin');
    const assetBase=new URL(entries[current].href,document.baseURI).href.replace(/&/g,'&amp;').replace(/"/g,'&quot;');
    viewer.srcdoc='<!doctype html><html><head><base href="'+assetBase+'"><style>html,body{margin:0;padding:0;overflow:hidden}svg{display:block}text[data-pm-field]{cursor:text}text[data-pm-field]:hover{outline:1px dashed #9ca3af;outline-offset:4px}</style></head><body>'+s.svg_markup+'</body></html>';
  }
  viewer.addEventListener('load',()=>{const s=slide(),doc=viewer.contentDocument;if(!s||!doc)return;s.fields.forEach(f=>doc.getElementById(f.id)?.addEventListener('click',()=>openField(f.id)));paint();doc.fonts?.ready.then(checkOverflow);});
  const originalSelect=selectSlide;selectSlide=function(index){originalSelect(index);selectEditorSlide();};
  undo.onclick=()=>{
    const h=history.pop();if(!h)return;const s=state.slides.find(s=>s.id===h.uid);if(!s)return;
    const e=draft.edits[h.uid],current=h.kind==='field'?e?.fields[h.id]:e?.[h.kind];
    const value=h.previous ? (h.kind==='comment'?h.previous.text:h.previous.value) : (h.kind==='comment'?'':current?.before??(h.kind==='notes'?s.notes:s.fields.find(f=>f.id===h.id)?.value));
    record(s,h.kind,h.id,value,false);selectEditorSlide();
  };
  function uuid(){return 'r'+(globalThis.crypto?.randomUUID?.().replace(/-/g,'').slice(0,16) || Date.now().toString(36)+Math.random().toString(36).slice(2,10));}
  async function copyAllChanges() {
    if(copying)return;
    const data=packageData();if(!data.changes.length&&!data.comments.length)return;
    const packet={schema:2,kind:'ppt-master-review',packet_id:uuid(),project_id:state.project_id,
      base_revision:draft.base_revision,changes:data.changes,base_values:data.base_values,comments:data.comments};
    const fields=data.changes.reduce((n,c)=>n+Object.keys(c.fields).length,0),notes=data.changes.filter(c=>'notes'in c).length;
    const summary=t(`正文修改 ${fields} 处 · 备注修改 ${notes} 页 · 批注 ${data.comments.length} 条`,`Text edits: ${fields} · Notes: ${notes} · Comments: ${data.comments.length}`);
    copying=true;updateUI();
    let text;
    try{text=await PptReviewFormat.format(packet,state,document.querySelector('.sidebar h1').textContent,zh);}
    catch(_){copying=false;updateUI(t('修改仍保留，生成修改清单失败，请重试。','Changes are retained. Could not prepare the change list; please retry.'));return;}
    draft.copies[packet.packet_id]={versions:data.versions,content_done:false,comments_done:false};persist();copying=true;updateUI();
    let copied=false;
    try {if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(text);copied=true;}}catch(_){}
    if(!copied)try{copied=legacyCopyText(text);}catch(_){}
    copying=false;
    if(copied)updateUI(t('已复制所有修改，请粘贴给 Codex。','All changes copied. Paste into Codex.')+' '+summary+(!storageOK?t(' 浏览器暂存不可用，请保留这份文本。',' Browser storage is unavailable; retain this text.') : ''));
    else{$('manualCopyText').value=text;manual.showModal();$('manualCopyText').focus();$('manualCopyText').select();updateUI(t('请在弹窗中手动复制，修改仍然保留。','Copy manually from the dialog. Your changes are retained.'));}
  }
  copyButton.addEventListener('click',copyAllChanges);
  window.addEventListener('beforeunload',e=>{const data=packageData();if(data.changes.length||data.comments.length){persist();e.preventDefault();e.returnValue='';}});
  persist();syncComments();selectEditorSlide();updateUI();
})();
