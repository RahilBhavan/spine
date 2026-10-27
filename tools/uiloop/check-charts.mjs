// Exact chart data and scale checks, plus chart-specific rendered evidence.
import { firefox } from 'playwright';
import { createServer } from 'node:http';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
const root=path.resolve('.'), out=process.env.CHART_ARTIFACTS || path.join(process.env.HOME,'scratch/spine-graphs/charts');
await mkdir(out,{recursive:true});
const server=createServer(async(req,res)=>{
  const file=path.resolve(root,'.'+new URL(req.url,'http://localhost').pathname.replace(/\/$/,'/index.html'));
  if(!file.startsWith(root+'/')){res.writeHead(403).end();return;}
  try {res.setHeader('Content-Type',({'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json','.csv':'text/csv'})[path.extname(file)]||'application/octet-stream');res.end(await readFile(file));}catch{res.writeHead(404).end();}
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const base='http://127.0.0.1:'+server.address().port;
const ids=['chart-ltv','chart-curve','chart-liq','chart-trend','chart-heat','chart-capital','chart-warn'];
let browser;
const report=[];
async function waitChart(page,id) {
  await page.locator('#'+id).scrollIntoViewIfNeeded();
  await page.waitForFunction(id=>document.getElementById(id)?._fullLayout!=null && document.getElementById(id).querySelector('svg')!=null,id);
}
try {
  browser=await firefox.launch();
  for(const width of [390,1440])for(const theme of ['light','dark']) {
    const ctx=await browser.newContext({viewport:{width,height:900},colorScheme:theme,reducedMotion:'reduce'}),page=await ctx.newPage();
    page.setDefaultTimeout(20000);
    if(process.env.UILOOP_PLOTLY)await page.route('**/plotly-cartesian.min.js',route=>route.fulfill({path:process.env.UILOOP_PLOTLY,contentType:'text/javascript'}));
    const errors=[];page.on('pageerror',e=>errors.push(String(e)));
    await page.goto(base+'/site/');
    await page.waitForFunction(()=>document.getElementById('bt-generated-at').textContent.includes('book as of'));
    const checks=await page.evaluate(()=>{
      const m=DATA.markets.cbBTC;
      return {histogram:JSON.stringify(document.getElementById('chart-ltv').data?.[0]?.y)===JSON.stringify(m.ltv_hist.map(b=>b.borrow_usd))};
    });
    // Await lazy data after scrolling before inspecting the actual Plotly traces.
    for(const id of ids) {
      await waitChart(page,id);
      const metrics=await page.locator('#'+id).evaluate(el=>{
        const box=el.getBoundingClientRect();
        const text=[...el.querySelectorAll('svg text')].filter(t=>t.getBoundingClientRect().width>0).map(t=>({text:t.textContent,size:parseFloat(getComputedStyle(t).fontSize),x:t.getBoundingClientRect().x-box.x,y:t.getBoundingClientRect().y-box.y,w:t.getBoundingClientRect().width,h:t.getBoundingClientRect().height}));
        return {id:el.id,width:box.width,height:box.height,minText:text.length?Math.min(...text.map(t=>t.size)):null,clipped:text.filter(t=>t.x< -2||t.y< -2||t.x+t.w>box.width+2||t.y+t.h>box.height+2),text,scale:el.data?.[0]?.zmax};
      });
      assert.ok(metrics.minText==null||metrics.minText>=12,id+' has readable SVG text');
      assert.equal(metrics.clipped.length,0,id+' text remains inside the chart: '+JSON.stringify(metrics.clipped));
      if(id==='chart-ltv') {
        assert.equal(await page.evaluate(()=>JSON.stringify(document.getElementById('chart-ltv').data[0].y)===JSON.stringify(DATA.markets.cbBTC.ltv_hist.map(b=>b.borrow_usd))),true);
        assert.equal(await page.evaluate(()=>document.getElementById('chart-ltv')._fullLayout.yaxis.range[0]),0);
      }
      if(['chart-ltv','chart-liq','chart-warn'].includes(id)) {
        const factor=await page.locator('#'+id).evaluate(el=>{
          const trace=el.data[0], horizontal=trace.orientation==='h';
          const values=horizontal?trace.x:trace.y;
          const paths=[...el.querySelectorAll('.barlayer .point path')];
          const bars=values.map((v,i)=>({value:v,length:paths[i]?(horizontal?paths[i].getBBox().width:paths[i].getBBox().height):0})).filter(b=>b.value>0&&b.length>=5).sort((a,b)=>b.value-a.value);
          if(bars.length<2)return null;
          return (bars[0].length/bars[1].length)/(bars[0].value/bars[1].value);
        });
        assert.ok(factor==null||(factor>=.95&&factor<=1.05),id+' preserves bar-length ratios');
        metrics.lieFactor=factor;
      }
      if(id==='chart-heat') {
        assert.equal(await page.locator('#'+id).evaluate(el=>el.layout.annotations.length),35);
        assert.equal(await page.locator('#'+id).evaluate(el=>el.data[0].x.length),width===390?5:7);
      }
      const button=page.locator('[aria-controls="'+id+'-table"]');
      await button.focus();await page.keyboard.press('Enter');
      assert.equal(await page.locator('#'+id+'-table').isVisible(),true);
      assert.equal(await page.locator('#'+id+'-table').evaluate(el=>el.parentElement.tabIndex),0);
      await page.keyboard.press('Enter');
      await page.locator('#'+id).evaluate(el=>el.closest('.fig').scrollIntoView({block:'start'}));
      await page.locator('#'+id).evaluate(el=>el.closest('.fig').dataset.capture='true');
      if (!process.env.CHART_SKIPSHOTS) await page.locator('[data-capture="true"]').screenshot({path:path.join(out,width+'-'+theme+'-'+id+'.png')});
      await page.locator('#'+id).evaluate(el=>delete el.closest('.fig').dataset.capture);
      report.push({width,theme,...metrics});
    }
    await page.locator('#log-y').check();
    await page.waitForFunction(()=>document.getElementById('chart-ltv').data[0].type==='scatter');
    assert.equal(await page.evaluate(()=>document.getElementById('chart-ltv')._fullLayout.yaxis.type),'log');
    await page.locator('#log-y').uncheck();
    const scales=[];
    for(const scenario of ['A','AB','ABC']) {
      await page.locator('#bt-scenario-buttons [data-k="'+scenario+'"]').click();
      await page.waitForFunction(s=>document.getElementById('chart-heat-source').textContent.includes('scenario '+s),scenario);
      scales.push(await page.locator('#chart-heat').evaluate(el=>el.data[0].zmax));
    }
    assert.equal(new Set(scales).size,1,'Scenario switches preserve the same color scale');
    // Verify both rows of the matrix, including missing values, against the source lookup.
    assert.equal(await page.evaluate(()=>{
      const expected=LLTVS.map(l=>WINDOWS.map(w=>{const r=pickCap(btRows(BT,{market,window:w,lltv:l,scenario:btScenario,cex_cap_usd:BT.cexCap}));return r?badDebt(r):null;}));
      const raw=document.getElementById('chart-heat').data[0].z;
      const actual=matchMedia('(max-width:700px)').matches?expected[0].map((_,j)=>expected.map(row=>row[j])):expected;
      return JSON.stringify(raw)===JSON.stringify(actual);
    }),true);
    assert.deepEqual(errors,[]);
    console.log(JSON.stringify({width,theme,result:'passed',scales}));
    await ctx.close();
  }
  const ctx=await browser.newContext({viewport:{width:390,height:900}}),page=await ctx.newPage();
  page.setDefaultTimeout(20000);
  if(process.env.UILOOP_PLOTLY)await page.route('**/plotly-cartesian.min.js',r=>r.fulfill({path:process.env.UILOOP_PLOTLY,contentType:'text/javascript'}));
  await page.goto(base+'/site/writeup.html');
  await waitChart(page,'fig-heat');await waitChart(page,'fig-warn');
  await page.locator('#writeup-metric-buttons button').last().click();
  await page.waitForFunction(()=>document.getElementById('fig-heat-summary').textContent.includes('exposure at trough'));
  assert.equal(await page.locator('#fig-warn').evaluate(el=>el.data[0].orientation),'h');
  await page.locator('#fig-heat').evaluate(el=>el.closest('.fig').scrollIntoView());
  await page.locator('#fig-heat').evaluate(el=>el.closest('.fig').dataset.capture='true');
  if (!process.env.CHART_SKIPSHOTS) await page.locator('[data-capture="true"]').screenshot({path:path.join(out,'writeup-phone-heat.png')});
  await ctx.close();
}finally{if(browser)await browser.close();await new Promise(r=>server.close(r));await writeFile(path.join(out,'chart-metrics.json'),JSON.stringify(report,null,2));}
