import fs from 'node:fs';
import {chromium} from 'playwright';
import lighthouse from 'lighthouse';
import * as chromeLauncher from 'chrome-launcher';
const base='https://duhoc.thompbui.com/';
const urls=[base,base+'bai-viet-visa-d4-va-d2/',base+'chuyen-muc/seoul/'];
fs.mkdirSync('site-diagnostics',{recursive:true});
const data={measured:new Date().toISOString(),results:[]};
const chrome=await chromeLauncher.launch({chromePath:chromium.executablePath(),chromeFlags:['--headless','--no-sandbox','--disable-dev-shm-usage','--disable-gpu']});
try{
  for(const url of urls){
    const item={url};
    try{
      const r=await lighthouse(url,{port:chrome.port,output:'json',logLevel:'error',onlyCategories:['performance','accessibility','best-practices','seo'],maxWaitForLoad:45000});
      const l=r.lhr;
      item.scores=Object.fromEntries(Object.entries(l.categories).map(([k,v])=>[k,Math.round(v.score*100)]));
      item.categoryAuditDetails={};
      for(const [cat,obj]of Object.entries(l.categories)){
        item.categoryAuditDetails[cat]=obj.auditRefs
          .filter(ref=>ref.weight>0)
          .map(ref=>l.audits[ref.id])
          .filter(a=>a && a.score!==null && a.score<1)
          .map(a=>({id:a.id,title:a.title,description:a.description,score:a.score,displayValue:a.displayValue,items:a.details?.items?.slice(0,4).map(x=>JSON.stringify(x).slice(0,350))||[]}));
      }
      item.lcpDetails={lcpElement:l.audits['largest-contentful-paint-element']?.details?.items?.slice(0,2),lcpPhases:l.audits['lcp-breakdown-insight']?.details?.items?.slice(0,2)};
    }catch(e){item.lighthouseError=e.message;}
    try{
      const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
      const context=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
      await context.addInitScript(()=>{
        window.__layoutShifts=[];
        new PerformanceObserver(list=>{for(const entry of list.getEntries())if(!entry.hadRecentInput)window.__layoutShifts.push({value:entry.value,sources:(entry.sources||[]).slice(0,5).map(s=>({oldRect:s.previousRect,newRect:s.currentRect,node:s.node?.outerHTML?.slice(0,240)||null}))});}).observe({type:'layout-shift',buffered:true});
      });
      const page=await context.newPage();
      await page.goto(url,{waitUntil:'domcontentloaded',timeout:35000});
      await page.waitForTimeout(5500);
      item.layoutShifts=await page.evaluate(()=>window.__layoutShifts||[]);
      await browser.close();
    }catch(e){item.playwrightError=e.message;}
    data.results.push(item);
    console.log('DIAG_RESULT',JSON.stringify(item).slice(0,20000));
    fs.writeFileSync('site-diagnostics/diagnostics.json',JSON.stringify(data,null,2));
  }
}finally{await chrome.kill();}
