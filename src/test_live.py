"""Run a short integration smoke test against the local MySQL instance."""
from app import app, db

client=app.test_client()
for path in ('/','/runs','/reports','/admin','/submit'):
    result=client.get(path)
    assert result.status_code==200,(path,result.status_code)

con=db()
with con.cursor() as c:
    c.execute('SELECT board_id FROM leaderboard ORDER BY board_id LIMIT 1')
    board_id=c.fetchone()['board_id']
con.close()

response=client.post('/submit',data={'board_id':board_id,'runner':'Phase4SmokeRunner','duration_ms':'123456','run_date':'2026-11-13','evidence':'https://example.com/smoke'},follow_redirects=False)
assert response.status_code==302,response.status_code
rid=response.headers['Location'].split('/')[-1]
assert client.get('/run/'+rid).status_code==200
response=client.post('/delete/'+rid,follow_redirects=False)
assert response.status_code==302
con=db()
with con.cursor() as c:
    c.execute('SELECT COUNT(*) n FROM run WHERE run_id=%s',(rid,))
    assert c.fetchone()['n']==0
    c.execute('DELETE FROM users WHERE username=%s',('Phase4SmokeRunner',))
con.commit();con.close()
print('Live MySQL smoke test passed: five pages, run create, detail, and delete')
