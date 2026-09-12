// Human-readable clipboard format. Complete identities and note baselines stay in the project.
const PptReviewFormat = (() => {
  const quote = text => text.split('\n').map(line => '> ' + line).join('\n');
  const value = (label,text) => text.includes('\n') || !text ? label+'\n'+quote(text) : label+text;
  const oneLine = text => (text || '').replace(/[\r\n]+/g,' ');
  const lines = text => text ? text.split('\n') : [];
  function diff(before,after,context=1) {
    const a=lines(before),b=lines(after),ops=[];
    let prefix=0,suffix=0;
    while(prefix<a.length && prefix<b.length && a[prefix]===b[prefix])prefix++;
    while(suffix<a.length-prefix && suffix<b.length-prefix && a[a.length-1-suffix]===b[b.length-1-suffix])suffix++;
    const x=a.slice(prefix,a.length-suffix),y=b.slice(prefix,b.length-suffix);
    for(const text of a.slice(0,prefix))ops.push([' ',text]);
    // Bound memory for unusually large notes; common prefix/suffix still avoid full duplication.
    if((x.length+1)*(y.length+1)>1000000) {
      x.forEach(text=>ops.push(['-',text]));y.forEach(text=>ops.push(['+',text]));
    } else {
      const width=y.length+1,dp=new Uint32Array((x.length+1)*width);
      for(let i=x.length-1;i>=0;i--)for(let j=y.length-1;j>=0;j--)
        dp[i*width+j]=x[i]===y[j] ? dp[(i+1)*width+j+1]+1 : Math.max(dp[(i+1)*width+j],dp[i*width+j+1]);
      let i=0,j=0;
      while(i<x.length || j<y.length) {
        if(i<x.length && j<y.length && x[i]===y[j]){ops.push([' ',x[i]]);i++;j++;}
        else if(i<x.length && (j===y.length || dp[(i+1)*width+j]>=dp[i*width+j+1]))ops.push(['-',x[i++]]);
        else ops.push(['+',y[j++]]);
      }
    }
    for(const text of a.slice(a.length-suffix))if(suffix)ops.push([' ',text]);
    const ranges=[];
    ops.forEach(([kind],i)=>{if(kind===' ')return;const start=Math.max(0,i-context),end=Math.min(ops.length,i+context+1),last=ranges.at(-1);
      if(last && start<=last[1])last[1]=end;else ranges.push([start,end]);});
    const oldPos=[0],newPos=[0];
    ops.forEach(([kind],i)=>{oldPos.push(oldPos[i]+(kind!=='+'?1:0));newPos.push(newPos[i]+(kind!=='-'?1:0));});
    return ranges.map(([start,end])=>{
      const oldCount=oldPos[end]-oldPos[start],newCount=newPos[end]-newPos[start];
      return `@@ -${oldPos[start]+(oldCount?1:0)},${oldCount} +${newPos[start]+(newCount?1:0)},${newCount} @@\n`+
        ops.slice(start,end).map(([kind,text])=>kind+text).join('\n');
    }).join('\n');
  }
  async function hash(text) {
    if(!globalThis.crypto?.subtle)return null;
    const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text));
    return Array.from(new Uint8Array(bytes),b=>b.toString(16).padStart(2,'0')).join('');
  }
  async function format(packet,state,projectName,zh=true) {
    const t=(cn,en)=>zh?cn:en,review=state.review;
    const out=[t('# PPT 修改清单','# PPT Change List'),'',
      t('项目：','Project: ')+oneLine(projectName)+` [${review.project_ref}]`,
      t('版本：','Version: ')+review.version_ref+'｜'+t('修改记录：','Record: ')+packet.packet_id];
    const pages=new Map();
    function page(uid,key,title) {
      const mapKey=uid||'legacy-'+key;
      if(!pages.has(mapKey))pages.set(mapKey,{uid,key,title,fields:{},comments:[]});
      return pages.get(mapKey);
    }
    for(const c of packet.changes)Object.assign(page(c.slide_id,c.key,c.title),{fields:c.fields,notes:c.notes,hasNotes:'notes'in c});
    for(const c of packet.comments)page(c.slide_id,c.key,c.title).comments.push(c.text);
    const order=new Map(state.slides.map((s,i)=>[s.id,i]));
    for(const p of [...pages.values()].sort((a,b)=>(order.get(a.uid)??Infinity)-(order.get(b.uid)??Infinity))) {
      const identity=review.slides[p.uid],slide=state.slides.find(s=>s.id===p.uid);
      const ref=p.uid ? identity?.ref||'S:'+encodeURIComponent(p.uid) : 'legacy';
      out.push('',`## ${p.key||slide?.key||'?'} ${oneLine(p.title||slide?.title||t('待确认页面','Unassigned slide'))} [${ref}]`);
      const baseline=packet.base_values[p.uid];
      for(const [id,after] of Object.entries(p.fields)) {
        const before=baseline.fields[id],version=review.field_versions[p.uid]?.[id]?.[before.field];
        const short=identity?.fields[id];
        const ref=short && version ? short+(version===review.version_ref?'':'@'+version) : 'T:'+encodeURIComponent(id)+';F:'+encodeURIComponent(before.field);
        out.push('',t('### 正文','### Text')+` [${ref}]`,value(t('原：','Before: '),before.value),value(t('改：','After: '),after));
      }
      if(p.hasNotes) {
        const before=baseline.notes,noteHash=await hash(before),version=noteHash && review.note_versions[p.uid]?.[noteHash];
        if(!version)out.push('',t('### 备注替换','### Notes replacement'),value(t('原：','Before: '),before),value(t('改：','After: '),p.notes));
        else {
          const patch=diff(before,p.notes),suffix=version===review.version_ref?'':` [${version}]`;
          // Entire rewrites carry the new text once; the original remains in the version archive.
          if(!patch || patch.length>p.notes.length*1.25+120)out.push('',t('### 备注全文','### Full notes')+suffix,quote(p.notes));
          else out.push('',t('### 备注修改','### Notes changes')+suffix,'```diff',patch,'```');
        }
      }
      if(p.comments.length)out.push('',t('### 批注','### Comment'),quote(p.comments.join('\n\n')));
    }
    return out.join('\n');
  }
  return {format,diff};
})();
if(typeof module!=='undefined')module.exports=PptReviewFormat;
