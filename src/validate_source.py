"""Check source snapshot and the importer eligibility rules without MySQL."""
import json
from collections import Counter
from pathlib import Path

data=json.loads(Path(__file__).with_name('source_data.json').read_text(encoding='utf-8'))
eligible=Counter(); boards=set(); run_ids=set()
for pack in data['games']:
    game=pack['game']; categories={c['id']:c for c in pack['categories']}
    levels={l['id'] for l in pack['levels']}
    for r in pack['runs']:
        c=categories.get(r['category'])
        links=(r.get('videos') or {}).get('links') or []
        players=r.get('players',{}).get('data',[])
        pid=r.get('system',{}).get('platform')
        duration=round(float(r['times']['primary_t'])*1000)
        if not c or (c['type']=='per-level')!=bool(r.get('level')) or not links or len(players)!=1 or players[0].get('rel')!='user' or not pid or duration<=0:
            continue
        assert not r.get('level') or r['level'] in levels
        assert r['id'] not in run_ids
        assert pid in data['platforms']
        run_ids.add(r['id']); eligible[game['abbreviation']]+=1
        boards.add((game['id'],c['id'],r.get('level'),pid,json.dumps(r.get('values') or {},sort_keys=True)))
print('Eligible imported runs:',dict(eligible))
print('Distinct comparable boards:',len(boards))
assert sum(eligible.values())>=300
