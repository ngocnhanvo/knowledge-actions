#!/usr/bin/env python3
import json,csv,statistics,collections
from pathlib import Path
out=Path('combined');out.mkdir(exist_ok=True)
root=Path('collected')
metrics=sorted(root.rglob('metrics-*.json'))
rows=[json.loads(p.read_text(encoding='utf-8')) for p in metrics]
pages_path=root/'pages.json'
pages=json.loads(pages_path.read_text(encoding='utf-8')) if pages_path.exists() else []
(out/'pages.json').write_text(json.dumps(pages,ensure_ascii=False,indent=2),encoding='utf-8')
(out/'lighthouse-results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
cols=['slug','label','group','mode','status','performance','accessibility','best_practices','seo','fcp_ms','lcp_ms','tbt_ms','cls','speed_index_ms','tti_ms','server_ms','total_bytes','unused_js_bytes','unused_css_bytes','cache_savings_bytes','final_url','fetch_time','error']
with (out/'lighthouse-results.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore');w.writeheader();w.writerows(rows)
def valid(mode,key):
 return [r[key] for r in rows if r.get('mode')==mode and r.get('status')=='ok' and isinstance(r.get(key),(int,float))]
def med(a):
 return statistics.median(a) if a else None
def fmt(x,div=1,suffix=''):
 return '-' if x is None else (f'{x/div:.2f}{suffix}' if div!=1 else f'{x:g}{suffix}')
summ=['# Aqua Thanh Xuan - Navigation Lighthouse audit','',f'Pages discovered: {len(pages)}',f'Total results: {len(rows)}','']
for mode in ['mobile','desktop']:
 vals=valid(mode,'performance'); lcp=valid(mode,'lcp_ms'); tbt=valid(mode,'tbt_ms');cls=valid(mode,'cls')
 summ.extend([f'## {mode.upper()}',f'Completed: {len(vals)}/{len(pages)}',f'Performance median: {fmt(med(vals))}/100 (min {fmt(min(vals) if vals else None)}, max {fmt(max(vals) if vals else None)})',
 f'LCP median: {fmt(med(lcp),1000,"s")}',f'TBT median: {fmt(med(tbt),1,"ms")}',f'CLS median: {fmt(med(cls))}',''])
by=collections.defaultdict(dict)
for r in rows:by[r['slug']][r['mode']]=r
summ+=['## Per-page table','|Page|Group|Mobile|Desktop|LCP M|LCP D|Status|','|---|---|---:|---:|---:|---:|---|']
for p in pages:
 group=by.get(p['slug'],{});m=group.get('mobile',{});d=group.get('desktop',{})
 summ.append('|'+ '|'.join([p['label'].replace('|','/'),p['group'].replace('|','/'),fmt(m.get('performance')),fmt(d.get('performance')),fmt(m.get('lcp_ms'),1000,'s'),fmt(d.get('lcp_ms'),1000,'s'),'OK' if m.get('status')=='ok' and d.get('status')=='ok' else 'CHECK'])+'|')
(out/'lighthouse-summary.md').write_text('\n'.join(summ)+'\n',encoding='utf-8')
print('\n'.join(summ[:16]))
with open(__import__('os').environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as f:f.write('\n'.join(summ)+'\n')
