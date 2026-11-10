"""Team 18 Speedrun leaderboard demo: Flask + native parameterized MySQL."""
import os
import uuid
import json
from pathlib import Path
from functools import lru_cache
from datetime import datetime, date
from urllib.parse import urlparse
import pymysql
from flask import Flask, request, redirect, url_for, flash, render_template_string, abort

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY','phase4-local-demo-only')
LOCAL_CREDENTIALS = Path(__file__).with_name('mysql-local') / 'credentials.json'

def db():
    local=json.loads(LOCAL_CREDENTIALS.read_text()) if LOCAL_CREDENTIALS.exists() else {}
    return pymysql.connect(host=os.getenv('DB_HOST',local.get('host','localhost')),port=int(os.getenv('DB_PORT',local.get('port',3306))),user=os.getenv('DB_USER',local.get('user','root')),password=os.getenv('DB_PASSWORD',local.get('password','')),database='speedrun_phase4',charset='utf8mb4',cursorclass=pymysql.cursors.DictCursor,autocommit=False)

def query(sql, args=()):
    con=db()
    try:
        with con.cursor() as c:
            c.execute(sql,args)
            return c.fetchall()
    finally: con.close()

SHELL='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Speedrun Atlas / Team 18</title><link rel="stylesheet" href="{{url_for('static',filename='site.css')}}"></head><body>
<header class="site-header"><div class="header-inner"><a class="brand" href="{{'/preview' if preview else '/'}}" aria-label="Speedrun Atlas home"><span class="brand-mark">S<span>/</span>A</span><span class="brand-name">SPEEDRUN<br>ATLAS</span></a><nav aria-label="Main navigation">{% if preview %}<a href="/preview" class="active">Games</a>{% else %}<a href="/" class="{{'active' if endpoint in ['home','game','category','board'] else ''}}">Games</a><a href="/runs" class="{{'active' if endpoint in ['runs','run_detail'] else ''}}">Runs</a><a href="/reports" class="{{'active' if endpoint=='reports' else ''}}">Reports</a><a href="/submit" class="{{'active' if endpoint=='submit' else ''}}">Submit</a><a href="/admin" class="{{'active' if endpoint=='admin' else ''}}">Manage</a>{% endif %}</nav><span class="header-tag">TEAM 18 / DATABASE PROJECT</span></div></header>
<main>{% with messages=get_flashed_messages() %}{% for m in messages %}<div class="msg">{{m}}</div>{% endfor %}{% endwith %}{{ body|safe }}</main>
<footer><span>SPEEDRUN ATLAS</span><span>TEAM 18 &nbsp; / &nbsp; DATA & APPLICATIONS</span></footer></body></html>'''
def page(body, **kw): return render_template_string(SHELL,body=render_template_string(body,**kw),preview=kw.get('preview',False),endpoint=request.endpoint)

@lru_cache(maxsize=1)
def variable_metadata():
    source=Path(__file__).with_name('source_data.json')
    return json.loads(source.read_text(encoding='utf-8')).get('variables',{})

def variant_label(category_id, description):
    try: selected=json.loads(description or '{}')
    except (ValueError,TypeError): return 'Other variant'
    if not selected: return 'Standard / unspecified'
    definitions=variable_metadata().get(category_id,{})
    parts=[]
    for var_id,value_id in selected.items():
        variable=definitions.get(var_id,{})
        name=variable.get('name',var_id)
        value=variable.get('values',{}).get(value_id,value_id)
        parts.append(f'{name}: {value}')
    return ' · '.join(parts)

def format_duration(milliseconds):
    seconds, milli=divmod(milliseconds,1000)
    minutes, second=divmod(seconds,60)
    hours, minute=divmod(minutes,60)
    return f'{hours}:{minute:02d}:{second:02d}.{milli:03d}' if hours else f'{minute}:{second:02d}.{milli:03d}'

@app.get('/preview')
def preview():
    data=json.loads(Path(__file__).with_name('source_data.json').read_text(encoding='utf-8'))
    term=request.args.get('q','').casefold()
    games=[p for p in data['games'] if term in p['game']['names']['international'].casefold() or term in p['game']['abbreviation'].casefold()]
    return page('''<p class="msg">Preview using saved source data. The MySQL-backed features need a running database.</p><h1>Explore games</h1><p class="muted">Public Speedrun.com data, curated for the database project.</p><form><input name="q" value="{{term}}" placeholder="Search game title or slug"><button>Search</button></form><div class="grid">{% for p in games %}<div class="card"><h2><a href="{{url_for('preview_game',slug=p.game.abbreviation)}}">{{p.game.names.international}}</a></h2><p>{{p.game.released}} · {{p.categories|length}} categories</p><small>{{p.game.abbreviation}}</small></div>{% endfor %}</div>''',games=games,term=request.args.get('q',''),preview=True)

@app.get('/preview/game/<slug>')
def preview_game(slug):
    data=json.loads(Path(__file__).with_name('source_data.json').read_text(encoding='utf-8'))
    pack=next((p for p in data['games'] if p['game']['abbreviation']==slug),None)
    if not pack: abort(404)
    cats={c['id']:c for c in pack['categories']}
    counts={cid:sum(r['category']==cid for r in pack['runs']) for cid in cats}
    return page('''<p><a href="/preview">← Games</a></p><h1>{{p.game.names.international}}</h1><p><a href="{{p.game.weblink}}">View on Speedrun.com</a></p><h2>Categories</h2><table><tr><th>Category</th><th>Type</th><th>Sample runs</th></tr>{% for c in p.categories %}<tr><td><a href="{{url_for('preview_category',slug=p.game.abbreviation,cid=c.id)}}">{{c.name}}</a></td><td>{{c.type}}</td><td>{{counts[c.id]}}</td></tr>{% endfor %}</table>''',p=pack,counts=counts,preview=True)

@app.get('/preview/game/<slug>/category/<cid>')
def preview_category(slug,cid):
    data=json.loads(Path(__file__).with_name('source_data.json').read_text(encoding='utf-8'))
    pack=next((p for p in data['games'] if p['game']['abbreviation']==slug),None)
    if not pack: abort(404)
    cat=next((c for c in pack['categories'] if c['id']==cid),None)
    if not cat: abort(404)
    rows=[]
    for r in pack['runs']:
        if r['category']!=cid: continue
        players=r.get('players',{}).get('data',[])
        if not players: continue
