from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import sqlite3
import os
import secrets
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FOLDER_LINK    = os.getenv("FOLDER_LINK", "https://t.me/addlist/REPLACE_ME")
DASH_LOGIN     = os.getenv("DASH_LOGIN", "toplivo")
DASH_PASSWORD  = os.getenv("DASH_PASSWORD", "fuel2026")

security = HTTPBasic()

def check_auth(credentials: HTTPBasicCredentials = Depends(security)):
    ok_login    = secrets.compare_digest(credentials.username, DASH_LOGIN)
    ok_password = secrets.compare_digest(credentials.password, DASH_PASSWORD)
    if not (ok_login and ok_password):
        raise HTTPException(status_code=401, headers={"WWW-Authenticate": "Basic"})
    return True

def get_db():
    conn = sqlite3.connect("events.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            event      TEXT,
            tg_id      TEXT,
            username   TEXT,
            first_name TEXT,
            utm        TEXT,
            ts         INTEGER,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

@app.get("/", response_class=HTMLResponse)
async def root():
    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read()
    html = html.replace("FOLDER_LINK_PLACEHOLDER", FOLDER_LINK)
    html = html.replace("TRACK_URL_PLACEHOLDER", "")
    return HTMLResponse(content=html)

@app.post("/track")
async def track(request: Request):
    try:
        data = await request.json()
    except:
        return JSONResponse({"ok": False}, status_code=400)

    conn = get_db()
    conn.execute(
        "INSERT INTO events (event, tg_id, username, first_name, utm, ts, created_at) VALUES (?,?,?,?,?,?,?)",
        (
            data.get("event", ""),
            str(data.get("tg_id", "")),
            data.get("username", ""),
            data.get("first_name", ""),
            data.get("utm", ""),
            data.get("ts", 0),
            datetime.utcnow().isoformat()
        )
    )
    conn.commit()
    conn.close()
    return JSONResponse({"ok": True})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(auth: bool = Depends(check_auth)):
    conn = get_db()

    # Всего событий
    total = conn.execute("SELECT COUNT(*) FROM events WHERE event='folder_click'").fetchone()[0]

    # По UTM
    by_utm = conn.execute("""
        SELECT utm, COUNT(*) as cnt
        FROM events WHERE event='folder_click'
        GROUP BY utm ORDER BY cnt DESC
    """).fetchall()

    # По дням
    by_day = conn.execute("""
        SELECT substr(created_at,1,10) as day, COUNT(*) as cnt
        FROM events WHERE event='folder_click'
        GROUP BY day ORDER BY day DESC LIMIT 30
    """).fetchall()

    # Последние 50 пользователей
    users = conn.execute("""
        SELECT created_at, first_name, username, tg_id, utm
        FROM events WHERE event='folder_click'
        ORDER BY id DESC LIMIT 50
    """).fetchall()

    conn.close()

    # Данные для графика
    days_labels = [r['day'] for r in reversed(list(by_day))]
    days_values = [r['cnt'] for r in reversed(list(by_day))]

    utm_rows = ""
    for r in by_utm:
        utm_label = r['utm'] if r['utm'] else 'прямой заход'
        utm_rows += f"<tr><td>{utm_label}</td><td><b>{r['cnt']}</b></td></tr>"

    user_rows = ""
    for u in users:
        username = f"@{u['username']}" if u['username'] else "—"
        utm_label = u['utm'] if u['utm'] else "—"
        date = u['created_at'][:16].replace('T', ' ')
        user_rows += f"<tr><td>{date}</td><td>{u['first_name'] or '—'}</td><td>{username}</td><td>{u['tg_id']}</td><td>{utm_label}</td></tr>"

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Дашборд — Топливо Папка</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family: -apple-system, sans-serif; background: #0f172a; color: #e2e8f0; padding: 24px; }}
  h1 {{ font-size: 24px; font-weight: 700; margin-bottom: 4px; }}
  .sub {{ color: #64748b; font-size: 14px; margin-bottom: 32px; }}
  .cards {{ display: flex; gap: 16px; margin-bottom: 32px; flex-wrap: wrap; }}
  .card {{ background: #1e293b; border-radius: 16px; padding: 24px 28px; flex: 1; min-width: 160px; }}
  .card .num {{ font-size: 48px; font-weight: 800; color: #3b82f6; line-height: 1; }}
  .card .label {{ font-size: 13px; color: #64748b; margin-top: 6px; }}
  .section {{ background: #1e293b; border-radius: 16px; padding: 24px; margin-bottom: 24px; }}
  .section h2 {{ font-size: 16px; font-weight: 600; margin-bottom: 16px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  th {{ text-align: left; color: #64748b; font-weight: 500; padding: 8px 12px; border-bottom: 1px solid #334155; }}
  td {{ padding: 10px 12px; border-bottom: 1px solid #1e293b; }}
  tr:hover td {{ background: #0f172a; }}
  .chart-wrap {{ max-height: 220px; }}
</style>
</head>
<body>

<h1>📊 Дашборд папки</h1>
<div class="sub">Топливо Недвижимости · обновляется в реальном времени</div>

<div class="cards">
  <div class="card">
    <div class="num">{total}</div>
    <div class="label">Всего добавлений папки</div>
  </div>
  <div class="card">
    <div class="num">{len(by_utm)}</div>
    <div class="label">Уникальных UTM источников</div>
  </div>
</div>

<div class="section">
  <h2>По дням</h2>
  <div class="chart-wrap">
    <canvas id="chart"></canvas>
  </div>
</div>

<div class="section">
  <h2>По UTM источникам</h2>
  <table>
    <tr><th>Источник</th><th>Добавлений</th></tr>
    {utm_rows}
  </table>
</div>

<div class="section">
  <h2>Последние пользователи</h2>
  <table>
    <tr><th>Дата</th><th>Имя</th><th>Username</th><th>TG ID</th><th>UTM</th></tr>
    {user_rows}
  </table>
</div>

<script>
new Chart(document.getElementById('chart'), {{
  type: 'bar',
  data: {{
    labels: {days_labels},
    datasets: [{{
      data: {days_values},
      backgroundColor: '#3b82f6',
      borderRadius: 6,
    }}]
  }},
  options: {{
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ ticks: {{ color: '#64748b' }}, grid: {{ color: '#1e293b' }} }},
      y: {{ ticks: {{ color: '#64748b', stepSize: 1 }}, grid: {{ color: '#334155' }} }}
    }}
  }}
}});
</script>
</body>
</html>"""

    return HTMLResponse(content=html)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
