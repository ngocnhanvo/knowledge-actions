import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright';
import lighthouse from 'lighthouse';
import * as chromeLauncher from 'chrome-launcher';

const base = new URL(process.env.AUDIT_URL || 'https://duhoc.thompbui.com/');
if (base.protocol !== 'https:' || base.hostname !== 'duhoc.thompbui.com') {
  throw new Error('Unexpected audit target');
}
const paths = [
  '/', '/gioi-thieu/', '/lien-he/', '/tin-tuc/',
  '/chuyen-muc/seoul/', '/chuyen-muc/busan/',
  '/dich-vu-tu-van-du-hoc/', '/dich-vu-ho-so-du-hoc/',
  '/dich-vu-luyen-phong-van-visa/', '/dich-vu-san-hoc-bong/',
  '/dich-vu-ho-tro-sau-visa/', '/bai-viet-visa-d4-va-d2/',
  '/bai-viet-hoc-bong-gks-2027/', '/bai-viet-top-10-truong-seoul/',
  '/bai-viet-chi-phi-sinh-hoat-seoul/', '/bai-viet-du-hoc-busan/'
];
const dir = process.env.AUDIT_DIR || 'sequential-audit-out';
fs.mkdirSync(dir, { recursive: true });
const targetRuns = 3;
const metrics = {
  FCP: 'first-contentful-paint',
  LCP: 'largest-contentful-paint',
  CLS: 'cumulative-layout-shift',
  TBT: 'total-blocking-time'
};
const data = {generated:new Date().toISOString(), method:'three Lighthouse runs per URL/device, no concurrency, median', lighthouseVersion:'12', targetRuns, rows:[]};
const intermediate = path.join(dir,'raw-results.json');
const save = () => fs.writeFileSync(intermediate, JSON.stringify(data,null,2));
async function measure(url, device) {
  const chrome=await chromeLauncher.launch({
    chromePath:chromium.executablePath(),
    chromeFlags:['--headless','--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--disable-background-networking']
  });
  try {
    const options={port:chrome.port, logLevel:'error',output:'json',
      onlyCategories:['performance','accessibility','best-practices','seo'],maxWaitForLoad:45000};
    if(device==='desktop') options.preset='desktop';
    const {lhr}=await lighthouse(url,options);
    if(lhr.runtimeError)throw Error(lhr.runtimeError.message);
    const scores=Object.fromEntries(Object.entries(lhr.categories||{}).map(([k,v])=>[k,v.score==null?null:Math.round(v.score*100)]));
    const values=Object.fromEntries(Object.entries(metrics).map(([name,key])=>[name,lhr.audits?.[key]?.numericValue??null]));
    return {scores,values,finalUrl:lhr.finalDisplayedUrl,fetchTime:lhr.fetchTime};
  } finally {await chrome.kill();}
}
function median(nums) {
  const a=nums.filter(x=>typeof x==='number'&&Number.isFinite(x)).sort((x,y)=>x-y);
  if(!a.length)return null;
  const mid=Math.floor(a.length/2);
  return a.length%2?a[mid]:(a[mid-1]+a[mid])/2;
}
const summary=[];
for(const sitePath of paths) {
  const url=new URL(sitePath,base).href;
  const page={path:sitePath,url,results:{}};
  for(const device of ['mobile','desktop']) {
    const runs=[];
    let tries=0;
    while(runs.length<targetRuns && tries<targetRuns+2) {
      tries++;
      const index=runs.length+1;
      try {
        const result=await measure(url,device);
        runs.push(result);
        console.log('MEASURED '+sitePath+' '+device+' '+index+'/'+targetRuns+' performance='+result.scores.performance+' LCPms='+Math.round(result.values.LCP||0));
      } catch(err) {
        console.error('ERROR '+sitePath+' '+device+' try='+tries+' '+String(err.message).slice(0,250));
      }
      page.results[device]={runs};
      data.rows=summary.concat([page]);
      save();
    }
    page.results[device]={
      runs, completed:runs.length,
      performance:median(runs.map(x=>x.scores.performance)),
      accessibility:median(runs.map(x=>x.scores.accessibility)),
      bestPractices:median(runs.map(x=>x.scores['best-practices'])),
      seo:median(runs.map(x=>x.scores.seo)),
      LCP:median(runs.map(x=>x.values.LCP))
    };
  }
  summary.push(page);
  data.rows=summary;
  save();
  console.log('PAGE_COMPLETE '+sitePath+' '+JSON.stringify({mobile:page.results.mobile.performance,desktop:page.results.desktop.performance}));
}
let md='# Lighthouse sequential rerun (median of 3)\n\n';
md+='Target '+base.origin+' · 16 distinct URLs · three measurements each on mobile and desktop, no simultaneous runs.\n\n';
md+='| Path | Performance M/D | Accessibility M/D | SEO M/D | LCP M/D (s) |\n';
md+='|---|---:|---:|---:|---:|\n';
const rowsCsv=[['path','mobile_performance','desktop_performance','mobile_accessibility','desktop_accessibility','mobile_best_practices','desktop_best_practices','mobile_seo','desktop_seo','mobile_lcp_ms','desktop_lcp_ms','mobile_runs','desktop_runs']];
for(const p of summary) {
  const m=p.results.mobile,d=p.results.desktop;
  const fmt=v=>v==null?'—':String(v);
  const fmtLcp=v=>v==null?'—':(v/1000).toFixed(2);
  md+='| '+p.path+' | '+fmt(m.performance)+' / '+fmt(d.performance)+' | '+fmt(m.accessibility)+' / '+fmt(d.accessibility)+' | '+fmt(m.seo)+' / '+fmt(d.seo)+' | '+fmtLcp(m.LCP)+' / '+fmtLcp(d.LCP)+' |\n';
  rowsCsv.push([p.path,m.performance,d.performance,m.accessibility,d.accessibility,m.bestPractices,d.bestPractices,m.seo,d.seo,m.LCP,d.LCP,m.completed,d.completed]);
}
const csv=x=>'"'+String(x??'').replace(/"/g,'""')+'"';
fs.writeFileSync(path.join(dir,'scorecard.csv'),rowsCsv.map(r=>r.map(csv).join(',')).join('\n')+'\n');
fs.writeFileSync(path.join(dir,'scorecard.md'),md);
if(process.env.GITHUB_STEP_SUMMARY)fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY,md);
console.log(md);
if(summary.some(x=>x.results.mobile.completed<targetRuns||x.results.desktop.completed<targetRuns))process.exitCode=1;
