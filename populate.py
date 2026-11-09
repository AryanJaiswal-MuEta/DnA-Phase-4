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
