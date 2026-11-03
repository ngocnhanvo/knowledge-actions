#!/usr/bin/env python3
"""Discover currently linked Aqua Thanh Xuan navigation/category URLs from homepage."""
import json,os,re,sys,unicodedata
from urllib.parse import urljoin,urlparse,urlunparse
import requests
from bs4 import BeautifulSoup

SITE=os.environ.get('AUDIT_BASE_URL','https://aquathanhxuan.com/')
BASE=urlparse(SITE)
HEADERS={'User-Agent':'Mozilla/5.0 (compatible; MenuLighthouseAudit/1.0; +https://github.com/ngocnhanvo/knowledge-actions)'}
TOP=[
 'THƯƠNG HIỆU','ĐÈN','MÁY LỌC','VẬT LIỆU LỌC','PHỤ KIỆN',
 'ĐÁ, LŨA VÀ CÁT','HÓA CHẤT','BỂ KÍNH','NỀN','CO2','SINH VẬT'
]

def norm(s):
 return re.sub(r'\s+',' ',str(s or '')).strip().casefold()
def slug(s):
 s=unicodedata.normalize('NFKD',str(s)).replace('đ','d').replace('Đ','D')
 s=''.join(c for c in s if not unicodedata.combining(c))
 return re.sub('-+','-',re.sub('[^a-z0-9]+','-',s.lower())).strip('-')[:48] or 'page'
def canonical(href):
 url=urlparse(urljoin(SITE,href))
 if url.scheme not in ('http','https') or url.netloc.lower().removeprefix('www.')!=BASE.netloc.lower().removeprefix('www.'):
  return None
 path=re.sub(r'/+','/',url.path) or '/'
 if path!='/' and not path.endswith('/'):path+='/'
 return urlunparse((BASE.scheme,BASE.netloc,path,'','',''))
response=requests.get(SITE,headers=HEADERS,timeout=40)
response.raise_for_status()
soup=BeautifulSoup(response.text,'html.parser')
pages=[];seen=set();group_stats={}
def add(label,url,group,kind):
 if not url or url in seen:return
 seen.add(url)
 path=urlparse(url).path
 pages.append(dict(slug=f'{len(pages)+1:03d}-{slug(label)}',label=label,group=group,kind=kind,path=path,url=url))
add('Trang chủ',canonical('/'),'Điều hướng','homepage')
for name in TOP:
 candidates=[a for a in soup.find_all('a',href=True) if norm(a.get_text(' ',strip=True))==norm(name)]
 candidates.sort(key=lambda a: (a.find_parent('li') is None,0 if (canonical(a['href']) or '').find('/danh-muc/')>=0 else 1))
 found=False;before=len(pages)
 for a in candidates:
  parent=a.find_parent('li')
  top_url=canonical(a.get('href'))
  if not top_url or '/danh-muc/' not in top_url:continue
  add(name,top_url,name,'parent')
  if parent:
   for child in parent.find_all('a',href=True):
    href=canonical(child.get('href'))
    if not href or '/danh-muc/' not in href:continue
    label=child.get_text(' ',strip=True) or href.rstrip('/').rsplit('/',1)[-1]
    add(label,href,name,'submenu' if child!=a else 'parent')
  found=True;break
 group_stats[name]=len(pages)-before
 if not found:print('WARNING - menu group not extracted:',name, file=sys.stderr)
for label,route in [('Tài khoản','/my-account/'),('Giỏ hàng','/cart/')]:
 if any(norm(a.get_text(' ',strip=True))==norm(label) and canonical(a.get('href')) for a in soup.find_all('a',href=True)):
  add(label,canonical(route),'Điều hướng','utility')
os.makedirs('discovery',exist_ok=True)
with open('discovery/pages.json','w',encoding='utf-8') as f:json.dump(pages,f,ensure_ascii=False,indent=2)
matrix={'include':[dict(slug=x['slug'],url=x['url'],group=x['group'],label=x['label']) for x in pages]}
with open('discovery/matrix.json','w',encoding='utf-8') as f:json.dump(matrix,f,ensure_ascii=False,separators=(',',':'))
with open('discovery/discovery-summary.txt','w',encoding='utf-8') as f:
 f.write(f"Source: {SITE}\nMenu targets discovered: {len(pages)}\n")
 for k,v in group_stats.items():f.write(f"{k}: {v}\n")
print(f'Found {len(pages)} unique internal navigation URLs')
for g,n in group_stats.items():print(f'  {g}: {n}')
if len(pages)<12:sys.exit('Fewer than 12 navigation links discovered: refuse incomplete audit')
with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as f:
 f.write('matrix='+json.dumps(matrix,ensure_ascii=True,separators=(',',':'))+'\n')
