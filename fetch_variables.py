"""Add human-readable category variable labels to the cached API snapshot."""
import json
import time
import urllib.request
from pathlib import Path

path=Path(__file__).with_name('source_data.json')
data=json.loads(path.read_text(encoding='utf-8'))
data.setdefault('variables',{})
for pack in data['games']:
    for category in pack['categories']:
        cid=category['id']
        if cid in data['variables']: continue
        url=f'https://www.speedrun.com/api/v1/categories/{cid}/variables'
        req=urllib.request.Request(url,headers={'User-Agent':'Team18-Course-Project/1.0'})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req,timeout=30) as response:
                    raw=json.load(response)['data']
                break
            except Exception:
                if attempt==3: raise
                time.sleep(2**attempt)
        data['variables'][cid]={v['id']:{'name':v['name'],'values':{key:item['label'] for key,item in v['values']['values'].items()}} for v in raw}
        print(pack['game']['abbreviation'],category['name'],len(raw),flush=True)
path.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
