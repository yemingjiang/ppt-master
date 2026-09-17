#!/usr/bin/env node
// OS picker/permission boundary mocked; all writes go to an isolated real fixture file.
const fs=require('fs'),os=require('os'),path=require('path'),assert=require('assert/strict');
const {execFileSync}=require('child_process'),{pathToFileURL}=require('url');
const {chromium}=require(process.env.PPT_TEST_NODE_MODULES?path.join(process.env.PPT_TEST_NODE_MODULES,'playwright'):'playwright');
const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'ppt save 中文%-')),html=path.join(tmp,'preview/index.html');
function py(code){return execFileSync('python3',['-c',code,tmp],{cwd:__dirname,encoding:'utf8'});}
const rebuild=()=>py('from pathlib import Path; import sys; from build_preview_html import render_preview; render_preview(Path(sys.argv[1]))');
let browser;
async function run(){
  py('from pathlib import Path; import sys; from test_preview_editing import fixture; from build_preview_html import render_preview; p=Path(sys.argv[1]); fixture(p); render_preview(p)');
  const manifest=JSON.parse(fs.readFileSync(path.join(tmp,'preview/editable_manifest.json'))),s=manifest.slides[0],f=s.fields[1];
  browser=await chromium.launch({channel:'chrome',headless:true});
  const context=await browser.newContext({viewport:{width:1600,height:1000}}),page=await context.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(String(e)));page.on('dialog',d=>d.accept());
  let mode='ok',writes=0,pickers=0;
  await page.exposeFunction('__read',()=>mode==='wrong'?'unrelated HTML':fs.readFileSync(html,'utf8'));
  await page.exposeFunction('__write',text=>{fs.writeFileSync(html,text);writes++;});
  await page.exposeFunction('__mode',()=>mode);
  await page.exposeFunction('__picker',()=>{pickers++;});
  await page.addInitScript(()=>{
    Object.defineProperty(navigator,'clipboard',{value:{writeText:async text=>{if(window.__copyFails)throw Error('Copy denied');window.__copied=text;}}});
    const originalExec=document.execCommand.bind(document);
    document.execCommand=(command,...args)=>{if(command!=='copy')return originalExec(command,...args);if(window.__copyFails)return false;window.__copied=document.activeElement.value;return true;};
    window.showOpenFilePicker=async options=>{
      window.__clipboardAtPicker=window.__copied;
      window.__activeAtPicker=navigator.userActivation.isActive;
      window.__pickerOptions=options;
      await window.__picker();if(await window.__mode()==='cancel')throw new DOMException('Cancelled','AbortError');
      return [{getFile:async()=>({text:()=>window.__read()}),createWritable:async()=>{
        if(await window.__mode()==='deny')throw new DOMException('Permission denied','NotAllowedError');
        let value;return {write:async text=>{value=text;if(await window.__mode()==='slow')await new Promise(resolve=>{window.__release=resolve;});},
          close:async()=>window.__write(value),abort:async()=>{}};
      }}];
    };
  });
  const url=pathToFileURL(html).href;
  await page.goto(url+'?review=test#slide=01');await page.locator('#saveHtmlBtn').waitFor();
  assert.equal(await page.locator('#copyOriginalPathBtn').count(),0,'No redundant path-copy button');

  await page.frameLocator('#viewer').locator('[id="'+f.id+'"]').click();
  await page.locator('#editOverlay').fill('已保存的正文');await page.locator('#editOverlay').press('Escape');
  const notes='正文与备注直存\n\n**重点** <script>literal</script> & <img src=x onerror=alert(1)>\n第二段';
  await page.locator('#editNotes').fill(notes);await page.locator('#commentBox').fill('仍需 Codex 调整版式');
  const before=fs.readFileSync(html,'utf8');
  for(const failure of ['cancel','wrong','deny']){
    mode=failure;await page.locator('#saveHtmlBtn').click();
    await page.waitForFunction(()=>!document.getElementById('saveHtmlBtn').disabled);
    assert.equal(fs.readFileSync(html,'utf8'),before);assert.equal(writes,0);
    assert.equal(await page.evaluate(()=>window.__clipboardAtPicker),html,'Save copies the path before opening the picker');
    assert.equal(await page.evaluate(()=>window.__activeAtPicker),true,'Picker retains user activation');
  }
  mode='ok';await page.locator('#saveHtmlBtn').click();await page.waitForFunction(()=>document.getElementById('editStatus').textContent.includes('已写回'));
  assert.equal(await page.locator('#saveFileHelp').isVisible(),false);
  const pickerOptions=await page.evaluate(()=>window.__pickerOptions);
  assert.match(pickerOptions.id,/^ppt-[A-Za-z0-9_-]{1,24}$/);
  assert.equal(pickerOptions.startIn,undefined,'Never pretend an arbitrary path is a startIn handle');
  assert.equal(writes,1);assert.ok(fs.readFileSync(html,'utf8').includes('\\u003cscript>literal'));
  assert.equal(await page.locator('#copyAllChangesBtn').textContent(),'复制批注');
  await page.evaluate(()=>window.__copied=null);
  await page.locator('#copyAllChangesBtn').click();await page.waitForFunction(()=>window.__copied);
  const copied=await page.evaluate(()=>window.__copied);
  assert.ok(copied.includes('仍需 Codex 调整版式'));assert.ok(!copied.includes('### 正文')&&!copied.includes('### 备注'));
  // A clean browser opens the saved file with edited content, without localStorage.
  const clean=await browser.newContext(),fresh=await clean.newPage();fresh.on('pageerror',e=>errors.push(String(e)));
  await fresh.goto(url);await fresh.locator('#editNotes').waitFor();
  assert.equal(await fresh.locator('#editNotes').inputValue(),notes);
  assert.equal(await fresh.frameLocator('#viewer').locator('[id="'+f.id+'"]').textContent(),'已保存的正文');
  assert.equal(await fresh.locator('#commentBox').inputValue(),''); // Comments remain local, as documented.
  await clean.close();
  // Writes during an in-flight save must remain unsaved.
  await page.evaluate(()=>window.__copied='Keep my clipboard');
  mode='slow';await page.locator('#editNotes').fill(notes+'\n保存快照');await page.locator('#saveHtmlBtn').click();
  await page.waitForFunction(()=>window.__release);await page.locator('#editNotes').fill(notes+'\n保存期间新增');
  await page.evaluate(()=>window.__release());await page.waitForFunction(()=>!document.getElementById('saveHtmlBtn').disabled);
  assert.ok((await page.locator('#editStatus').textContent()).includes('尚未保存'));
  assert.equal(await page.evaluate(()=>window.__copied),'Keep my clipboard','Reusing a file handle must not replace the clipboard');
  await page.evaluate(()=>window.__copied=null);await page.locator('#copyAllChangesBtn').click();await page.waitForFunction(()=>window.__copied);
  const unsavedCopy=await page.evaluate(()=>window.__copied);
  assert.ok(!unsavedCopy.includes('### 正文'),'Already-saved text must not be copied again');
  assert.ok(unsavedCopy.includes('保存快照') && unsavedCopy.includes('保存期间新增'),'Notes compare against the last saved HTML');
  mode='ok';await page.locator('#saveHtmlBtn').click();await page.waitForFunction(()=>document.getElementById('editStatus').textContent.includes('已写回'));
  assert.equal(pickers,4,'The granted handle is reused in this tab');
  // Automatic source import and regenerated draft preserve content and local comments.
  rebuild();assert.ok(fs.readFileSync(path.join(tmp,'main_content.md'),'utf8').includes('已保存的正文'));
  assert.ok(fs.readFileSync(path.join(tmp,'notes/total.md'),'utf8').includes('保存期间新增'));
  // A stale open tab may not overwrite a regenerated file.
  const rebuilt=fs.readFileSync(html,'utf8');await page.locator('#saveHtmlBtn').click();
  await page.waitForFunction(()=>document.getElementById('editStatus').textContent.startsWith('未保存'));
  assert.equal(fs.readFileSync(html,'utf8'),rebuilt);
  await page.reload();assert.equal(await page.locator('#editNotes').inputValue(),notes+'\n保存期间新增');
  assert.equal(await page.locator('#commentBox').inputValue(),'仍需 Codex 调整版式');
  assert.equal(await page.locator('#copyAllChangesBtn').textContent(),'复制批注');
  const countBeforeFailure=pickers;
  await page.evaluate(()=>{window.__copyFails=true;window.__copied='unchanged';});
  await page.locator('#saveHtmlBtn').click();
  await page.waitForFunction(()=>document.getElementById('editStatus').textContent.includes('自动复制不可用'));
  assert.equal(pickers,countBeforeFailure,'Do not open the picker with stale clipboard after copy failure');
  assert.equal(await page.locator('#originalFilePath').inputValue(),html);
  assert.equal(await page.locator('#originalFilePath').isVisible(),true);
  await page.evaluate(()=>window.__copied=document.getElementById('originalFilePath').value);
  mode='cancel';await page.locator('#saveHtmlBtn').click();await page.waitForFunction(()=>!document.getElementById('saveHtmlBtn').disabled);
  assert.equal(pickers,countBeforeFailure+1,'Manual copy followed by another save still opens the picker');
  const reopened=await browser.newContext(),reopenedPage=await reopened.newPage();
  await reopenedPage.goto(url);await reopenedPage.locator('#editNotes').waitFor();
  assert.equal(await reopenedPage.locator('#editNotes').inputValue(),notes+'\n保存期间新增','Saved literal HTML must also survive source regeneration');
  await reopened.close();
  assert.deepEqual(errors,[]);console.log('PASS: authorized-save boundary, recovery, comments, concurrent edits, stale-file rejection and source round trip');
}
run().catch(e=>{console.error(e);process.exitCode=1;}).finally(async()=>{await browser?.close();fs.rmSync(tmp,{recursive:true,force:true});});
