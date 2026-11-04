import fs from 'node:fs';
import path from 'node:path';
const dir='site-audit-out';
const menuPath=path.join(dir,'menu-targets.json');
const meta=fs.existsSync(menuPath)?JSON.parse(fs.readFileSync(menuPath,'utf8')):{targets:[]};
const names=fs.existsSync(dir)?fs.readdirSync(dir).filter(s=>s.endsWith('.json')&&!s.startsWith('menu-')&&!s.startsWith('audit-scorecard')):[];
const rows=[];
for(const file of names){
  let x;try{x=JSON.parse(fs.readFileSync(path.join(dir,file),'utf8'))}catch{continue}
  if(!x.url||!x.lighthouse)continue;
  for(const mode of ['mobile','desktop']){
    const l=x.lighthouse[mode]||{},b=x.screens?.[mode]||{};
    rows.push({url:x.url,mode,http:b.status??'',performance:l.categories?.performance??'',accessibility:l.categories?.accessibility??'',bestPractices:l.categories?.['best-practices']??'',seo:l.categories?.seo??'',FCP:l.metrics?.['first-contentful-paint']?.display??'',LCP:l.metrics?.['largest-contentful-paint']?.display??'',CLS:l.metrics?.['cumulative-layout-shift']?.display??'',TBT:l.metrics?.['total-blocking-time']?.display??'',overflow:b.horizontalOverflow??'',brokenImages:b.brokenImages?.length??'',jsErrors:b.jsErrors?.length??'',error:l.error||b.loadError||''});
  }
}
rows.sort((a,b)=>a.url.localeCompare(b.url)||a.mode.localeCompare(b.mode));
const fields=['url','mode','http','performance','accessibility','bestPractices','seo','FCP','LCP','CLS','TBT','overflow','brokenImages','jsErrors','error'];
const quote=v=>'"'+String(v??'').replace(/"/g,'""')+'"';
fs.writeFileSync(path.join(dir,'audit-scorecard.csv'),fields.join(',')+'\n'+rows.map(r=>fields.map(k=>quote(r[k])).join(',')).join('\n')+'\n');
fs.writeFileSync(path.join(dir,'audit-scorecard.json'),JSON.stringify({measured:new Date().toISOString(),targets:meta.targets,rows},null,2));
let md='# Lighthouse + Playwright: audit of all homepage menu URLs\n\n';
md+='Measured: '+new Date().toISOString()+'; mobile 390×844, desktop 1440×900.\n\n';
md+='Discovered **'+meta.targets.length+' unique URLs**; obtained **'+rows.length+'/'+(2*meta.targets.length)+' device reports**.\n\n';
md+='| URL | Mode | HTTP | Performance | Accessibility | Best practices | SEO | LCP | CLS | Overflow px | JS errors |\n|---|---|---:|---:|---:|---:|---:|---|---|---:|---:|\n';
for(const r of rows)md+='| '+[r.url,r.mode,r.http,r.performance,r.accessibility,r.bestPractices,r.seo,r.LCP,r.CLS,r.overflow,r.jsErrors].join(' | ')+' |\n';
md+='\n## Browser / layout flags\n';
const flags=rows.filter(x=>x.error||x.http>=400||x.overflow>2||x.jsErrors>0||x.brokenImages>0);
if(!flags.length)md+='No reported loading errors, horizontal overflows, broken visible images or JS runtime errors.\n';
for(const r of flags)md+='- '+r.mode+' '+r.url+': '+(r.error||('HTTP '+r.http+'; overflow '+r.overflow+'px; broken images '+r.brokenImages+'; JS errors '+r.jsErrors))+'\n';
fs.writeFileSync(path.join(dir,'audit-scorecard.md'),md);
if(process.env.GITHUB_STEP_SUMMARY)fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY,md);
console.log(md);
