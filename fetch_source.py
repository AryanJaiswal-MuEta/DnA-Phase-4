"""Cache public Speedrun.com API records for reproducible offline population."""
import json
import time
import urllib.request
from pathlib import Path

BASE = 'https://www.speedrun.com/api/v1/'
OUT = Path(__file__).with_name('source_data.json')

def get(path):
    for attempt in range(4):
        try:
            req = urllib.request.Request(BASE + path, headers={'User-Agent': 'Team18-Course-Project/1.0'})
            with urllib.request.urlopen(req, timeout=45) as response:
                return json.load(response)['data']
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)

data = {'source': BASE, 'games': []}
for slug in ('sm64', 'celeste', 'smb1'):
    game = get('games/' + slug)
    gid = game['id']
    categories = get(f'games/{gid}/categories')
    levels = get(f'games/{gid}/levels')
    runs_by_id = {}
    for category in categories:
        category_runs = get(f'runs?game={gid}&category={category["id"]}&status=verified&max=200&embed=players')
        for run in category_runs:
            runs_by_id[run['id']] = run
        print(slug, category['name'], len(category_runs), flush=True)
        time.sleep(0.1)
    runs = list(runs_by_id.values())
    data['games'].append({'game': game, 'categories': categories, 'levels': levels, 'runs': runs})
    print(slug, len(categories), len(levels), len(runs), flush=True)
platform_ids = {run['system']['platform'] for pack in data['games'] for run in pack['runs'] if run.get('system',{}).get('platform')}
data['platforms'] = {pid:get('platforms/'+pid) for pid in sorted(platform_ids)}
OUT.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
print(OUT)
