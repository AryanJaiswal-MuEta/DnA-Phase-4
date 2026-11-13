"""Team 18 Speedrun leaderboard demo: Flask + native parameterized MySQL."""
import os
import uuid
import json
from pathlib import Path
from functools import lru_cache
from datetime import datetime, date
from urllib.parse import urlparse
import pymysql
from flask import Flask, request, redirect, url_for, flash, render_template_string, abort, jsonify

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY','phase4-local-demo-only')
LOCAL_CREDENTIALS = Path(__file__).with_name('mysql-local') / 'credentials.json'
PAGE_TEMPLATES = Path(__file__).with_name('templates')

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

SHELL='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TAKA / Team 18</title><link rel="stylesheet" href="{{url_for('static',filename='site.css')}}"><link rel="stylesheet" href="{{url_for('static',filename='experience.css')}}"><link rel="stylesheet" href="{{url_for('static',filename='submit-menu.css')}}"><link rel="stylesheet" href="{{url_for('static',filename='tv-home.css')}}"></head><body class="{{page_class}}">
{% if page_class=='home-page' %}<header class="submit-menu-top"><a class="submit-menu-brand" href="/" aria-label="TAKA home">TAKA</a><nav class="submit-game-nav" aria-label="Main navigation"><a href="/" aria-current="page">GAMES</a><a href="/runs">RUNS</a><a href="/reports">REPORTS</a><a href="/submit">SUBMIT</a><a href="/admin">MANAGE</a></nav><span class="submit-menu-team">TEAM 18 <span class="live-dot"></span></span></header>{% else %}<header class="site-header"><div class="header-inner"><a class="brand" href="{{'/preview' if preview else '/'}}" aria-label="TAKA home"><span class="brand-mark">TAKA</span></a><nav aria-label="Main navigation">{% if preview %}<a href="/preview" class="active">Games</a>{% else %}<a href="/" class="{{'active' if endpoint in ['home','game','category','board'] else ''}}">Games</a><a href="/runs" class="{{'active' if endpoint in ['runs','run_detail'] else ''}}">Runs</a><a href="/reports" class="{{'active' if endpoint=='reports' else ''}}">Reports</a><a href="/submit" class="{{'active' if endpoint=='submit' else ''}}">Submit</a><a href="/admin" class="{{'active' if endpoint=='admin' else ''}}">Manage</a>{% endif %}</nav><span class="header-tag">TEAM 18 / DATABASE PROJECT</span></div></header>{% endif %}
<div class="signal-bar" aria-label="Site status"><span class="signal-live"><i aria-hidden="true"></i> SYSTEM ONLINE</span><span class="signal-flow">TAKA <b>//</b> THREE GAMES <b>//</b> VERIFIED RUNS <b>//</b> EVERY SECOND COUNTS</span><span class="signal-end">TEAM 18 / PHASE 4</span></div>
<main>{% with messages=get_flashed_messages() %}{% for m in messages %}<div class="msg">{{m}}</div>{% endfor %}{% endwith %}{{ body|safe }}</main>
<footer><span>TAKA</span><span>TEAM 18 &nbsp; / &nbsp; DATA & APPLICATIONS</span></footer></body></html>'''
def page(body, **kw): return render_template_string(SHELL,body=render_template_string(body,**kw),preview=kw.get('preview',False),endpoint=request.endpoint,page_class=kw.get('page_class',''))

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
        rows.append({'name':players[0].get('names',{}).get('international') or 'Guest','time':r['times']['primary_t'],'date':r.get('date'),'url':r['weblink']})
    rows.sort(key=lambda x:x['time'])
    return page('''<p><a href="{{url_for('preview_game',slug=p.game.abbreviation)}}">← {{p.game.names.international}}</a></p><h1>{{p.game.names.international}} / {{cat.name}}</h1><p>{{rows|length}} sample runs · fastest {{'%.3f'|format(rows[0].time)}}s</p><table><tr><th>Rank</th><th>Runner</th><th>Time</th><th>Date</th><th>Source</th></tr>{% for r in rows %}<tr><td>{{loop.index}}</td><td>{{r.name}}</td><td>{{'%.3f'|format(r.time)}}s</td><td>{{r.date}}</td><td><a href="{{r.url}}">Run</a></td></tr>{% endfor %}</table>''',p=pack,cat=cat,rows=rows,preview=True)

@app.get('/')
def home():
    games=query('SELECT g.*, COUNT(DISTINCT b.board_id) boards FROM game g LEFT JOIN category c ON c.game_id=g.game_id LEFT JOIN leaderboard b ON b.category_id=c.category_id GROUP BY g.game_id ORDER BY g.title_international')
    total=sum(g['boards'] for g in games)
    art={'celeste':'game-art/celeste.webp','sm64':'game-art/sm64-generated.png','smb1':'game-art/smb1-generated.png'}
    return page(PAGE_TEMPLATES.joinpath('home.html').read_text(encoding='utf-8'),games=games,total=total,art=art,page_class='home-page')

@app.get('/api/tv/game/<gid>')
def tv_game(gid):
    games=query('SELECT game_id,title_international,slug,release_year FROM game WHERE game_id=%s',(gid,))
    if not games: abort(404)
    categories=query('''SELECT c.category_id,c.name,c.kind,COUNT(DISTINCT b.board_id) board_count,COUNT(r.run_id) run_count FROM category c LEFT JOIN leaderboard b ON b.category_id=c.category_id LEFT JOIN run r ON r.board_id=b.board_id WHERE c.game_id=%s GROUP BY c.category_id ORDER BY c.kind,c.name''',(gid,))
    return jsonify(game=games[0],categories=categories)

@app.get('/api/tv/category/<cid>')
def tv_category(cid):
    cats=query('''SELECT c.category_id,c.game_id,c.name,c.kind,g.title_international game_name FROM category c JOIN game g ON g.game_id=c.game_id WHERE c.category_id=%s''',(cid,))
    if not cats: abort(404)
    boards=query('''SELECT b.board_id,b.variant_description,l.name level_name,p.name platform_name,COUNT(r.run_id) run_count FROM leaderboard b LEFT JOIN level l ON l.level_id=b.level_id JOIN platform p ON p.platform_id=b.platform_id LEFT JOIN run r ON r.board_id=b.board_id WHERE b.category_id=%s GROUP BY b.board_id ORDER BY l.display_order,run_count DESC,p.name''',(cid,))
    for b in boards: b['settings']=variant_label(cid,b['variant_description'])
    return jsonify(category=cats[0],boards=[{'board_id':b['board_id'],'level':b['level_name'] or 'Full game','platform':b['platform_name'],'settings':b['settings'],'runs':b['run_count']} for b in boards])

@app.get('/api/tv/board/<int:bid>')
def tv_board(bid):
    boards=query('''SELECT b.board_id,b.category_id,b.variant_description,g.title_international game_name,c.name category_name,l.name level_name,p.name platform_name,rv.rules_text FROM leaderboard b JOIN category c ON c.category_id=b.category_id JOIN game g ON g.game_id=c.game_id LEFT JOIN level l ON l.level_id=b.level_id JOIN platform p ON p.platform_id=b.platform_id LEFT JOIN board_rule_version rv ON rv.board_id=b.board_id AND rv.version_no=(SELECT MAX(version_no) FROM board_rule_version WHERE board_id=b.board_id) WHERE b.board_id=%s''',(bid,))
    if not boards: abort(404)
    rows=query('''SELECT r.run_id,u.display_name,r.duration_ms,r.run_date FROM run r JOIN users u ON u.user_id=r.runner_id JOIN run_status rs ON rs.run_id=r.run_id WHERE r.board_id=%s AND rs.current_status='verified' ORDER BY r.duration_ms,r.run_date''',(bid,))
    best={}
    for r in rows: best.setdefault(r['display_name'],r)
    ranked=sorted(best.values(),key=lambda r:(r['duration_ms'],r['run_date']))
    board=boards[0]
    return jsonify(board={'board_id':bid,'category_id':board['category_id'],'game':board['game_name'],'category':board['category_name'],'level':board['level_name'] or 'Full game','platform':board['platform_name'],'settings':variant_label(board['category_id'],board['variant_description']),'rules':board['rules_text'] or ''},runs=[{'run_id':r['run_id'],'runner':r['display_name'],'time':format_duration(r['duration_ms']),'date':str(r['run_date']),'rank':i} for i,r in enumerate(ranked,1)])

@app.get('/api/tv/run/<rid>')
def tv_run(rid):
    runs=query('''SELECT r.run_id,r.board_id,r.duration_ms,r.run_date,r.source_url,rs.current_status,u.display_name,g.title_international game_name,c.name category_name FROM run r JOIN run_status rs ON rs.run_id=r.run_id JOIN users u ON u.user_id=r.runner_id JOIN leaderboard b ON b.board_id=r.board_id JOIN category c ON c.category_id=b.category_id JOIN game g ON g.game_id=c.game_id WHERE r.run_id=%s''',(rid,))
    if not runs: abort(404)
    evidence=query('SELECT url,kind,label FROM evidence_link WHERE run_id=%s ORDER BY evidence_no',(rid,))
    r=runs[0]
    return jsonify(run={'run_id':r['run_id'],'board_id':r['board_id'],'runner':r['display_name'],'time':format_duration(r['duration_ms']),'date':str(r['run_date']),'status':r['current_status'],'game':r['game_name'],'category':r['category_name'],'source_url':r['source_url']},evidence=evidence)

@app.get('/game/<gid>')
def game(gid):
    games=query('SELECT * FROM game WHERE game_id=%s',(gid,))
    if not games: abort(404)
    categories=query('''SELECT c.category_id,c.name,c.kind,COUNT(DISTINCT b.board_id) board_count,COUNT(r.run_id) run_count FROM category c LEFT JOIN leaderboard b ON b.category_id=c.category_id LEFT JOIN run r ON r.board_id=b.board_id WHERE c.game_id=%s GROUP BY c.category_id ORDER BY c.kind,c.name''',(gid,))
    art={'celeste':'game-art/celeste.webp','sm64':'game-art/sm64-generated.png','smb1':'game-art/smb1-generated.png'}.get(games[0]['slug'])
    if games[0]['slug']=='celeste':
        return page('''<div class="breadcrumb"><a href="/">GAMES</a><span>/</span>CELESTE</div><section class="celeste-stage"><div class="celeste-orbit" aria-hidden="true"></div><div class="celeste-wordmark" aria-hidden="true">CELESTE</div><div class="celeste-copy"><span class="eyebrow"><span class="live-dot"></span> FEATURED GAME / 2018</span><h1>CLIMB.<br><em>RESET.</em><br>REPEAT.</h1><p>One mountain. A thousand ways to race it. Pick your category and chase the fastest verified time.</p></div><img class="celeste-sticker" src="{{url_for('static',filename='game-art/celeste-character.png')}}" alt="Madeline leaping upward"><aside class="celeste-rail" aria-label="Celeste categories"><div class="celeste-rail-head"><span>01 / CHOOSE YOUR ROUTE</span><strong>{{categories|length}} CATEGORIES</strong></div><div class="celeste-rail-scroll" tabindex="0" aria-label="Scroll Celeste categories">{% for c in categories %}<a class="celeste-rail-item" href="{{url_for('category',gid=g.game_id,cid=c.category_id)}}"><span class="celeste-rail-index">{{'%02d'|format(loop.index)}}</span><span class="celeste-rail-info"><strong>{{c.name}}</strong><small>{{'FULL GAME' if c.kind=='full_game' else 'LEVEL RUNS'}}</small><span class="celeste-rail-reveal"><b>{{c.run_count}} RUNS</b><b>{{c.board_count}} BOARDS</b></span></span><span class="celeste-rail-arrow" aria-hidden="true">↗</span></a>{% endfor %}</div><div class="celeste-rail-foot">SCROLL FOR MORE <span aria-hidden="true">↓</span></div></aside><div class="celeste-stats"><span>CELESTE <b>/</b> TAKA</span><strong>{{categories|length}} <small>CATEGORIES</small></strong><strong>{{total_runs}} <small>RUNS INDEXED</small></strong></div></section><div class="celeste-source"><span>KEEP CLIMBING.</span><a href="{{g.source_url}}" target="_blank" rel="noopener noreferrer">ORIGINAL GAME PAGE ↗</a></div>''',g=games[0],categories=categories,total_runs=sum(c['run_count'] for c in categories),page_class='celeste-page')
    return page('''<div class="breadcrumb"><a href="/">GAMES</a><span>/</span>{{g.slug|upper}}</div><section class="celeste-stage mario-stage {{g.slug}}-stage"><div class="celeste-orbit" aria-hidden="true"></div><div class="celeste-wordmark" aria-hidden="true">{{g.slug|upper}}</div><div class="celeste-copy mario-copy"><span class="eyebrow"><span class="live-dot"></span> GAME PROFILE / {{g.release_year or 'YEAR UNKNOWN'}}</span><h1>{{g.title_international}}</h1><p>Pick a category. Compare verified runs. Chase the fastest time.</p></div><img class="mario-art" src="{{url_for('static',filename=art)}}" alt="" aria-hidden="true"><aside class="celeste-rail" aria-label="{{g.title_international}} categories"><div class="celeste-rail-head"><span>01 / CHOOSE YOUR ROUTE</span><strong>{{categories|length}} CATEGORIES</strong></div><div class="celeste-rail-scroll" tabindex="0" aria-label="Scroll {{g.title_international}} categories">{% for c in categories %}<a class="celeste-rail-item" href="{{url_for('category',gid=g.game_id,cid=c.category_id)}}"><span class="celeste-rail-index">{{'%02d'|format(loop.index)}}</span><span class="celeste-rail-info"><strong>{{c.name}}</strong><small>{{'FULL GAME' if c.kind=='full_game' else 'LEVEL RUNS'}}</small><span class="celeste-rail-reveal"><b>{{c.run_count}} RUNS</b><b>{{c.board_count}} BOARDS</b></span></span><span class="celeste-rail-arrow" aria-hidden="true">↗</span></a>{% endfor %}</div><div class="celeste-rail-foot">SCROLL FOR MORE <span aria-hidden="true">↓</span></div></aside><div class="celeste-stats"><span>{{g.title_international|upper}} <b>/</b> TAKA</span><strong>{{categories|length}} <small>CATEGORIES</small></strong><strong>{{total_runs}} <small>RUNS INDEXED</small></strong></div></section>''',g=games[0],categories=categories,art=art,total_runs=sum(c['run_count'] for c in categories),page_class='celeste-page mario-page')

@app.get('/game/<gid>/category/<cid>')
def category(gid,cid):
    games=query('SELECT * FROM game WHERE game_id=%s',(gid,))
    if not games: abort(404)
    cats=query('SELECT * FROM category WHERE category_id=%s AND game_id=%s',(cid,gid))
    if not cats: abort(404)
    boards=query('''SELECT b.*,l.name level_name,p.name platform_name,COUNT(r.run_id) run_count FROM leaderboard b LEFT JOIN level l ON l.level_id=b.level_id JOIN platform p ON p.platform_id=b.platform_id LEFT JOIN run r ON r.board_id=b.board_id WHERE b.category_id=%s GROUP BY b.board_id ORDER BY l.display_order,run_count DESC,p.name''',(cid,))
    for b in boards: b['variant_label']=variant_label(cid,b['variant_description'])
    platforms=sorted({b['platform_name'] for b in boards})
    return page('''<div class="breadcrumb"><a href="/">GAMES</a><span>/</span><a href="{{url_for('game',gid=g.game_id)}}">{{g.slug|upper}}</a><span>/</span>{{c.name|upper}}</div><section class="page-intro"><span class="eyebrow">CATEGORY / {{'FULL GAME' if c.kind=='full_game' else 'LEVEL RUNS'}}</span><h1>{{c.name}}</h1><p class="muted">{{g.title_international}} · Choose a leaderboard to see ranked runs.</p></section><section class="section-head"><div><span class="eyebrow">03 / SELECT A BOARD</span><h2>Leaderboards</h2></div><span class="section-count">{{boards|length}} BOARDS</span></section><div class="board-controls"><label class="sr-only" for="board-filter">Filter leaderboards</label><input id="board-filter" type="search" placeholder="Filter level or settings"><label class="sr-only" for="platform-filter">Platform</label><select id="platform-filter"><option value="">All platforms</option>{% for p in platforms %}<option value="{{p}}">{{p}}</option>{% endfor %}</select><span id="visible-count">{{boards|length}} SHOWN</span></div><div class="table-wrap"><table class="board-index"><thead><tr><th>Level</th><th>Platform</th><th>Settings</th><th class="num">Runs</th></tr></thead><tbody>{% for b in boards %}<tr data-search="{{((b.level_name or 'Full game') ~ ' ' ~ b.variant_label)|lower}}" data-platform="{{b.platform_name}}"><td><a href="{{url_for('board',bid=b.board_id)}}">{{b.level_name or 'Full game'}} <span aria-hidden="true">↗</span></a></td><td><span class="platform-pill">{{b.platform_name}}</span></td><td class="settings">{{b.variant_label}}</td><td class="num">{{b.run_count}}</td></tr>{% endfor %}</tbody></table></div><script>const q=document.getElementById('board-filter'),p=document.getElementById('platform-filter'),n=document.getElementById('visible-count');function filterBoards(){let count=0;document.querySelectorAll('.board-index tbody tr').forEach(row=>{let show=row.dataset.search.includes(q.value.toLowerCase())&&(!p.value||row.dataset.platform===p.value);row.hidden=!show;if(show)count++});n.textContent=count+' SHOWN'}q.addEventListener('input',filterBoards);p.addEventListener('change',filterBoards)</script>''',g=games[0],c=cats[0],boards=boards,platforms=platforms)

@app.get('/board/<int:bid>')
def board(bid):
    info=query('''SELECT b.*,g.title_international,c.name category_name,l.name level_name,p.name platform_name,rv.rules_text FROM leaderboard b JOIN category c ON c.category_id=b.category_id JOIN game g ON g.game_id=c.game_id LEFT JOIN level l ON l.level_id=b.level_id JOIN platform p ON p.platform_id=b.platform_id JOIN board_rule_version rv ON rv.board_id=b.board_id AND rv.version_no=(SELECT MAX(version_no) FROM board_rule_version WHERE board_id=b.board_id) WHERE b.board_id=%s''',(bid,))
    if not info: abort(404)
    rows=query('''SELECT r.run_id,u.display_name,r.duration_ms,r.run_date,r.source_url,rs.current_status FROM run r JOIN users u ON u.user_id=r.runner_id JOIN run_status rs ON rs.run_id=r.run_id WHERE r.board_id=%s AND rs.current_status='verified' ORDER BY r.duration_ms,r.run_date''',(bid,))
    best={}
    for r in rows:
        best.setdefault(r['display_name'],r)
    ranked=sorted(best.values(),key=lambda r:(r['duration_ms'],r['run_date']))
    for n,r in enumerate(ranked,1): r['rank']=n; r['time']=format_duration(r['duration_ms'])
    related=query('''SELECT b.board_id,b.variant_description,p.name platform_name,COUNT(r.run_id) run_count FROM leaderboard b JOIN platform p ON p.platform_id=b.platform_id LEFT JOIN run r ON r.board_id=b.board_id WHERE b.category_id=%s AND b.board_id<>%s AND (b.level_id<=>%s) GROUP BY b.board_id ORDER BY run_count DESC LIMIT 12''',(info[0]['category_id'],bid,info[0]['level_id']))
    info[0]['variant_label']=variant_label(info[0]['category_id'],info[0]['variant_description'])
    for x in related: x['variant_label']=variant_label(info[0]['category_id'],x['variant_description'])
    return page('''<div class="breadcrumb"><a href="/">GAMES</a><span>/</span>{{b.title_international|upper}}<span>/</span>{{b.category_name|upper}}</div><section class="page-intro board-intro"><span class="eyebrow">LEADERBOARD / {{b.level_name or 'FULL GAME'}}</span><h1>{{b.title_international}}<span class="title-slash">/</span>{{b.category_name}}</h1><div class="board-meta"><span>{{b.platform_name}}</span><span>{{b.variant_label}}</span></div></section><div class="record-strip"><div><small>TOP TIME</small><strong>{{ranked[0].time if ranked else '—'}}</strong></div><div><small>RANKED RUNNERS</small><strong>{{ranked|length}}</strong></div><p>Runs here share the same platform and settings. Other splits are listed below.</p></div><section class="section-head"><div><span class="eyebrow">01 / STANDINGS</span><h2>Verified runs</h2></div></section><div class="table-wrap"><table class="standings"><thead><tr><th>Rank</th><th>Runner</th><th>Time</th><th>Date</th><th>Evidence</th></tr></thead><tbody>{% for r in ranked %}<tr><td class="rank">{{'%02d'|format(r.rank)}}</td><td class="runner">{{r.display_name}}</td><td class="run-time">{{r.time}}</td><td>{{r.run_date}}</td><td><a href="{{url_for('run_detail',rid=r.run_id)}}">VIEW RUN ↗</a></td></tr>{% endfor %}</tbody></table></div><section class="section-head"><div><span class="eyebrow">02 / OTHER SPLITS</span><h2>Related boards</h2></div></section><div class="table-wrap"><table><thead><tr><th>Platform</th><th>Settings</th><th>Runs</th></tr></thead><tbody>{% for x in related %}<tr><td><a href="{{url_for('board',bid=x.board_id)}}">{{x.platform_name}} ↗</a></td><td>{{x.variant_label}}</td><td>{{x.run_count}}</td></tr>{% endfor %}</tbody></table></div><details><summary>READ CURRENT BOARD RULES</summary><pre>{{b.rules_text}}</pre></details>''',b=info[0],ranked=ranked,related=related)

@app.get('/runs')
def runs():
    status=request.args.get('status','all')
    rows=query('''SELECT r.run_id,g.title_international,c.name category_name,u.display_name,r.duration_ms,r.run_date,rs.current_status FROM run r JOIN leaderboard b ON b.board_id=r.board_id JOIN category c ON c.category_id=b.category_id JOIN game g ON g.game_id=c.game_id JOIN users u ON u.user_id=r.runner_id JOIN run_status rs ON rs.run_id=r.run_id WHERE (%s='all' OR rs.current_status=%s) ORDER BY r.submitted_at DESC LIMIT 100''',(status,status))
    return page((PAGE_TEMPLATES/'runs.html').read_text(encoding='utf-8'),rows=rows,status=status,format_duration=format_duration,verified=sum(r['current_status']=='verified' for r in rows),pending=sum(r['current_status']=='new' for r in rows),rejected=sum(r['current_status']=='rejected' for r in rows),page_class='experience-page runs-page')

@app.get('/run/<rid>')
def run_detail(rid):
    runs=query('''SELECT r.*,rs.current_status,u.display_name,g.title_international,c.name category_name FROM run r JOIN run_status rs ON rs.run_id=r.run_id JOIN users u ON u.user_id=r.runner_id JOIN leaderboard b ON b.board_id=r.board_id JOIN category c ON c.category_id=b.category_id JOIN game g ON g.game_id=c.game_id WHERE r.run_id=%s''',(rid,))
    if not runs: abort(404)
    evidence=query('SELECT * FROM evidence_link WHERE run_id=%s ORDER BY evidence_no',(rid,))
    events=query('SELECT e.*,u.display_name author_name FROM review_event e JOIN users u ON u.user_id=e.author_id WHERE e.run_id=%s ORDER BY e.event_no',(rid,))
    return page((PAGE_TEMPLATES/'run_detail.html').read_text(encoding='utf-8'),r=runs[0],evidence=evidence,events=events,format_duration=format_duration,page_class='experience-page run-detail-page')

@app.get('/reports')
def reports():
    counts=query('''SELECT g.title_international,c.name category_name,COUNT(r.run_id) submissions,COUNT(CASE WHEN rs.current_status='verified' THEN 1 END) verified,COUNT(DISTINCT r.runner_id) runners FROM game g JOIN category c ON c.game_id=g.game_id LEFT JOIN leaderboard b ON b.category_id=c.category_id LEFT JOIN run r ON r.board_id=b.board_id LEFT JOIN run_status rs ON rs.run_id=r.run_id GROUP BY g.game_id,c.category_id ORDER BY g.title_international,c.name''')
    mods=query('''SELECT u.display_name,g.title_international,COUNT(e.event_no) reviews,SUM(e.outcome='verified') verified,SUM(e.outcome='rejected') rejected,ROUND(AVG(TIMESTAMPDIFF(HOUR,r.submitted_at,e.event_at)),1) avg_hours FROM authorizes a JOIN users u ON u.user_id=a.user_id JOIN game g ON g.game_id=a.game_id LEFT JOIN category c ON c.game_id=g.game_id LEFT JOIN leaderboard b ON b.category_id=c.category_id LEFT JOIN run r ON r.board_id=b.board_id LEFT JOIN review_event e ON e.run_id=r.run_id AND e.author_id=u.user_id WHERE a.permission_code='REVIEW_RUNS' GROUP BY u.user_id,g.game_id HAVING reviews>0 ORDER BY reviews DESC LIMIT 30''')
    fastest=query('''SELECT p.name platform,c.name category_name,g.title_international,u.display_name,r.duration_ms best_ms FROM run r JOIN run_status rs ON rs.run_id=r.run_id JOIN leaderboard b ON b.board_id=r.board_id JOIN platform p ON p.platform_id=b.platform_id JOIN category c ON c.category_id=b.category_id JOIN game g ON g.game_id=c.game_id JOIN users u ON u.user_id=r.runner_id WHERE rs.current_status='verified' AND r.duration_ms=(SELECT MIN(r2.duration_ms) FROM run r2 JOIN run_status s2 ON s2.run_id=r2.run_id WHERE r2.board_id=b.board_id AND s2.current_status='verified') ORDER BY g.title_international,c.name,b.board_id LIMIT 30''')
    return page((PAGE_TEMPLATES/'reports.html').read_text(encoding='utf-8'),counts=counts,mods=mods,fastest=fastest,format_duration=format_duration,total_submissions=sum(x['submissions'] for x in counts),total_verified=sum(x['verified'] for x in counts),max_submissions=max((x['submissions'] for x in counts),default=1),page_class='experience-page reports-page')

@app.route('/submit',methods=['GET','POST'])
def submit():
    if request.method=='POST':
        con=db()
        try:
            with con.cursor() as c:
                board_id=int(request.form['board_id']); name=request.form['runner'].strip(); ms=int(request.form['duration_ms']); evidence=request.form['evidence'].strip()
                if not name or ms<=0 or urlparse(evidence).scheme not in ('http','https'): raise ValueError('Provide a runner, positive time in milliseconds, and HTTP(S) evidence.')
                c.execute('SELECT board_id FROM leaderboard WHERE board_id=%s AND active=1',(board_id,))
                if not c.fetchone(): raise ValueError('Choose an active board.')
                c.execute('SELECT user_id FROM users WHERE username=%s',(name,)); user=c.fetchone()
                if user: uid=user['user_id']
                else:
                    uid='local_'+uuid.uuid4().hex[:20]
                    c.execute('INSERT INTO users(user_id,username,display_name,joined_at,is_admin,active) VALUES(%s,%s,%s,NOW(),0,1)',(uid,name,name))
                rid='local_'+uuid.uuid4().hex[:20]
                c.execute('SELECT MAX(version_no) version_no FROM board_rule_version WHERE board_id=%s AND effective_at<=NOW()',(board_id,)); version=c.fetchone()['version_no']
                if not version: raise ValueError('This board has no effective rules.')
                submitted=datetime.now().replace(microsecond=0)
                c.execute('SELECT 1 FROM run_rule WHERE submitted_at=%s AND board_id=%s',(submitted,board_id))
                while c.fetchone():
                    from datetime import timedelta
                    submitted+=timedelta(seconds=1)
                    c.execute('SELECT 1 FROM run_rule WHERE submitted_at=%s AND board_id=%s',(submitted,board_id))
                c.execute('INSERT INTO run_rule VALUES(%s,%s,%s)',(submitted,board_id,version))
                run_date=date.fromisoformat(request.form['run_date'])
                c.execute('INSERT INTO run VALUES(%s,%s,%s,NULL,%s,%s,%s,%s,NULL)',(rid,run_date,ms,uid,uid,submitted,board_id))
                c.execute('INSERT INTO evidence_link VALUES(%s,1,%s,%s,NULL)',(rid,evidence,'video'))
            con.commit(); flash('Run submitted and awaiting review.'); return redirect(url_for('run_detail',rid=rid))
        except (ValueError,pymysql.MySQLError) as exc:
            con.rollback(); flash(str(exc))
        finally: con.close()
    boards=query('''SELECT b.board_id,b.variant_description,c.category_id,g.title_international,c.name category_name,l.name level_name,p.name platform_name FROM leaderboard b JOIN category c ON c.category_id=b.category_id JOIN game g ON g.game_id=c.game_id LEFT JOIN level l ON l.level_id=b.level_id JOIN platform p ON p.platform_id=b.platform_id WHERE b.active=1 ORDER BY g.title_international,c.name''')
    for board in boards: board['variant_label']=variant_label(board['category_id'],board['variant_description'])
    return page((PAGE_TEMPLATES/'submit.html').read_text(encoding='utf-8'),boards=boards,today=date.today().isoformat(),page_class='experience-page submit-page')

@app.post('/review/<rid>')
def review(rid):
    outcome=request.form.get('outcome'); note=request.form.get('note','').strip()
    if outcome not in ('verified','rejected') or (outcome=='rejected' and not note): flash('Rejection requires a reason.'); return redirect(url_for('run_detail',rid=rid))
    con=db()
    try:
        with con.cursor() as c:
            c.execute('''SELECT r.runner_id,r.submitter_id,c.game_id FROM run r JOIN leaderboard b ON b.board_id=r.board_id JOIN category c ON c.category_id=b.category_id WHERE r.run_id=%s FOR UPDATE''',(rid,)); row=c.fetchone()
            c.execute('SELECT current_status FROM run_status WHERE run_id=%s',(rid,)); status=c.fetchone()
            if row and status: row['current_status']=status['current_status']
            if not row or row['current_status']!='new': raise ValueError('Only pending runs can be reviewed.')
            actor='team5_admin'
            if actor in (row['runner_id'],row['submitter_id']): raise ValueError('Self-review is forbidden.')
            c.execute("SELECT 1 FROM authorizes WHERE user_id=%s AND game_id=%s AND permission_code='REVIEW_RUNS'",(actor,row['game_id']))
            if not c.fetchone(): raise ValueError('Reviewer lacks game permission.')
            c.execute('INSERT INTO review_event VALUES(%s,1,NOW(),%s,%s,%s)',(rid,outcome,note or None,actor))
        con.commit(); flash('Review saved.')
    except (ValueError,pymysql.MySQLError) as exc: con.rollback(); flash(str(exc))
    finally: con.close()
    return redirect(url_for('run_detail',rid=rid))

@app.post('/delete/<rid>')
def delete_run(rid):
    con=db()
    try:
        with con.cursor() as c:
            c.execute('SELECT submitted_at,board_id FROM run WHERE run_id=%s FOR UPDATE',(rid,)); row=c.fetchone()
            if not row: raise ValueError('Run missing.')
            c.execute('SELECT 1 FROM review_event WHERE run_id=%s',(rid,))
            if c.fetchone(): raise ValueError('Reviewed runs cannot be deleted.')
            c.execute('DELETE FROM run WHERE run_id=%s',(rid,))
            c.execute('DELETE FROM run_rule WHERE submitted_at=%s AND board_id=%s',(row['submitted_at'],row['board_id']))
        con.commit(); flash('Pending run deleted.'); return redirect(url_for('runs'))
    except (ValueError,pymysql.MySQLError) as exc: con.rollback(); flash(str(exc)); return redirect(url_for('run_detail',rid=rid))
    finally: con.close()

@app.route('/admin',methods=['GET','POST'])
def admin():
    if request.method=='POST':
        con=db()
        try:
            with con.cursor() as c:
                action=request.form['action']
                if action=='game':
                    slug=request.form['slug'].strip(); title=request.form['title'].strip(); cat=request.form['category'].strip(); rules=request.form['rules'].strip()
                    if not all((slug,title,cat,rules)): raise ValueError('All game fields are required.')
                    pid=request.form['platform_id']; gid='local_'+uuid.uuid4().hex[:20]; cid='local_'+uuid.uuid4().hex[:20]
                    c.execute('INSERT INTO game VALUES(%s,%s,%s,NULL,NULL,NULL,1)',(gid,slug,title))
                    c.execute('INSERT INTO category VALUES(%s,%s,%s,1,%s)',(cid,cat,'full_game',gid))
                    c.execute('INSERT INTO supports VALUES(%s,%s)',(gid,pid))
                    c.execute('INSERT INTO leaderboard(board_code,variant_code,variant_description,timing_method,active,category_id,platform_id,level_id) VALUES(%s,%s,%s,%s,1,%s,%s,NULL)',(slug+':standard:'+pid,'standard','Standard','realtime',cid,pid))
                    bid=c.lastrowid
                    c.execute('INSERT INTO board_rule_version VALUES(%s,1,%s,NOW(),NOW())',(bid,rules))
                    for perm in ('REVIEW_RUNS','EDIT_RULES','MANAGE_GAME'): c.execute('INSERT INTO authorizes VALUES(%s,%s,%s)',('team5_admin',gid,perm))
                elif action=='rules':
                    bid=int(request.form['board_id']); rules=request.form['rules'].strip()
                    if not rules: raise ValueError('Rules cannot be empty.')
                    c.execute('SELECT COALESCE(MAX(version_no),0)+1 next_version FROM board_rule_version WHERE board_id=%s FOR UPDATE',(bid,)); n=c.fetchone()['next_version']
                    c.execute('INSERT INTO board_rule_version VALUES(%s,%s,%s,NOW(),NOW())',(bid,n,rules))
                else: raise ValueError('Unknown action.')
            con.commit(); flash('Change saved.')
        except (ValueError,pymysql.MySQLError) as exc: con.rollback(); flash(str(exc))
        finally: con.close()
        return redirect(url_for('admin'))
    boards=query('SELECT b.board_id,g.title_international,c.name category_name FROM leaderboard b JOIN category c ON c.category_id=b.category_id JOIN game g ON g.game_id=c.game_id ORDER BY g.title_international,c.name')
    platforms=query('SELECT * FROM platform ORDER BY name')
    return page((PAGE_TEMPLATES/'admin.html').read_text(encoding='utf-8'),boards=boards,platforms=platforms,page_class='experience-page admin-page')

if __name__=='__main__': app.run(debug=True,host='127.0.0.1',port=5000)


