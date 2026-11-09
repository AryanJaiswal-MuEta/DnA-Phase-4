"""Load the cached public API snapshot into the Phase 3 MySQL schema."""
import datetime as dt
import hashlib
import json
import os
import pymysql
from pathlib import Path

DATA = json.loads(Path(__file__).with_name('source_data.json').read_text(encoding='utf-8'))

def stamp(value, default='2015-01-01T00:00:00'):
    return (value or default).replace('T', ' ').replace('Z', '')[:19]

def main():
    local_path=Path(__file__).with_name('mysql-local')/'credentials.json'
    local=json.loads(local_path.read_text()) if local_path.exists() else {}
    con = pymysql.connect(host=os.getenv('DB_HOST',local.get('host','localhost')), port=int(os.getenv('DB_PORT',local.get('port',3306))), user=os.getenv('DB_USER',local.get('user','root')), password=os.getenv('DB_PASSWORD',local.get('password','')), database='speedrun_phase4', charset='utf8mb4', autocommit=False)
    cur = con.cursor()
    def put(sql, args): cur.execute(sql, args)
    put("INSERT INTO permission VALUES ('REVIEW_RUNS','May review runs for this game'),('EDIT_RULES','May edit board rules for this game'),('MANAGE_GAME','May manage this game')", ())
    put("INSERT INTO users VALUES ('team5_admin','team5_admin','Team 18 Demo Admin','2026-11-01 00:00:00',1,1,NULL,NULL)", ())
    platform_ids = sorted({r['system']['platform'] for pack in DATA['games'] for r in pack['runs'] if r.get('system',{}).get('platform')})
    for pid in platform_ids:
        meta=DATA['platforms'][pid]
        put('INSERT INTO platform(platform_id,name,manufacturer) VALUES(%s,%s,%s)', (pid,meta['name'],None))
    count = 0
    for pack in DATA['games']:
        g = pack['game']; gid=g['id']; slug=g['abbreviation']
        put('INSERT INTO game VALUES(%s,%s,%s,%s,%s,%s,1)', (gid,slug,g['names']['international'],g['names'].get('japanese'),g.get('released'),g.get('weblink')))
        for pid in platform_ids:
            if any(r['system'].get('platform')==pid for r in pack['runs']):
                put('INSERT INTO supports VALUES(%s,%s)',(gid,pid))
        cats={}
        for c in pack['categories']:
            kind='per_level' if c['type']=='per-level' else 'full_game'
            cats[c['id']]=c
            put('INSERT INTO category VALUES(%s,%s,%s,1,%s)',(c['id'],c['name'],kind,gid))
        for i,l in enumerate(pack['levels'],1):
            put('INSERT INTO level VALUES(%s,%s,%s,%s)',(l['id'],l['name'],i,gid))
        boards={}; used_rule_keys=set()
        for r in pack['runs']:
            cid=r['category']; c=cats.get(cid)
            if not c or (c['type']=='per-level') != bool(r.get('level')): continue
            links=(r.get('videos') or {}).get('links') or []
            if not links: continue
            players=r.get('players',{}).get('data',[])
            if len(players)!=1 or players[0].get('rel')!='user': continue
            player=players[0]; uid=player['id']; pid=r['system'].get('platform')
            if not pid: continue
            duration=round(float(r['times']['primary_t'])*1000)
            if duration<=0: continue
            for u in [player]:
                name=u['names']['international'] or u['id']
                loc=u.get('location') or {}; country=(loc.get('country') or {}).get('code')
                put('INSERT IGNORE INTO users(user_id,username,display_name,joined_at,is_admin,active,country_code) VALUES(%s,%s,%s,%s,0,1,%s)',(u['id'],(name[:90]+'_'+u['id'])[:100],name[:150],stamp(u.get('signup')),country))
            values=json.dumps(r.get('values') or {},sort_keys=True,separators=(',',':'))
            variant=hashlib.sha1(values.encode()).hexdigest()[:12] if values!='{}' else 'standard'
            key=(cid,r.get('level'),pid,variant)
            if key not in boards:
                code=f'{slug}:{cid}:{r.get("level") or "full"}:{pid}:{variant}'
                put('INSERT INTO leaderboard(board_code,variant_code,variant_description,timing_method,active,category_id,platform_id,level_id) VALUES(%s,%s,%s,%s,1,%s,%s,%s)',(code,variant,values[:255],'realtime',cid,pid,r.get('level')))
                bid=cur.lastrowid; boards[key]=bid
                put('INSERT INTO board_rule_version VALUES(%s,1,%s,%s,%s)',(bid,c.get('rules') or 'See source game rules.', '2015-01-01 00:00:00','2015-01-01 00:00:00'))
            bid=boards[key]
            submitted=stamp(r.get('submitted') or r.get('date-time'))
            while (submitted,bid) in used_rule_keys:
                submitted=(dt.datetime.fromisoformat(submitted)+dt.timedelta(seconds=1)).strftime('%Y-%m-%d %H:%M:%S')
            used_rule_keys.add((submitted,bid))
            put('INSERT INTO run_rule VALUES(%s,%s,1)',(submitted,bid))
            put('INSERT INTO run VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)',(r['id'],r.get('date') or submitted[:10],duration,r.get('comment'),uid,uid,submitted,bid,r.get('weblink')))
            for n,link in enumerate(links[:10],1):
                put('INSERT INTO evidence_link VALUES(%s,%s,%s,%s,NULL)',(r['id'],n,link['uri'],'video'))
            examiner=r['status'].get('examiner') or 'team5_admin'
            if examiner:
                put('INSERT IGNORE INTO users(user_id,username,display_name,joined_at,is_admin,active) VALUES(%s,%s,%s,%s,0,1)',(examiner,'moderator_'+examiner,'Moderator '+examiner,'2015-01-01 00:00:00'))
                put('INSERT IGNORE INTO authorizes VALUES(%s,%s,%s)',(examiner,gid,'REVIEW_RUNS'))
                put('INSERT INTO review_event VALUES(%s,1,%s,%s,NULL,%s)',(r['id'],stamp(r['status'].get('verify-date'),submitted),'verified',examiner))
            count+=1
        for perm in ('REVIEW_RUNS','EDIT_RULES','MANAGE_GAME'):
            put('INSERT IGNORE INTO authorizes VALUES(%s,%s,%s)',('team5_admin',gid,perm))
        print(slug, 'boards',len(boards),flush=True)
    con.commit(); con.close()
    print('Imported',count,'source runs')

if __name__=='__main__': main()
