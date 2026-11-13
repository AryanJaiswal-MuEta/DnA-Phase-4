(() => {
  const room=document.querySelector('.tv-room');
  if(!room)return;
  const app=document.getElementById('tv-app'),title=document.getElementById('tv-title'),status=document.getElementById('tv-status'),detail=document.getElementById('tv-detail');
  const cassettes=[...document.querySelectorAll('.game-cassette')];
  const state={game:null,category:null,board:null,run:null};
  const esc=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const safeUrl=value=>{try{const url=new URL(value);return ['https:','http:'].includes(url.protocol)?url.href:null}catch{return null}};
  const request=async path=>{const response=await fetch(path,{headers:{Accept:'application/json'}});if(!response.ok)throw Error(`Could not load this screen (${response.status}).`);return response.json()};
  function artwork(id){document.querySelectorAll('.tv-preview').forEach(img=>img.classList.toggle('is-visible',img.dataset.game===id))}
  function preview(cassette){if(state.game)return;const id=cassette?.dataset.game;room.classList.toggle('is-previewing',!!cassette);artwork(id);title.textContent=cassette?cassette.dataset.title:'READY PLAYER ONE';status.textContent=cassette?'GAME DETECTED':'SELECT A CASSETTE';detail.textContent=cassette?`${cassette.dataset.boards} BOARDS · CLICK TO LOAD`:'3 GAMES · SELECT TO LOAD'}
  function screen(step,heading,meta,body,back){
    room.classList.remove('is-loading');room.classList.add('has-game');
    app.hidden=false;app.innerHTML=`<div class="tv-app-head"><button class="tv-back" type="button" data-back="${back}" aria-label="Go back">←</button><span>${esc(step)}</span><small>${esc(meta)}</small></div><h2>${esc(heading)}</h2><div class="tv-app-content">${body}</div>`;
    app.querySelector('.tv-app-content').scrollTop=0;
  }
  function error(message){room.classList.remove('is-loading');app.hidden=false;room.classList.add('has-game');app.innerHTML=`<div class="tv-error">${esc(message)}<button type="button" data-back="game">TRY AGAIN ↶</button></div>`}
  async function showGame(id){
    try{const data=await request(`/api/tv/game/${encodeURIComponent(id)}`);state.game=data.game;state.category=null;state.board=null;state.run=null;artwork(id);
      const items=data.categories.map((c,i)=>`<button type="button" class="tv-choice" data-category="${esc(c.category_id)}"><b>${String(i+1).padStart(2,'0')}</b><span><strong>${esc(c.name)}</strong><small>${c.kind==='full_game'?'FULL GAME':'LEVEL RUNS'} · ${c.board_count} BOARDS · ${c.run_count} RUNS</small></span><i>↗</i></button>`).join('');
      screen('01 / SELECT CATEGORY',data.game.title_international,`${data.categories.length} ROUTES`,items||'<p>No categories yet.</p>','library');
      cassettes.forEach(c=>c.classList.toggle('is-inserted',c.dataset.game===id));
    }catch(e){error(e.message)}
  }
  async function showCategory(id){
    try{const data=await request(`/api/tv/category/${encodeURIComponent(id)}`);state.category=data.category;state.board=null;state.run=null;
      const items=data.boards.map((b,i)=>`<button type="button" class="tv-choice" data-board="${b.board_id}"><b>${String(i+1).padStart(2,'0')}</b><span><strong>${esc(b.level)} / ${esc(b.platform)}</strong><small>${esc(b.settings)} · ${b.runs} RUNS</small></span><i>↗</i></button>`).join('');
      screen('02 / SELECT BOARD',data.category.name,`${data.boards.length} BOARDS`,items||'<p>No boards yet.</p>','game');
    }catch(e){error(e.message)}
  }
  async function showBoard(id){
    try{const data=await request(`/api/tv/board/${encodeURIComponent(id)}`);state.board=data.board;state.run=null;
      const items=data.runs.map(r=>`<button type="button" class="tv-choice tv-run-choice ${r.rank<=3?`tv-podium tv-podium-${r.rank}`:''}" data-run="${esc(r.run_id)}"><b>${String(r.rank).padStart(2,'0')}</b><span><strong>${esc(r.runner)}</strong><small>${esc(r.date)}</small></span><em>${esc(r.time)}</em></button>`).join('');
      const rules=data.board.rules?`<details class="tv-rules"><summary>BOARD RULES</summary><p>${esc(data.board.rules)}</p></details>`:'';
      screen('03 / LEADERBOARD',`${data.board.category} / ${data.board.level}`,`${data.board.platform} · ${data.runs.length} RUNNERS`,`<div class="tv-board-settings">${esc(data.board.settings)}</div>${items||'<p>No verified runs on this board yet.</p>'}${rules}`,'category');
    }catch(e){error(e.message)}
  }
  async function showRun(id){
    try{const data=await request(`/api/tv/run/${encodeURIComponent(id)}`);state.run=data.run;
      const links=data.evidence.map((e,i)=>{const url=safeUrl(e.url);return url?`<a class="tv-evidence" href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(e.label||e.kind||`EVIDENCE ${i+1}`)} ↗</a>`:''}).join('');
      const source=safeUrl(data.run.source_url);
      screen('04 / RUN DETAIL',data.run.runner,esc(data.run.status).toUpperCase(),`<div class="tv-run-time">${esc(data.run.time)}</div><div class="tv-run-meta">${esc(data.run.game)} / ${esc(data.run.category)}<br>${esc(data.run.date)}</div>${links}${source?`<a class="tv-evidence" href="${esc(source)}" target="_blank" rel="noopener noreferrer">ORIGINAL RUN ↗</a>`:''}`,'board');
    }catch(e){error(e.message)}
  }
  function library(){state.game=null;state.category=null;state.board=null;state.run=null;room.classList.remove('has-game','is-loading');app.hidden=true;app.innerHTML='';cassettes.forEach(c=>{c.classList.remove('is-inserted');c.style.visibility='' });preview(null)}
  app.addEventListener('click',event=>{const button=event.target.closest('button');if(!button)return;
    if(button.dataset.category)showCategory(button.dataset.category);
    else if(button.dataset.board)showBoard(button.dataset.board);
    else if(button.dataset.run)showRun(button.dataset.run);
    else if(button.dataset.back==='library')library();
    else if(button.dataset.back==='game'&&state.game)showGame(state.game.game_id);
    else if(button.dataset.back==='category'&&state.category)showCategory(state.category.category_id);
    else if(button.dataset.back==='board'&&state.board)showBoard(state.board.board_id);
  });
  cassettes.forEach(cassette=>{
    cassette.addEventListener('mouseenter',()=>preview(cassette));cassette.addEventListener('focus',()=>preview(cassette));
    cassette.addEventListener('mouseleave',()=>preview(null));cassette.addEventListener('blur',()=>preview(null));
    cassette.addEventListener('click',event=>{
      if(event.defaultPrevented||event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;
      event.preventDefault();if(room.classList.contains('is-loading'))return;
      const id=cassette.dataset.game;preview(cassette);
      if(matchMedia('(prefers-reduced-motion: reduce)').matches){showGame(id);return}
      room.classList.add('is-loading');status.textContent='LOADING GAME';
      const rect=cassette.getBoundingClientRect(),slot=document.querySelector('.tv-slot').getBoundingClientRect();
      const clone=cassette.cloneNode(true);clone.classList.add('cassette-flying');clone.style.cssText=`left:${rect.left}px;top:${rect.top}px;width:${rect.width}px;height:${rect.height}px`;
      document.body.append(clone);
      requestAnimationFrame(()=>requestAnimationFrame(()=>{clone.style.transform=`translate(${slot.left+slot.width/2-rect.left-rect.width/2}px,${slot.top+slot.height/2-rect.top-rect.height/2}px) rotate(-90deg) scale(.2)`;clone.style.opacity='0'}));
      setTimeout(()=>{clone.remove();showGame(id)},780);
    });
  });
})();
