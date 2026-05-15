from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import os
import httpx
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

METRIKA_COUNTER = os.getenv("METRIKA_COUNTER", "")
FOLDER_LINK     = os.getenv("FOLDER_LINK", "https://t.me/addlist/REPLACE_ME")

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

@app.get("/events")
async def events():
    conn = get_db()
    rows = conn.execute("SELECT * FROM events ORDER BY id DESC LIMIT 100").fetchall()
    conn.close()
    return JSONResponse([dict(r) for r in rows])

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
