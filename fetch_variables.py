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
