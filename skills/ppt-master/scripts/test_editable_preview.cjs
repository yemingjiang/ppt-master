#!/usr/bin/env node
/* Offline browser regression. Uses isolated fixtures and a mock clipboard. */
const fs=require('fs'),os=require('os'),path=require('path'),assert=require('assert/strict');
const {execFileSync}=require('child_process');
const {pathToFileURL}=require('url');
const args=process.argv.slice(2);
if(args.includes('--help')){console.log('Usage: node test_editable_preview.cjs [--python python3] [--node-modules /path/to/node_modules] [--screenshots /path/to/qa]\nRuns isolated offline editing, clipboard and processing-receipt checks.');process.exit(0);}
function arg(name,fallback){const i=args.indexOf(name);return i<0?fallback:args[i+1];}
const python=arg('--python','python3'),modules=arg('--node-modules',null),shots=arg('--screenshots',null);
const {chromium}=require(modules?path.join(modules,'playwright'):'playwright');
const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'ppt-edit-test-'));
let browser;
function pythonRun(code,...extra){return execFileSync(python,['-c',code,...extra],{cwd:__dirname,encoding:'utf8'});}
function processCopy(command,text,...flags){return JSON.parse(execFileSync(python,[path.join(__dirname,'edit_preview.py'),command,tmp,'--stdin','--json',...flags],{input:text,encoding:'utf8'}));}
function payload(text){
  return JSON.parse(execFileSync(python,['-c','import json, sys; from pathlib import Path; from review_packets import parse_packet; print(json.dumps(parse_packet(sys.stdin.read(), Path(sys.argv[1])), ensure_ascii=False))',tmp],{cwd:__dirname,input:text,encoding:'utf8'}));
}
async function editField(page,id,value){
  await page.frameLocator('#viewer').locator('[id="'+id+'"]').click();
  await page.locator('#editOverlay').fill(value);
  await page.locator('#editOverlay').press('Escape');
}
async function copyAll(page){
  await page.evaluate(()=>window.__copied=null);
  await page.locator('#copyAllChangesBtn').click();
  await page.waitForFunction(()=>window.__copied!==null);
  return page.evaluate(()=>window.__copied);
}
async function main(){
  pythonRun('from pathlib import Path; import sys; from test_preview_editing import fixture; from build_preview_html import render_preview; p=Path(sys.argv[1]); fixture(p); render_preview(p)',tmp);
  fs.mkdirSync(path.join(tmp,'images'));
  fs.writeFileSync(path.join(tmp,'images/asset.svg'),'<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80"><rect width="80" height="80" fill="#2563eb"/></svg>');
  const svgPath=path.join(tmp,'svg_output/01_开场.svg');
  fs.writeFileSync(svgPath,fs.readFileSync(svgPath,'utf8').replace('</svg>','<image href="../images/asset.svg" x="1100" y="40" width="80" height="80"/></svg>'));
  pythonRun('from pathlib import Path; import sys; from build_preview_html import render_preview; render_preview(Path(sys.argv[1]))',tmp);
  const manifest=JSON.parse(fs.readFileSync(path.join(tmp,'preview/editable_manifest.json'),'utf8'));
  const field=manifest.slides[0].fields[1],id=field.id,uid=manifest.slides[0].id;
  browser=await chromium.launch({channel:'chrome',headless:true});
  const context=await browser.newContext({viewport:{width:1600,height:1000}});
  // Never touch the user's clipboard or start a server.
  await context.addInitScript(()=>Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async text=>{window.__copied=text;}}}));
  const page=await context.newPage(),errors=[],network=[],downloads=[];
  page.on('pageerror',e=>errors.push(String(e)));page.on('dialog',d=>d.accept());
  context.on('request',r=>{if(/^https?:/.test(r.url()))network.push(r.url());});
  page.on('download',d=>downloads.push(d.suggestedFilename()));
  const url=pathToFileURL(path.join(tmp,'preview/index.html')).href;
  await page.goto(url);
  await page.locator('#copyAllChangesBtn').waitFor();
  await page.frameLocator('#viewer').locator('image').waitFor();
  const assetLoaded=await page.evaluate(()=>new Promise(resolve=>{
    const node=document.getElementById('viewer').contentDocument.querySelector('image'),probe=new Image();
    const timer=setTimeout(()=>resolve(false),5000);
    probe.onload=()=>{clearTimeout(timer);resolve(true);};probe.onerror=()=>{clearTimeout(timer);resolve(false);};
    probe.src=new URL(node.getAttribute('href'),node.baseURI).href;
  }));
  assert.equal(assetLoaded,true,'Relative SVG assets should load in the editable frame');
  assert.equal(await page.locator('#editToggle,#saveEdits,#exportEdits,#compareEdits').count(),0);
  assert.equal(await page.locator('#copyAllChangesBtn').isDisabled(),true);
  assert.equal(await page.locator('#editNotes').isEnabled(),true);
  await editField(page,id,'越要说清标准。');
  const notes='新的演讲备注。\n\n第二段 **重点** 与 [链接](https://example.org)。\n\n要点：① 标准 ② 责任\n\n时长：1分20秒';
  await page.locator('#editNotes').fill(notes);
  await page.locator('#editNotes').press('ArrowRight');
  assert.equal(new URL(page.url()).hash,'#slide=01');
  await page.locator('#commentBox').fill('请把这页标题再精简一点。');
  const first=await copyAll(page),p1=payload(first);
  assert.ok(first.startsWith('# PPT 修改清单'));
  assert.ok(!first.includes('```json')&&!first.includes('base_values')&&!first.includes(manifest.project_id));
  assert.equal(p1.changes[0].fields[id],'越要说清标准。');
  assert.equal(p1.changes[0].notes,notes);
  assert.equal(p1.base_values[uid].fields[id].value,field.value);
  assert.equal(p1.base_values[uid].fields[id].field,field.field);
  assert.equal(p1.comments[0].text,'请把这页标题再精简一点。');
  assert.equal(await page.locator('#copyAllChangesBtn').isEnabled(),true);
  await page.reload();
  assert.equal(await page.frameLocator('#viewer').locator('[id="'+id+'"]').textContent(),'越要说清标准。');
  assert.equal(await page.locator('#editNotes').inputValue(),notes);
  assert.equal(await page.locator('#commentBox').inputValue(),p1.comments[0].text);
  // A post-copy revert to the old wording must survive application of the first copy.
  await editField(page,id,field.value);
  const laterNotes=notes+'\n\n复制后补充的讲述。';
  await page.locator('#editNotes').fill(laterNotes);
  await page.locator('#commentBox').fill('复制之后新补充的批注。');
  assert.equal(processCopy('inspect',first).comments_pending.length,1);
  processCopy('apply',first,'--dry-run');
  assert.ok(!fs.readFileSync(path.join(tmp,'main_content.md'),'utf8').includes('越要说清标准。'));
  processCopy('apply',first);
  assert.ok(fs.readFileSync(path.join(tmp,'main_content.md'),'utf8').includes('越要说清标准。'));
  await page.reload();
  assert.equal(await page.frameLocator('#viewer').locator('[id="'+id+'"]').textContent(),field.value);
  assert.equal(await page.locator('#editNotes').inputValue(),laterNotes);
  assert.equal(await page.locator('#commentBox').inputValue(),'复制之后新补充的批注。');
  processCopy('ack',first,'--comments-processed');
  await page.reload();
  assert.equal(await page.locator('#commentBox').inputValue(),'复制之后新补充的批注。');
  const second=await copyAll(page),p2=payload(second);
  assert.equal(p2.changes[0].fields[id],field.value);
  assert.equal(p2.base_values[uid].fields[id].value,'越要说清标准。');
  assert.equal(p2.base_values[uid].notes,notes);
  processCopy('apply',second);processCopy('ack',second,'--comments-processed');
  await page.reload();
  assert.equal(await page.locator('#copyAllChangesBtn').isDisabled(),true);
  assert.equal(await page.locator('#commentBox').inputValue(),'');
  assert.equal(await page.locator('#editNotes').inputValue(),laterNotes);
  assert.equal(await page.frameLocator('#viewer').locator('[id="'+id+'"]').textContent(),field.value);
  // An older processed record cannot restore superseded wording.
  assert.equal(processCopy('apply',first).already_processed,true);
  await page.reload();assert.equal(await page.locator('#copyAllChangesBtn').isDisabled(),true);
  assert.ok(fs.readFileSync(path.join(tmp,'main_content.md'),'utf8').includes(field.value));
  // Comment-only records copy and remain pending until explicitly processed.
  await page.locator('#commentBox').fill('只有一条版式批注。');
  const third=await copyAll(page);assert.equal(payload(third).changes.length,0);
  processCopy('apply',third);await page.reload();
  assert.equal(await page.locator('#commentBox').inputValue(),'只有一条版式批注。');
  assert.equal(await page.locator('#copyAllChangesBtn').isEnabled(),true);
  processCopy('ack',third,'--comments-processed');await page.reload();
  assert.equal(await page.locator('#commentBox').inputValue(),'');
  assert.equal(await page.locator('#copyAllChangesBtn').isDisabled(),true);
  // Overflow and undo preserve source files; text cursor keys do not turn pages.
  await editField(page,id,'这是一段很长的文字'.repeat(20));
  await page.waitForFunction(()=>document.getElementById('editOverflow').textContent.length>0);
  await page.locator('#undoEdit').click();
  await page.waitForFunction(()=>document.getElementById('viewer').contentDocument?.querySelector('svg'));
  assert.equal(await page.frameLocator('#viewer').locator('[id="'+id+'"]').textContent(),field.value);
  assert.equal(await page.locator('#copyAllChangesBtn').isDisabled(),true);
  await page.frameLocator('#viewer').locator('[id="'+id+'"]').click();
  await page.locator('#editOverlay').press('ArrowRight');
  assert.equal(new URL(page.url()).hash,'#slide=01');
  await page.locator('#editOverlay').press('Escape');
  await page.locator('#nextBtn').click();assert.equal(new URL(page.url()).hash,'#slide=02');
  await page.locator('#prevBtn').click();
  if(shots){fs.mkdirSync(shots,{recursive:true});await page.screenshot({path:path.join(shots,'editable-desktop.png')});}
  // Manual fallback shows the entire payload and leaves drafts intact.
  await page.evaluate(()=>{navigator.clipboard.writeText=async()=>{throw Error('test clipboard denial');};document.execCommand=()=>false;});
  await page.locator('#commentBox').fill('手动复制也包括批注。');
  await page.locator('#copyAllChangesBtn').click();
  await page.locator('#manualCopyDialog').waitFor();
  const manual=await page.locator('#manualCopyText').inputValue();
  assert.equal(payload(manual).comments[0].text,'手动复制也包括批注。');
  assert.equal(await page.locator('#manualCopyText').evaluate(n=>n.selectionEnd-n.selectionStart),manual.length);
  await page.locator('#closeManualCopy').click();
  assert.equal(await page.locator('#commentBox').inputValue(),'手动复制也包括批注。');
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  if(shots)await page.screenshot({path:path.join(shots,'editable-mobile.png'),fullPage:true});
  // Storage denial must warn, while still allowing immediate copying.
  const privateContext=await browser.newContext();
  await privateContext.addInitScript(()=>{
    Storage.prototype.setItem=()=>{throw Error('test storage denial');};
    Object.defineProperty(navigator,'clipboard',{value:{writeText:async text=>{window.__copied=text;}}});
  });
  const privatePage=await privateContext.newPage();privatePage.on('dialog',d=>d.accept());privatePage.on('pageerror',e=>errors.push(String(e)));
  await privatePage.goto(url);await privatePage.locator('#commentBox').fill('浏览器不能暂存。');
  assert.match(await privatePage.locator('#editStatus').textContent(),/暂存不可用/);
  assert.equal(payload(await copyAll(privatePage)).comments[0].text,'浏览器不能暂存。');
  await privateContext.close();
  assert.deepEqual(errors,[]);assert.deepEqual(network,[]);assert.deepEqual(downloads,[]);
  console.log(JSON.stringify({status:'ok',offline:true,defaultEditable:true,combinedClipboard:true,commentOnly:true,draftRecovery:true,postCopyRevert:true,processingReceipts:true,retrySafe:true,undo:true,keyboard:true,overflowWarning:true,manualCopyFallback:true,storageFailure:true,mobile:true,pageErrors:errors}));
}
main().catch(e=>{console.error(e);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();fs.rmSync(tmp,{recursive:true,force:true});});
