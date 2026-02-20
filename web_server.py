import asyncio
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from proxy_manager import ProxyManager
from browser_manager import BrowserManager

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger("WebServer")

import sys

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

app = FastAPI()

STATIC_DIR = Path(resource_path("static"))
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

class BotState:
    def __init__(self):
        self.manager: Optional[BrowserManager] = None
        self.proxy_manager: Optional[ProxyManager] = None
        self.task: Optional[asyncio.Task] = None
        self.running = False
        self.start_time: Optional[float] = None
        self.channel = ""
        self.max_concurrent = 5
        self.logs: list[dict] = []
        self.connected_clients: set[WebSocket] = set()
        self.viewers_active = 0
        self.viewers_playing = 0
        self.viewers_failed = 0

state = BotState()

class WSLogHandler(logging.Handler):
    def emit(self, record):
        msg = self.format(record)
        log_entry = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "message": msg,
            "level": record.levelname.lower(),
        }
        state.logs.append(log_entry)
        if len(state.logs) > 200:
            state.logs = state.logs[-200:]

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(broadcast({"type": "log", "data": log_entry}))
        except RuntimeError:
            pass

ws_handler = WSLogHandler()
ws_handler.setFormatter(logging.Formatter('%(message)s'))

for logger_name in ["BrowserViewer", "BrowserManager", "ProxyManager", "WebServer"]:
    lg = logging.getLogger(logger_name)
    lg.addHandler(ws_handler)
    lg.setLevel(logging.INFO)

async def broadcast(message: dict):
    dead = set()
    data = json.dumps(message)
    for ws in state.connected_clients:
        try:
            await ws.send_text(data)
        except:
            dead.add(ws)
    state.connected_clients -= dead

async def stats_loop():
    while True:
        if state.running and state.manager:
            uptime = int(time.time() - state.start_time) if state.start_time else 0
            hours, remainder = divmod(uptime, 3600)
            minutes, seconds = divmod(remainder, 60)

            viewers = state.manager.viewers
            active = len(viewers)

            await broadcast({
                "type": "stats",
                "data": {
                    "status": "running" if state.running else "idle",
                    "channel": state.channel,
                    "uptime": f"{hours:02d}:{minutes:02d}:{seconds:02d}",
                    "viewers_active": active,
                    "proxies_total": state.proxy_manager.total_count if state.proxy_manager else 0,
                    "max_concurrent": state.max_concurrent,
                }
            })
        else:
            await broadcast({
                "type": "stats",
                "data": {
                    "status": "idle",
                    "channel": state.channel,
                    "uptime": "00:00:00",
                    "viewers_active": 0,
                    "proxies_total": 0,
                    "max_concurrent": state.max_concurrent,
                }
            })
        await asyncio.sleep(2)

@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    state.connected_clients.add(ws)
    logger.info("Client connected")

    await ws.send_text(json.dumps({
        "type": "init",
        "data": {
            "status": "running" if state.running else "idle",
            "channel": state.channel,
            "max_concurrent": state.max_concurrent,
            "logs": state.logs[-50:],
            "proxies": _get_proxy_list(),
        }
    }))

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            await handle_message(ws, msg)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        state.connected_clients.discard(ws)
        logger.info("Client disconnected")

async def handle_message(ws: WebSocket, msg: dict):
    action = msg.get("action")

    if action == "start":
        channel = msg.get("channel", "").strip()
        max_c = msg.get("max_concurrent", 5)
        if not channel:
            await ws.send_text(json.dumps({"type": "error", "data": "Channel name is required"}))
            return
        await start_bot(channel, max_c)

    elif action == "stop":
        await stop_bot()

    elif action == "get_proxies":
        await ws.send_text(json.dumps({
            "type": "proxies",
            "data": _get_proxy_list()
        }))

    elif action == "save_settings":
        state.max_concurrent = msg.get("max_concurrent", 5)
        proxies_text = msg.get("proxies", "")
        if proxies_text:
            proxy_path = Path("proxylist.txt")
            proxy_path.write_text(proxies_text, encoding="utf-8")
            logger.info(f"Proxy list saved ({len(proxies_text.splitlines())} proxies)")
        await broadcast({"type": "settings_saved"})

async def start_bot(channel: str, max_concurrent: int):
    if state.running:
        logger.warning("Bot is already running")
        return

    state.channel = channel
    state.max_concurrent = max_concurrent
    state.running = True
    state.start_time = time.time()

    proxy_file = "proxylist.txt"
    state.proxy_manager = ProxyManager(proxy_file)

    channel_url = f"https://www.twitch.tv/{channel}"
    state.manager = BrowserManager(channel_url, state.proxy_manager, max_concurrent)

    logger.info(f"Starting bot: channel={channel}, max_concurrent={max_concurrent}")
    await broadcast({"type": "status", "data": "running"})

    state.task = asyncio.create_task(_run_bot())

async def _run_bot():
    try:
        await state.manager.start()
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Bot error: {e}")
    finally:
        state.running = False
        state.start_time = None
        await broadcast({"type": "status", "data": "idle"})
        logger.info("Bot stopped")

async def stop_bot():
    if not state.running:
        return

    logger.info("Stopping bot...")
    state.running = False

    if state.manager:
        await state.manager.stop()

    if state.task:
        state.task.cancel()
        try:
            await state.task
        except asyncio.CancelledError:
            pass
        state.task = None

    state.start_time = None
    await broadcast({"type": "status", "data": "idle"})

def _get_proxy_list() -> list[dict]:
    proxies = []
    proxy_path = Path("proxylist.txt")
    if proxy_path.exists():
        for line in proxy_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(":")
            display = f"{parts[0]}:{parts[1]}" if len(parts) >= 2 else line
            proxies.append({
                "raw": line,
                "display": display,
                "status": "ready",
            })
    return proxies

@app.on_event("startup")
async def on_startup():
    asyncio.create_task(stats_loop())
    logger.info("TWBT Web Server started on http://localhost:8080")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web_server:app", host="0.0.0.0", port=8080, reload=False)
