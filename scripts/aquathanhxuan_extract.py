#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
slug=os.environ['PAGE_SLUG']
target=os.environ['PAGE_URL']
label=os.environ['PAGE_LABEL']
group=os.environ['PAGE_GROUP']
Path('outputs').mkdir(exist_ok=True)
for mode in ('mobile','desktop'):
 p=Path(f'outputs/audit-{slug}-{mode}.json')
 out=dict(slug=slug,label=label,group=group,url=target,mode=mode,status='no-report')
 if p.exists():
  try:
   d=json.loads(p.read_text(encoding='utf-8'))
   audits=d.get('audits') or {}
   def metric(key,prop='numericValue'):
    return (audits.get(key) or {}).get(prop)
   def score(key):
    s=(d.get('categories') or {}).get(key,{}).get('score')
    return round(s*100) if isinstance(s,(int,float)) else None
   def saving(key):
    a=audits.get(key) or {}
    details=a.get('details') or {}
    return details.get('overallSavingsBytes') or (a.get('numericValue') if a.get('numericUnit')=='byte' else None)
   out.update(status='ok',fetch_time=d.get('fetchTime'),final_url=d.get('finalUrl'),lighthouse_version=d.get('lighthouseVersion'),
    performance=score('performance'),accessibility=score('accessibility'),best_practices=score('best-practices'),seo=score('seo'),
    fcp_ms=metric('first-contentful-paint'),lcp_ms=metric('largest-contentful-paint'),tbt_ms=metric('total-blocking-time'),
    cls=metric('cumulative-layout-shift'),speed_index_ms=metric('speed-index'),tti_ms=metric('interactive'),
    server_ms=metric('server-response-time'),total_bytes=metric('total-byte-weight'),
    unused_js_bytes=saving('unused-javascript'),unused_css_bytes=saving('unused-css-rules'),
    cache_savings_bytes=saving('cache-insight'),
    render_blocking_ms=saving('render-blocking-resources'),warnings=d.get('runWarnings',[])[:4],
    runtime_error=d.get('runtimeError'),http_status=metric('http-status-code'))
   if d.get('runtimeError') or out['performance'] is None:out['status']='invalid-lhr'
  except Exception as e:out['status']='parse-error';out['error']=str(e)
 else:out['error']='Lighthouse CLI did not create JSON'
 Path(f'outputs/metrics-{slug}-{mode}.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
 print(f"{slug} {mode}: {out['status']} performance={out.get('performance')} LCP={out.get('lcp_ms')}ms CLS={out.get('cls')} TBT={out.get('tbt_ms')}ms")
