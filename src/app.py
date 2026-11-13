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

SHELL='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Speedrun Atlas / Team 18</title><link rel="stylesheet" href="{{url_for('static',filename='site.css')}}"></head><body class="{{page_class}}">
<header class="site-header"><div class="header-inner"><a class="brand" href="{{'/preview' if preview else '/'}}" aria-label="Speedrun Atlas home"><span class="brand-mark">S<span>/</span>A</span><span class="brand-name">SPEEDRUN<br>ATLAS</span></a><nav aria-label="Main navigation">{% if preview %}<a href="/preview" class="active">Games</a>{% else %}<a href="/" class="{{'active' if endpoint in ['home','game','category','board'] else ''}}">Games</a><a href="/runs" class="{{'active' if endpoint in ['runs','run_detail'] else ''}}">Runs</a><a href="/reports" class="{{'active' if endpoint=='reports' else ''}}">Reports</a><a href="/submit" class="{{'active' if endpoint=='submit' else ''}}">Submit</a><a href="/admin" class="{{'active' if endpoint=='admin' else ''}}">Manage</a>{% endif %}</nav><span class="header-tag">TEAM 18 / DATABASE PROJECT</span></div></header>
<div class="signal-bar" aria-label="Site status"><span class="signal-live"><i aria-hidden="true"></i> SYSTEM ONLINE</span><span class="signal-flow">SPEEDRUN ATLAS <b>//</b> THREE GAMES <b>//</b> VERIFIED RUNS <b>//</b> EVERY SECOND COUNTS</span><span class="signal-end">TEAM 18 / PHASE 4</span></div>
<main>{% with messages=get_flashed_messages() %}{% for m in messages %}<div class="msg">{{m}}</div>{% endfor %}{% endwith %}{{ body|safe }}</main>
<footer><span>SPEEDRUN ATLAS</span><span>TEAM 18 &nbsp; / &nbsp; DATA & APPLICATIONS</span></footer></body></html>'''
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
    art={'celeste':'game-art/celeste.webp','sm64':'game-art/sm64-custom.png','smb1':'game-art/smb1-custom.png'}
    return page('''<section class="hero"><div class="eyebrow"><span class="live-dot"></span> THE LEADERBOARD INDEX</div><h1>Every second<br><em class="glitch-word" data-text="counts.">counts.</em></h1><div class="hero-bottom"><p>Explore verified runs, compare records, and follow the rules behind each leaderboard.</p><div class="hero-stat"><strong>{{total}}</strong><span>BOARDS<br>INDEXED</span></div></div></section><section class="section-head"><div><span class="eyebrow">01 / DISCOVER</span><h2>Games</h2></div><span class="section-count">{{games|length}} TITLES</span></section><div class="game-list">{% for g in games %}<a class="game-row" href="{{url_for('game',gid=g.game_id)}}">{% if art.get(g.slug) %}<img class="game-art" src="{{url_for('static',filename=art[g.slug])}}" alt="" loading="lazy">{% endif %}<span class="game-number">{{'%02d'|format(loop.index)}}</span><span class="game-title">{{g.title_international}}<small>{{g.slug|upper}} &nbsp;·&nbsp; {{g.release_year or 'YEAR UNKNOWN'}}</small></span><span class="game-boards">{{g.boards}} <small>BOARDS</small></span><span class="game-arrow" aria-hidden="true">↗</span></a>{% else %}<p class="empty">No games are available.</p>{% endfor %}</div>''',games=games,total=total,art=art)

@app.get('/game/<gid>')
def game(gid):
    games=query('SELECT * FROM game WHERE game_id=%s',(gid,))
    if not games: abort(404)
    categories=query('''SELECT c.category_id,c.name,c.kind,COUNT(DISTINCT b.board_id) board_count,COUNT(r.run_id) run_count FROM category c LEFT JOIN leaderboard b ON b.category_id=c.category_id LEFT JOIN run r ON r.board_id=b.board_id WHERE c.game_id=%s GROUP BY c.category_id ORDER BY c.kind,c.name''',(gid,))
    art={'celeste':'game-art/celeste.webp','sm64':'game-art/sm64-custom.png','smb1':'game-art/smb1-custom.png'}.get(games[0]['slug'])
    if games[0]['slug']=='celeste':
        return page('''<div class="breadcrumb"><a href="/">GAMES</a><span>/</span>CELESTE</div><section class="celeste-stage"><div class="celeste-orbit" aria-hidden="true"></div><div class="celeste-wordmark" aria-hidden="true">CELESTE</div><div class="celeste-copy"><span class="eyebrow"><span class="live-dot"></span> FEATURED GAME / 2018</span><h1>CLIMB.<br><em>RESET.</em><br>REPEAT.</h1><p>One mountain. A thousand ways to race it. Pick your category and chase the fastest verified time.</p></div><img class="celeste-sticker" src="{{url_for('static',filename='game-art/celeste-character.png')}}" alt="Madeline leaping upward"><aside class="celeste-rail" aria-label="Celeste categories"><div class="celeste-rail-head"><span>01 / CHOOSE YOUR ROUTE</span><strong>{{categories|length}} CATEGORIES</strong></div><div class="celeste-rail-scroll" tabindex="0" aria-label="Scroll Celeste categories">{% for c in categories %}<a class="celeste-rail-item" href="{{url_for('category',gid=g.game_id,cid=c.category_id)}}"><span class="celeste-rail-index">{{'%02d'|format(loop.index)}}</span><span class="celeste-rail-info"><strong>{{c.name}}</strong><small>{{'FULL GAME' if c.kind=='full_game' else 'LEVEL RUNS'}}</small><span class="celeste-rail-reveal"><b>{{c.run_count}} RUNS</b><b>{{c.board_count}} BOARDS</b></span></span><span class="celeste-rail-arrow" aria-hidden="true">↗</span></a>{% endfor %}</div><div class="celeste-rail-foot">SCROLL FOR MORE <span aria-hidden="true">↓</span></div></aside><div class="celeste-stats"><span>CELESTE <b>/</b> SPEEDRUN ATLAS</span><strong>{{categories|length}} <small>CATEGORIES</small></strong><strong>{{total_runs}} <small>RUNS INDEXED</small></strong></div></section><div class="celeste-source"><span>KEEP CLIMBING.</span><a href="{{g.source_url}}" target="_blank" rel="noopener noreferrer">ORIGINAL GAME PAGE ↗</a></div>''',g=games[0],categories=categories,total_runs=sum(c['run_count'] for c in categories),page_class='celeste-page')
    return page('''<div class="breadcrumb"><a href="/">GAMES</a><span>/</span>{{g.slug|upper}}</div><section class="page-intro game-intro">{% if art %}<img class="game-intro-art" src="{{url_for('static',filename=art)}}" alt="">{% endif %}<span class="eyebrow">GAME PROFILE / {{g.release_year or 'YEAR UNKNOWN'}}</span><h1>{{g.title_international}}</h1><p><a class="external" href="{{g.source_url}}" target="_blank" rel="noopener noreferrer">ORIGINAL GAME PAGE ↗</a></p></section><section class="section-head"><div><span class="eyebrow">02 / CHOOSE A CATEGORY</span><h2>Categories</h2></div><span class="section-count">{{categories|length}} CATEGORIES</span></section><p class="muted">Choose a category, then find the platform and settings you want.</p><div class="category-list">{% for c in categories %}<a class="category-row" href="{{url_for('category',gid=g.game_id,cid=c.category_id)}}"><span class="category-number">{{'%02d'|format(loop.index)}}</span><span class="category-title">{{c.name}}<small>{{'FULL GAME' if c.kind=='full_game' else 'LEVEL RUNS'}}</small></span><span class="category-count">{{c.board_count}} <small>BOARDS</small></span><span class="category-count">{{c.run_count}} <small>RUNS</small></span><span class="category-arrow" aria-hidden="true">↗</span></a>{% else %}<p class="empty">No categories available.</p>{% endfor %}</div>''',g=games[0],categories=categories,art=art)

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
    return page('''<section class="page-intro"><span class="eyebrow">RUN ARCHIVE / {{rows|length}} SHOWN</span><h1>Every run.<br>One record.</h1><p class="muted">Browse submitted times and their review status.</p></section><section class="section-head"><div><span class="eyebrow">01 / BROWSE</span><h2>Submissions</h2></div></section><form class="filter-form" method="get"><label for="status">REVIEW STATUS</label><select id="status" name="status">{% for s in ['all','new','verified','rejected'] %}<option {{'selected' if s==status else ''}}>{{s}}</option>{% endfor %}</select><button>APPLY FILTER ↗</button></form><div class="table-wrap"><table><thead><tr><th>Game / category</th><th>Runner</th><th>Time</th><th>Status</th></tr></thead><tbody>{% for r in rows %}<tr><td><a href="{{url_for('run_detail',rid=r.run_id)}}">{{r.title_international}} / {{r.category_name}} ↗</a></td><td>{{r.display_name}}</td><td class="mono">{{format_duration(r.duration_ms)}}</td><td><span class="status status-{{r.current_status}}">{{r.current_status}}</span></td></tr>{% else %}<tr><td colspan="4">No runs in this view.</td></tr>{% endfor %}</tbody></table></div>''',rows=rows,status=status,format_duration=format_duration)

@app.get('/run/<rid>')
def run_detail(rid):
    runs=query('''SELECT r.*,rs.current_status,u.display_name,g.title_international,c.name category_name FROM run r JOIN run_status rs ON rs.run_id=r.run_id JOIN users u ON u.user_id=r.runner_id JOIN leaderboard b ON b.board_id=r.board_id JOIN category c ON c.category_id=b.category_id JOIN game g ON g.game_id=c.game_id WHERE r.run_id=%s''',(rid,))
    if not runs: abort(404)
    evidence=query('SELECT * FROM evidence_link WHERE run_id=%s ORDER BY evidence_no',(rid,))
    events=query('SELECT e.*,u.display_name author_name FROM review_event e JOIN users u ON u.user_id=e.author_id WHERE e.run_id=%s ORDER BY e.event_no',(rid,))
    return page('''<h1>{{r.title_international}} / {{r.category_name}}</h1><div class="panel"><p><b>{{r.display_name}}</b> · {{'%.3f'|format(r.duration_ms/1000)}}s · {{r.current_status}}</p><p>Run date {{r.run_date}} · Submitted {{r.submitted_at}}</p>{% for e in evidence %}<p><a href="{{e.url}}" target="_blank">Evidence {{e.evidence_no}}</a></p>{% endfor %}{% for e in events %}<p>{{e.outcome}} by {{e.author_name}} at {{e.event_at}} {{e.note or ''}}</p>{% endfor %}</div>{% if r.current_status=='new' %}<form method="post" action="{{url_for('review',rid=r.run_id)}}"><label>Decision <select name="outcome"><option>verified</option><option>rejected</option></select></label><label>Reason for rejection <input name="note"></label><button>Save review</button></form><form method="post" action="{{url_for('delete_run',rid=r.run_id)}}" onsubmit="return confirm('Delete this untouched pending run?')"><button>Delete pending run</button></form>{% endif %}''',r=runs[0],evidence=evidence,events=events)

@app.get('/reports')
def reports():
    counts=query('''SELECT g.title_international,c.name category_name,COUNT(r.run_id) submissions,COUNT(CASE WHEN rs.current_status='verified' THEN 1 END) verified,COUNT(DISTINCT r.runner_id) runners FROM game g JOIN category c ON c.game_id=g.game_id LEFT JOIN leaderboard b ON b.category_id=c.category_id LEFT JOIN run r ON r.board_id=b.board_id LEFT JOIN run_status rs ON rs.run_id=r.run_id GROUP BY g.game_id,c.category_id ORDER BY g.title_international,c.name''')
    mods=query('''SELECT u.display_name,g.title_international,COUNT(e.event_no) reviews,SUM(e.outcome='verified') verified,SUM(e.outcome='rejected') rejected,ROUND(AVG(TIMESTAMPDIFF(HOUR,r.submitted_at,e.event_at)),1) avg_hours FROM authorizes a JOIN users u ON u.user_id=a.user_id JOIN game g ON g.game_id=a.game_id LEFT JOIN category c ON c.game_id=g.game_id LEFT JOIN leaderboard b ON b.category_id=c.category_id LEFT JOIN run r ON r.board_id=b.board_id LEFT JOIN review_event e ON e.run_id=r.run_id AND e.author_id=u.user_id WHERE a.permission_code='REVIEW_RUNS' GROUP BY u.user_id,g.game_id HAVING reviews>0 ORDER BY reviews DESC LIMIT 30''')
    fastest=query('''SELECT p.name platform,c.name category_name,g.title_international,u.display_name,r.duration_ms best_ms FROM run r JOIN run_status rs ON rs.run_id=r.run_id JOIN leaderboard b ON b.board_id=r.board_id JOIN platform p ON p.platform_id=b.platform_id JOIN category c ON c.category_id=b.category_id JOIN game g ON g.game_id=c.game_id JOIN users u ON u.user_id=r.runner_id WHERE rs.current_status='verified' AND r.duration_ms=(SELECT MIN(r2.duration_ms) FROM run r2 JOIN run_status s2 ON s2.run_id=r2.run_id WHERE r2.board_id=b.board_id AND s2.current_status='verified') ORDER BY g.title_international,c.name,b.board_id LIMIT 30''')
    return page('''<section class="page-intro"><span class="eyebrow">DATA DESK / LIVE FROM THE DATABASE</span><h1>Inside the<br>numbers.</h1><p class="muted">Activity across games, runners, and moderator reviews.</p></section><section class="section-head"><div><span class="eyebrow">01 / PARTICIPATION</span><h2>Game and category activity</h2></div></section><div class="table-wrap"><table><thead><tr><th>Game</th><th>Category</th><th>Submitted</th><th>Verified</th><th>Runners</th></tr></thead><tbody>{% for x in counts %}<tr><td>{{x.title_international}}</td><td>{{x.category_name}}</td><td class="mono">{{x.submissions}}</td><td class="mono">{{x.verified}}</td><td class="mono">{{x.runners}}</td></tr>{% endfor %}</tbody></table></div><section class="section-head"><div><span class="eyebrow">02 / REVIEW</span><h2>Moderator activity</h2></div></section><div class="table-wrap"><table><thead><tr><th>Moderator</th><th>Game</th><th>Reviews</th><th>Verified</th><th>Rejected</th><th>Average hours</th></tr></thead><tbody>{% for x in mods %}<tr><td>{{x.display_name}}</td><td>{{x.title_international}}</td><td class="mono">{{x.reviews}}</td><td class="mono">{{x.verified}}</td><td class="mono">{{x.rejected}}</td><td class="mono">{{x.avg_hours}}</td></tr>{% endfor %}</tbody></table></div><section class="section-head"><div><span class="eyebrow">03 / PERFORMANCE</span><h2>Fastest by platform</h2></div></section><p class="muted">Times are directly comparable only within the same leaderboard and settings.</p><div class="table-wrap"><table><thead><tr><th>Game</th><th>Category</th><th>Platform</th><th>Runner</th><th>Time</th></tr></thead><tbody>{% for x in fastest %}<tr><td>{{x.title_international}}</td><td>{{x.category_name}}</td><td>{{x.platform}}</td><td>{{x.display_name}}</td><td class="mono">{{format_duration(x.best_ms)}}</td></tr>{% endfor %}</tbody></table></div>''',counts=counts,mods=mods,fastest=fastest,format_duration=format_duration)

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
    boards=query('''SELECT b.board_id,g.title_international,c.name category_name,l.name level_name,p.name platform_name FROM leaderboard b JOIN category c ON c.category_id=b.category_id JOIN game g ON g.game_id=c.game_id LEFT JOIN level l ON l.level_id=b.level_id JOIN platform p ON p.platform_id=b.platform_id WHERE b.active=1 ORDER BY g.title_international,c.name LIMIT 300''')
    return page('''<section class="page-intro"><span class="eyebrow">SUBMIT / CHASE THE CLOCK</span><h1>Got a time?<br>Put it up.</h1><p class="muted">Send a run to the review queue with a link to its evidence.</p></section><div class="form-layout"><form method="post" class="editor-form"><span class="eyebrow">01 / RUN DETAILS</span><label>Leaderboard <select name="board_id">{% for b in boards %}<option value="{{b.board_id}}">{{b.title_international}} / {{b.category_name}} / {{b.level_name or 'Full game'}} / {{b.platform_name}}</option>{% endfor %}</select></label><label>Runner name <input name="runner" required placeholder="Your display name"></label><label>Duration in milliseconds <input type="number" name="duration_ms" min="1" required placeholder="For example, 5272000"></label><label>Run date <input type="date" name="run_date" value="{{today}}"></label><label>Evidence URL <input type="url" name="evidence" required placeholder="https://..."></label><button>SUBMIT FOR REVIEW ↗</button></form><aside class="form-aside"><span class="eyebrow">HOW IT WORKS</span><div><strong>01</strong><p>Choose the exact leaderboard for your game, category, platform, and settings.</p></div><div><strong>02</strong><p>Enter the time in milliseconds and provide a video or other evidence link.</p></div><div><strong>03</strong><p>The run appears in the queue until a moderator reviews it.</p></div><small>This local demo creates a runner profile from the name you enter.</small></aside></div>''',boards=boards,today=date.today().isoformat())

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
    boards=query('SELECT b.board_id,g.title_international,c.name category_name FROM leaderboard b JOIN category c ON c.category_id=b.category_id JOIN game g ON g.game_id=c.game_id ORDER BY g.title_international,c.name LIMIT 300')
    platforms=query('SELECT * FROM platform ORDER BY name')
    return page('''<section class="page-intro"><span class="eyebrow">CONTROL ROOM / DATABASE TOOLS</span><h1>Manage the<br>boards.</h1><p class="muted">Add a game or publish a new version of leaderboard rules.</p></section><div class="admin-grid"><section class="editor-form"><span class="eyebrow">01 / NEW GAME</span><h2>Add game and category</h2><form method="post"><input type="hidden" name="action" value="game"><label>Slug <input name="slug" required></label><label>Title <input name="title" required></label><label>Initial full game category <input name="category" required></label><label>Platform <select name="platform_id">{% for p in platforms %}<option value="{{p.platform_id}}">{{p.name}}</option>{% endfor %}</select></label><label>Rules <textarea name="rules" required></textarea></label><button>CREATE GAME ↗</button></form></section><section class="editor-form"><span class="eyebrow">02 / RULES VERSION</span><h2>Update board rules</h2><form method="post"><input type="hidden" name="action" value="rules"><label>Board <select name="board_id">{% for b in boards %}<option value="{{b.board_id}}">{{b.title_international}} / {{b.category_name}} / {{b.board_id}}</option>{% endfor %}</select></label><label>New rules <textarea name="rules" required></textarea></label><button>PUBLISH VERSION ↗</button></form></section></div>''',boards=boards,platforms=platforms)

if __name__=='__main__': app.run(debug=True,host='127.0.0.1',port=5000)
