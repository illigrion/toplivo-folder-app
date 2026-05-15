from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import os
import httpx
import json
from datetime import datetime

app = FastAPI()

# CORS — разрешаем запросы из Telegram Mini App
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Папка для статики (index.html)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Конфиг из переменных окружения
METRIKA_COUNTER = os.getenv("METRIKA_COUNTER", "")
METRIKA_TOKEN   = os.getenv("METRIKA_TOKEN", "")
FOLDER_LINK     = os.getenv("FOLDER_LINK", "")

# База данных
def get_db():
    conn = sqlite3.connect("events.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            event     TEXT,
            tg_id     TEXT,
            username  TEXT,
            first_name TEXT,
            utm       TEXT,
            ts        INTEGER,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# Главная страница — отдаём Mini App
@app.get("/", response_class=HTMLResponse)
async def root():
    with open("static/index.html", "r", encoding="utf-8") as f:
        html = f.read()
    # Подставляем реальные значения
    html = html.replace("FOLDER_LINK_PLACEHOLDER", FOLDER_LINK)
    html = html.replace("TRACK_URL_PLACEHOLDER", "")  # пустой = relative URL
    return HTMLResponse(content=html)

# Трекинг события
@app.post("/track")
async def track(request: Request):
    try:
        data = await request.json()
    except:
        return JSONResponse({"ok": False, "error": "bad json"}, status_code=400)

    event     = data.get("event", "unknown")
    tg_id     = str(data.get("tg_id", ""))
    username  = data.get("username", "")
    first_name = data.get("first_name", "")
    utm       = data.get("utm", "")
    ts        = data.get("ts", 0)

    # Сохраняем в БД
    conn = get_db()
    conn.execute(
        "INSERT INTO events (event, tg_id, username, first_name, utm, ts, created_at) VALUES (?,?,?,?,?,?,?)",
        (event, tg_id, username, first_name, utm, ts, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()

    # Отправляем в Яндекс.Метрику (Measurement Protocol)
    if METRIKA_COUNTER and METRIKA_TOKEN:
        await send_to_metrika(event, tg_id, utm)

    return JSONResponse({"ok": True})

async def send_to_metrika(event: str, tg_id: str, utm: str):
    """Передаём оффлайн-конверсию в Яндекс.Метрику"""
    try:
        # Парсим UTM параметры из startapp строки
        # Формат: source_campaign_content
        parts = utm.split("_") if utm else []
        utm_source   = parts[0] if len(parts) > 0 else "telegram"
        utm_campaign = parts[1] if len(parts) > 1 else ""

        url = f"https://mc.yandex.ru/watch/{METRIKA_COUNTER}"
        params = {
            "id": METRIKA_COUNTER,
            "t": "reachGoal",
            "goal-id": event,       # folder_click или folder_confirmed
            "rn": tg_id,
        }
        async with httpx.AsyncClient() as client:
            await client.get(url, params=params, timeout=5)
    except Exception as e:
        print(f"Metrika error: {e}")

# Список событий (для отладки)
@app.get("/events")
async def events():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM events ORDER BY id DESC LIMIT 100"
    ).fetchall()
    conn.close()
    return JSONResponse([dict(r) for r in rows])

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
