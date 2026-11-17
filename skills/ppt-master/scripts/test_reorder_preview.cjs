#!/usr/bin/env node
// Real offline pointer/keyboard interaction, isolated project and mock clipboard/file picker.
const fs=require('fs'),os=require('os'),path=require('path'),assert=require('assert/strict');
const {execFileSync}=require('child_process'),{pathToFileURL}=require('url');
const {chromium}=require(process.env.PPT_TEST_NODE_MODULES?path.join(process.env.PPT_TEST_NODE_MODULES,'playwright'):'playwright');
const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'ppt-order-')),html=path.join(tmp,'preview/index.html');
const py=code=>execFileSync('python3',['-c',code,tmp],{cwd:__dirname,encoding:'utf8'});
const rebuild=()=>py('from pathlib import Path; import sys; from build_preview_html import render_preview; render_preview(Path(sys.argv[1]))');
const processCopy=(command,text,...flags)=>JSON.parse(execFileSync('python3',[path.join(__dirname,'edit_preview.py'),command,tmp,'--stdin','--json',...flags],{input:text,encoding:'utf8'}));
let browser;
async function main(){
  py('from pathlib import Path; import sys; from test_preview_editing import fixture; from build_preview_html import render_preview; p=Path(sys.argv[1]); fixture(p); render_preview(p)');
  const m=JSON.parse(fs.readFileSync(path.join(tmp,'preview/editable_manifest.json'))),ids=m.slides.map(s=>s.id),url=pathToFileURL(html).href;
  browser=await chromium.launch({channel:'chrome',headless:true});
  const context=await browser.newContext({viewport:{width:1600,height:1000}}),page=await context.newPage(),errors=[],network=[];
  context.on('request',r=>{if(/^https?:/.test(r.url()))network.push(r.url());});
  page.on('pageerror',e=>errors.push(String(e)));page.on('dialog',d=>d.accept());
  await context.addInitScript(()=>Object.defineProperty(navigator,'clipboard',{value:{writeText:async text=>{window.__copied=text;}}}));
  const order=()=>page.locator('.slide-link').evaluateAll(rows=>rows.map(r=>r.dataset.slideId));
  const copy=async()=>{await page.evaluate(()=>window.__copied=null);await page.locator('#copyAllChangesBtn').click();await page.waitForFunction(()=>window.__copied);return page.evaluate(()=>window.__copied);};
  async function moveUp(){const handle=page.locator('.order-handle').nth(1);await handle.focus();await handle.press('Alt+ArrowUp');}
  await page.goto(url);await page.locator('.order-handle').first().waitFor();
  await page.locator('#commentBox').fill('第一页的批注随页面移动');
  await page.locator('#editNotes').fill('第一页重排前编辑的备注');
  const from=await page.locator('.order-handle').nth(1).boundingBox(),to=await page.locator('.slide-link').first().boundingBox();
  await page.mouse.move(from.x+from.width/2,from.y+from.height/2);await page.mouse.down();
  await page.mouse.move(to.x+to.width/2,to.y+5,{steps:12});await page.mouse.up();
  assert.deepEqual(await order(),ids.toReversed(),'Pointer drag moves the page');
  assert.equal(await page.locator('.slide-link.active').getAttribute('data-slide-id'),ids[0],'The current page stays selected');
  assert.deepEqual(await page.locator('.slide-no').allTextContents(),['01','02']);
  assert.equal(await page.locator('#editNotes').inputValue(),'第一页重排前编辑的备注');
  await page.locator('#undoEdit').click();assert.deepEqual(await order(),ids);
  await moveUp();assert.deepEqual(await order(),ids.toReversed(),'Keyboard sorting uses the same change record');
  await page.reload();await page.locator('.order-handle').first().waitFor();assert.deepEqual(await order(),ids.toReversed());
  const copied=await copy();assert.ok(copied.includes('## 全局修改：页面顺序'));assert.ok(copied.includes('新顺序：s2 → s1'));
  assert.ok(processCopy('inspect',copied).pending_order);
  // Restore the original order AFTER copying. The first receipt must not discard this newer action.
  await moveUp();assert.deepEqual(await order(),ids);
  processCopy('apply',copied,'--dry-run');assert.equal(fs.existsSync(path.join(tmp,'svg_output/01_开场.svg')),true);
  processCopy('apply',copied);await page.reload();await page.locator('.order-handle').first().waitFor();
  assert.deepEqual(await order(),ids,'A post-copy revert survives the first apply/rebuild');
  await page.locator('.slide-link').first().click();
  assert.equal(await page.locator('#commentBox').inputValue(),'第一页的批注随页面移动');
  assert.equal(await page.locator('#editNotes').inputValue(),'第一页重排前编辑的备注');
  const second=await copy();assert.ok(second.includes('新顺序：s1 → s2'));processCopy('apply',second);processCopy('ack',second,'--comments-processed');
  await page.reload();await page.locator('.order-handle').first().waitFor();assert.deepEqual(await order(),ids);
  assert.equal(await page.locator('#copyAllChangesBtn').isDisabled(),true);
  // Persist order to the authorized HTML and open it with no browser draft storage.
  await page.exposeFunction('__readHtml',()=>fs.readFileSync(html,'utf8'));
  await page.exposeFunction('__writeHtml',text=>fs.writeFileSync(html,text));
  await page.evaluate(()=>{window.showOpenFilePicker=async()=>[{getFile:async()=>({text:()=>window.__readHtml()}),createWritable:async()=>{let value;return {write:async text=>{value=text;},close:async()=>window.__writeHtml(value),abort:async()=>{}};}}];});
  // API detection occurs at startup, so install mocks for the next load too.
  await page.addInitScript(()=>{window.showOpenFilePicker=async()=>[{getFile:async()=>({text:()=>window.__readHtml()}),createWritable:async()=>{let value;return {write:async text=>{value=text;},close:async()=>window.__writeHtml(value),abort:async()=>{}};}}];document.addEventListener('DOMContentLoaded',()=>{document.execCommand=()=>true;});});
  await page.reload();await page.locator('.order-handle').first().waitFor();await moveUp();
  await page.locator('#saveHtmlBtn').click();await page.waitForFunction(()=>document.getElementById('editStatus').textContent.includes('已写回'));
  const freshContext=await browser.newContext(),fresh=await freshContext.newPage();fresh.on('pageerror',e=>errors.push(String(e)));
  await fresh.goto(url);await fresh.locator('.order-handle').first().waitFor();
  assert.deepEqual(await fresh.locator('.slide-link').evaluateAll(rows=>rows.map(r=>r.dataset.slideId)),ids.toReversed());
  await freshContext.close();rebuild();
  assert.deepEqual(JSON.parse(fs.readFileSync(path.join(tmp,'preview/editable_manifest.json'))).slides.map(s=>s.id),ids.toReversed());
  await page.reload();await page.locator('.order-handle').first().waitFor();assert.deepEqual(await order(),ids.toReversed());
  assert.equal(await page.locator('#copyAllChangesBtn').isDisabled(),true,'Saved ordering receipts clear only the applied snapshot');
  if(process.env.PPT_TEST_SCREENSHOT)await page.screenshot({path:process.env.PPT_TEST_SCREENSHOT,fullPage:true});
  await page.setViewportSize({width:390,height:844});assert.equal(await page.locator('.order-handle').first().isVisible(),true);
  // A long outline scrolls during dragging and Escape cancels the in-flight move.
  py(`from pathlib import Path
import sys
from test_preview_editing import fixture
from preview_editing import MAIN_BLOCK
from build_preview_html import render_preview
p=Path(sys.argv[1])/'long'; fixture(p)
main=p/'main_content.md'; block=list(MAIN_BLOCK.finditer(main.read_text()))[-1][0]
svg=(p/'svg_output/02_下一页.svg').read_text()
for i in range(3,26):
    key=str(i).zfill(2); title='页面'+key
    main.write_text(main.read_text()+'\\n'+block.replace('Slide 02','Slide '+key).replace('下一页',title))
    (p/('svg_output/'+key+'_page.svg')).write_text(svg.replace('下一页',title))
render_preview(p)`);
  await page.setViewportSize({width:1600,height:1000});await page.goto(pathToFileURL(path.join(tmp,'long/preview/index.html')).href);
  await page.locator('.order-handle').first().waitFor();
  const first=await page.locator('.order-handle').first().boundingBox(),nav=await page.locator('.nav').boundingBox();
  await page.mouse.move(first.x+first.width/2,first.y+first.height/2);await page.mouse.down();
  await page.mouse.move(first.x+first.width/2,nav.y+nav.height-6,{steps:15});
  await page.waitForFunction(()=>document.querySelector('.nav').scrollTop>100);
  await page.keyboard.press('Escape');await page.mouse.up();
  assert.equal(await page.locator('#copyAllChangesBtn').isDisabled(),true,'Cancelled drag makes no change');
  // Page activation and Previous/Next continue to use the reordered dynamic indexes.
  await page.locator('.slide-link').nth(24).click();await page.locator('#prevBtn').click();
  assert.equal(await page.locator('.slide-link.active .slide-no').textContent(),'24');
  assert.deepEqual(errors,[]);assert.deepEqual(network,[]);
  console.log('PASS: pointer drag, numbering, selection, keyboard, undo, reload, global copy, post-copy revert, receipts, saved-file recovery and offline source round trip');
}
main().catch(e=>{console.error(e);process.exitCode=1;}).finally(async()=>{await browser?.close();fs.rmSync(tmp,{recursive:true,force:true});});
