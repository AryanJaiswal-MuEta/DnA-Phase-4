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
