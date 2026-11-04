import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { chromium } from 'playwright';

const out = process.env.AUDIT_DIR || 'site-audit-out';
const home = (process.env.AUDIT_URL || '').trim();
const mode = process.env.AUDIT_MODE || 'discover';
fs.mkdirSync(out, { recursive: true });
const u = new URL(home);
if (u.protocol !== 'https:' || !/^duhoc\.thompbui\.com$/i.test(u.hostname)) throw Error('Audit origin must be https://duhoc.thompbui.com/');
const origin = u.origin;
const sleep = ms => new Promise(r => setTimeout(r, ms));
const sha = v => crypto.createHash('sha1').update(v).digest('hex').slice(0,8);
const slug = url => {
  const p = new URL(url).pathname.replace(/^\/|\/$/g,'').replace(/[^a-zA-Z0-9-]/g,'-').replace(/-+/g,'-');
  return (p || 'home').slice(0,50) + '-' + sha(url);
};
const write = (name, obj) => fs.writeFileSync(path.join(out,name), JSON.stringify(obj,null,2));
async function launch() {
  return chromium.launch({ headless:true, args:['--no-sandbox','--disable-dev-shm-usage'] });
}
function normalize(raw) {
  try {
    const a = new URL(raw, home);
    if (a.origin !== origin || !/^https?:$/.test(a.protocol)) return null;
    a.hash = '';
    a.search = '';
    a.pathname = a.pathname.replace(/\/+/g,'/');
    return a.href;
  } catch { return null; }
}
async function discover() {
  const browser = await launch();
  const pages = [];
  const error = [];
  for (const device of ['desktop','mobile']) {
    const context = await browser.newContext({
      viewport: device==='mobile'?{width:390,height:844}:{width:1440,height:900},
      isMobile:device==='mobile', hasTouch:device==='mobile'
    });
    const page = await context.newPage();
    try {
      const response = await page.goto(home,{waitUntil:'domcontentloaded',timeout:45000});
      await page.waitForTimeout(1500);
      const anchors = await page.locator('header a[href], nav a[href], [role="navigation"] a[href], [class*="menu"] a[href]').evaluateAll(nodes=>
        nodes.map(a=>({
          text:(a.innerText||a.getAttribute('aria-label')||a.title||'').trim().replace(/\s+/g,' ').slice(0,100),
          url:a.href,
          menu:!!a.closest('nav,[role="navigation"],[class*="menu"],[id*="menu"]')
        })).filter(x=>x.menu)
      );
      pages.push(...anchors.map(x=>({...x, device})));
      fs.writeFileSync(path.join(out,'menu-'+device+'.json'),JSON.stringify({status:response?.status(),title:await page.title(),anchors},null,2));
      await page.screenshot({path:path.join(out,'homepage-'+device+'.png'),fullPage:false});
    } catch(e) { error.push(device+': '+e.message); }
    await context.close();
  }
  await browser.close();
  const map = new Map([[normalize(home),{url:normalize(home),names:['Trang chủ'],devices:[]}]]);
  for(const entry of pages) {
    const url=normalize(entry.url);
    if(!url)continue;
    if(!map.has(url))map.set(url,{url,names:[],devices:[]});
    const item=map.get(url);
    if(entry.text && !item.names.includes(entry.text))item.names.push(entry.text);
    if(!item.devices.includes(entry.device))item.devices.push(entry.device);
  }
  const targets=[...map.values()].map(x=>({...x,slug:slug(x.url)}));
  write('menu-targets.json',{home,targets,error,menuEntries:pages.length,uniqueTargets:targets.length});
  console.log('DISCOVERY',JSON.stringify({menuEntries:pages.length,uniqueTargets:targets.length,error,targets},null,2));
  if(targets.length<=1)throw Error('Menu extraction yielded no inner pages; do not report full coverage');
  if(targets.length>60)throw Error('Too many menu URL targets: '+targets.length);
  if(process.env.GITHUB_OUTPUT) fs.appendFileSync(process.env.GITHUB_OUTPUT,'matrix='+JSON.stringify({include:targets.map(x=>({url:x.url,slug:x.slug}))})+'\n');
}
async function inspect(browser,url,device,dest) {
  const mobile=device==='mobile';
  const context=await browser.newContext({viewport:mobile?{width:390,height:844}:{width:1440,height:900},deviceScaleFactor:1,isMobile:mobile,hasTouch:mobile,locale:'vi-VN',ignoreHTTPSErrors:false});
  const page=await context.newPage();
  const jsErrors=[],responseErrors=[],requestsFailed=[];
  page.on('pageerror',e=>{if(jsErrors.length<12)jsErrors.push(e.message.slice(0,400))});
  page.on('response',r=>{if(r.status()>=400&&responseErrors.length<18)responseErrors.push({status:r.status(),url:r.url().slice(0,240)})});
  page.on('requestfailed',r=>{if(requestsFailed.length<18)requestsFailed.push({failure:r.failure()?.errorText||'',url:r.url().slice(0,240)})});
  let status=null,loadError=null;
  try {
    const response=await page.goto(url,{waitUntil:'domcontentloaded',timeout:45000});
    status=response?.status()||null;
    await page.waitForTimeout(1300);
    await page.screenshot({path:path.join(dest,device+'.png'),fullPage:false,animations:'disabled',timeout:20000});
  } catch(e) {loadError=e.message;}
  let details={};
  try {
    details=await page.evaluate(()=>{
      const visible=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'};
      const brokenImages=[...document.images].filter(i=>visible(i)&&i.complete&&i.naturalWidth===0).slice(0,12).map(i=>({src:i.currentSrc||i.src,alt:i.alt}));
      const smallTargets=[...document.querySelectorAll('a,button,[role="button"]')].filter(visible).filter(e=>{const r=e.getBoundingClientRect();return r.width<40||r.height<40}).slice(0,15).map(e=>({text:(e.innerText||e.getAttribute('aria-label')||'').trim().slice(0,50),width:Math.round(e.getBoundingClientRect().width),height:Math.round(e.getBoundingClientRect().height)}));
      const title=document.title;
      const description=document.querySelector('meta[name="description"]')?.content||'';
      return {title,descriptionLength:description.length,heading1:[...document.querySelectorAll('h1')].map(x=>x.textContent.trim().slice(0,120)),horizontalOverflow:Math.max(0,document.documentElement.scrollWidth-innerWidth),scrollWidth:document.documentElement.scrollWidth,viewportWidth:innerWidth,brokenImages,smallTargets,images:document.images.length,links:document.querySelectorAll('a[href]').length,mainLandmarks:document.querySelectorAll('main,[role="main"]').length,lang:document.documentElement.lang};
    });
    if(mobile) {
      const candidates=page.locator('button[aria-label*="menu" i], button[aria-label*="mở" i], button[class*="hamburger"], [role="button"][aria-label*="menu" i]');
      if(await candidates.count()>0) {
        try {
          await candidates.first().click({timeout:2500});
          await page.waitForTimeout(400);
          await page.screenshot({path:path.join(dest,'mobile-menu-open.png'),fullPage:false,animations:'disabled'});
          details.mobileMenuClicked=true;
        } catch(e) { details.mobileMenuError=e.message.slice(0,200); }
      }
    }
  } catch(e){details.error=e.message;}
  await context.close();
  return {device,status,loadError,jsErrors,responseErrors,requestsFailed,...details};
}
async function lighthouseOnce(url, mobile) {
  const { default:lighthouse } = await import('lighthouse');
  const chromeLauncher = await import('chrome-launcher');
  const chrome=await chromeLauncher.launch({
    chromePath:chromium.executablePath(),
    chromeFlags:['--headless','--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--disable-background-networking']
  });
  try {
    const options={port:chrome.port,logLevel:'error',output:'json',onlyCategories:['performance','accessibility','best-practices','seo'],maxWaitForLoad:45000};
    if(!mobile)options.preset='desktop';
    const result=await lighthouse(url,options);
    const lhr=result.lhr;
    const cats={};
    for(const [key,v]of Object.entries(lhr.categories||{}))cats[key]=Math.round((v.score||0)*100);
    const keys=['first-contentful-paint','largest-contentful-paint','speed-index','total-blocking-time','cumulative-layout-shift','server-response-time','interactive'];
    const metrics={};
    for(const k of keys) if(lhr.audits?.[k]) metrics[k]={value:lhr.audits[k].numericValue??null,display:lhr.audits[k].displayValue??null};
    const issues=(Object.values(lhr.audits||{})).filter(a=>a.score!==null&&a.score!==undefined&&a.score<0.9&&a.details?.type==='opportunity').map(a=>({id:a.id,title:a.title,score:a.score,estimatedSavingsMs:a.details?.overallSavingsMs||0})).sort((a,b)=>b.estimatedSavingsMs-a.estimatedSavingsMs).slice(0,10);
    return {requestedUrl:url,finalUrl:lhr.finalDisplayedUrl,fetchTime:lhr.fetchTime,categories:cats,metrics,issues,runWarnings:lhr.runWarnings,environment:lhr.environment,error:lhr.runtimeError?.message||null};
  } finally {await chrome.kill();}
}
async function audit() {
  const target=process.env.TARGET_URL;
  if(!target||!normalize(target))throw Error('Invalid TARGET_URL');
  const name=slug(target), dest=path.join(out,name);
  fs.mkdirSync(dest,{recursive:true});
  const result={url:target,slug:name,started:new Date().toISOString(),screens:{},lighthouse:{}};
  const browser=await launch();
  for(const device of ['desktop','mobile']) {
    try{result.screens[device]=await inspect(browser,target,device,dest);}
    catch(e){result.screens[device]={error:e.message};}
  }
  await browser.close();
  for(const device of ['mobile','desktop']) {
    try{result.lighthouse[device]=await lighthouseOnce(target,device==='mobile');}
    catch(e){result.lighthouse[device]={error:e.message};}
    write(name+'.json',result);
    console.log('LIGHTHOUSE',JSON.stringify({url:target,device,...result.lighthouse[device].categories,error:result.lighthouse[device].error||null}));
  }
  result.finished=new Date().toISOString();
  write(name+'.json',result);
  console.log('AUDIT_RESULT',JSON.stringify(result).slice(0,22000));
}
if(mode==='discover')await discover();
else if(mode==='audit')await audit();
else throw Error('Unsupported AUDIT_MODE '+mode);
