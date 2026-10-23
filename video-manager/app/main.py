"""영상 관리 사이트 — 서버 본체"""

import hmac
import time
from pathlib import Path
from typing import Optional

import httpx
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from . import config, db

STATIC = Path(__file__).resolve().parent / "static"
THUMB_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
MAX_THUMB = 5 * 1024 * 1024

app = FastAPI(title="영상 관리", docs_url=None, redoc_url=None)
app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY,
                   max_age=60 * 60 * 24 * 30, same_site="lax", https_only=False)


@app.on_event("startup")
def _start():
    db.conn()
    db.seed_if_empty()


def _same(a, b):
    return bool(a) and bool(b) and hmac.compare_digest(a.encode(), b.encode())


def need_user(request: Request):
    """브라우저(로그인 쿠키) 또는 PC(열쇠) 둘 중 하나면 통과"""
    if request.session.get("ok"):
        return "web"
    auth = request.headers.get("authorization", "")
    token = auth[7:] if auth.lower().startswith("bearer ") else request.headers.get("x-token", "")
    if _same(token, config.API_TOKEN):
        return "pc"
    raise HTTPException(401, "로그인이 필요합니다")


# ---------------------------------------------------------------- 화면

@app.get("/")
def home(request: Request):
    if not request.session.get("ok"):
        return RedirectResponse("/login")
    return FileResponse(STATIC / "index.html")


@app.get("/login")
def login_page():
    return FileResponse(STATIC / "login.html")


_tries = {}


@app.post("/login")
def login(request: Request, password: str = Form(...)):
    ip = request.client.host if request.client else "?"
    recent = [t for t in _tries.get(ip, []) if time.time() - t < 600]
    if len(recent) >= 10:
        return RedirectResponse("/login?e=many", status_code=303)
    if not config.ADMIN_PASSWORD or not _same(password, config.ADMIN_PASSWORD):
        _tries[ip] = recent + [time.time()]
        return RedirectResponse("/login?e=1", status_code=303)
    _tries.pop(ip, None)
    request.session["ok"] = True
    return RedirectResponse("/", status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login")


app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/thumbs/{name}")
def thumb(name: str, _=Depends(need_user)):
    path = (config.THUMB_DIR / name).resolve()
    if path.parent != config.THUMB_DIR.resolve() or not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, headers={"Cache-Control": "private, max-age=86400"})


# ---------------------------------------------------------------- 기본 정보

@app.get("/api/meta")
def meta(_=Depends(need_user)):
    return {"channels": config.CHANNELS, "steps": config.STEPS, "states": config.STEP_STATES,
            "today": db.today(), "youtube_stats": bool(config.YT_API_KEY)}


# ---------------------------------------------------------------- 편

@app.get("/api/episodes")
def list_episodes(channel: Optional[str] = None, _=Depends(need_user)):
    return db.episodes(config.channel_key(channel) if channel else None)


@app.post("/api/episodes")
async def add_episode(request: Request, _=Depends(need_user)):
    body = await request.json()
    ch = config.channel_key(body.get("channel"))
    if not ch:
        raise HTTPException(400, "채널을 골라 주세요")
    ep = int(body.get("ep") or db.next_ep(ch))
    if db.episode_by(ch, ep):
        raise HTTPException(409, f"{ep}편은 이미 있습니다")
    e = db.create_episode(ch, ep, date=body.get("date", ""))
    if body.get("start"):
        db.add_queue("진행", e["id"], f"{_name(ch)} {ep}편 새로 시작")
    db.add_log(f"{_name(ch)} {ep}편을 {body.get('date') or '날짜 미정'}에 넣었습니다")
    return e


@app.get("/api/episodes/{eid}")
def get_episode(eid: int, _=Depends(need_user)):
    e = db.episode(eid)
    if not e:
        raise HTTPException(404)
    return e


@app.patch("/api/episodes/{eid}")
async def patch_episode(eid: int, request: Request, _=Depends(need_user)):
    e = db.update_episode(eid, await request.json())
    if not e:
        raise HTTPException(404)
    return e


@app.delete("/api/episodes/{eid}")
def remove_episode(eid: int, _=Depends(need_user)):
    e = db.episode(eid)
    if e:
        db.delete_episode(eid)
        db.add_log(f"{_name(e['channel'])} {e['ep']}편을 지웠습니다")
    return {"ok": True}


async def _save_thumb(e, file: UploadFile):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in THUMB_TYPES:
        raise HTTPException(400, "jpg, png, webp 그림만 올릴 수 있습니다")
    data = await file.read()
    if len(data) > MAX_THUMB:
        raise HTTPException(400, "그림이 5MB를 넘습니다")
    name = f"{e['channel']}-{e['ep']}-{int(time.time())}{ext}"
    (config.THUMB_DIR / name).write_bytes(data)
    old = e.get("thumb")
    if old and (config.THUMB_DIR / old).is_file():
        (config.THUMB_DIR / old).unlink()
    return db.update_episode(e["id"], {"thumb": name})


@app.post("/api/episodes/{eid}/thumbnail")
async def upload_thumb(eid: int, file: UploadFile = File(...), _=Depends(need_user)):
    e = db.episode(eid)
    if not e:
        raise HTTPException(404)
    return await _save_thumb(e, file)


@app.post("/api/episodes/{eid}/run")
def run_episode(eid: int, _=Depends(need_user)):
    e = db.episode(eid)
    if not e:
        raise HTTPException(404)
    return db.add_queue("진행", eid, f"{_name(e['channel'])} {e['ep']}편 진행")


@app.post("/api/episodes/{eid}/edit")
async def edit_request(eid: int, request: Request, _=Depends(need_user)):
    """제목·설명·썸네일 문구를 고쳐 두고, PC에게 '실제로 반영해' 를 시킵니다."""
    e = db.episode(eid)
    if not e:
        raise HTTPException(404)
    body = await request.json()
    text = {k: body.get(k) for k in ("title", "description", "thumb_lines", "date") if k in body}
    changed = [n for k, n in (("title", "제목"), ("description", "설명"),
                              ("thumb_lines", "썸네일 문구"), ("date", "공개 날짜"))
               if k in text and text[k] != e.get(k)]
    db.update_episode(eid, text)
    if not changed:
        return {"ok": True, "changed": []}
    item = db.add_queue("글고침", eid, f"{_name(e['channel'])} {e['ep']}편 {' · '.join(changed)} 고치기",
                        {"changed": changed, **text})
    return {"ok": True, "changed": changed, "queue": item}


@app.post("/api/episodes/{eid}/approve")
def approve(eid: int, _=Depends(need_user)):
    """검토 대기 편을 승인 → PC가 비공개 영상을 공개 날짜에 맞춰 예약 공개로 바꿈"""
    e = db.episode(eid)
    if not e:
        raise HTTPException(404)
    db.update_episode(eid, {"review": "승인"})
    db.add_log(f"{_name(e['channel'])} {e['ep']}편을 승인했습니다 (예약 공개로 바꾸기를 PC에게 시킴)")
    return db.add_queue("승인", eid, f"{_name(e['channel'])} {e['ep']}편 승인 — 예약 공개로 바꾸기",
                        {"video_id": e.get("video_id"), "date": e.get("date")})


@app.post("/api/episodes/{eid}/redo")
async def redo(eid: int, request: Request, _=Depends(need_user)):
    """검토해 보니 마음에 안 듦 → PC가 이유를 보고 다시 만듦"""
    e = db.episode(eid)
    if not e:
        raise HTTPException(404)
    body = await request.json()
    why = str(body.get("note", "")).strip()[:500]
    db.update_episode(eid, {"review": "다시만들기"})
    db.add_log(f"{_name(e['channel'])} {e['ep']}편 다시 만들기를 시켰습니다" + (f" — {why}" if why else ""))
    return db.add_queue("다시만들기", eid, f"{_name(e['channel'])} {e['ep']}편 다시 만들기", {"note": why, "video_id": e.get("video_id")})


# ---------------------------------------------------------------- PC 보고 (보고.py 가 씁니다)

@app.post("/api/report")
async def report(request: Request, _=Depends(need_user)):
    """채널+편 번호로 찾아서 있으면 고치고 없으면 만듭니다."""
    body = await request.json()
    ch = config.channel_key(body.pop("channel", None))
    ep = body.pop("ep", None)
    if not ch or not ep:
        raise HTTPException(400, "channel 과 ep 가 필요합니다")
    e = db.episode_by(ch, int(ep)) or db.create_episode(ch, int(ep))
    log = body.pop("log", None)
    e = db.update_episode(e["id"], body)
    if log:
        db.add_log(f"{_name(ch)} {ep}편 — {log}")
    return e


@app.post("/api/report/thumbnail")
async def report_thumb(channel: str = Form(...), ep: int = Form(...),
                       file: UploadFile = File(...), _=Depends(need_user)):
    ch = config.channel_key(channel)
    if not ch:
        raise HTTPException(400, "그런 채널이 없습니다")
    e = db.episode_by(ch, ep) or db.create_episode(ch, ep)
    return await _save_thumb(e, file)


# ---------------------------------------------------------------- 시킨 일

@app.get("/api/queue")
def list_queue(state: Optional[str] = None, _=Depends(need_user)):
    items = db.queue(state)
    eps = {e["id"]: e for e in db.episodes()}
    for it in items:
        e = eps.get(it["episode_id"])
        it["episode"] = {"channel": e["channel"], "ep": e["ep"], "date": e["date"]} if e else None
    return items


@app.post("/api/queue")
async def add_queue(request: Request, _=Depends(need_user)):
    body = await request.json()
    kind = body.get("kind")
    if kind not in ("이어서", "멈춤", "진행", "글고침", "메모", "승인", "다시만들기"):
        raise HTTPException(400, "모르는 일입니다")
    return db.add_queue(kind, body.get("episode_id"), body.get("label", kind), body.get("payload"))


@app.patch("/api/queue/{qid}")
async def patch_queue(qid: int, request: Request, _=Depends(need_user)):
    body = await request.json()
    return db.update_queue(qid, body.get("state"), body.get("note"))


@app.delete("/api/queue/{qid}")
def remove_queue(qid: int, _=Depends(need_user)):
    db.delete_queue(qid)
    return {"ok": True}


# ---------------------------------------------------------------- PC 상태 · 기록

@app.get("/api/status")
def get_status(_=Depends(need_user)):
    return db.get_status()


@app.put("/api/status")
async def put_status(request: Request, _=Depends(need_user)):
    return db.set_status(await request.json())


@app.get("/api/log")
def get_log(_=Depends(need_user)):
    return db.logs()


@app.post("/api/log")
async def post_log(request: Request, _=Depends(need_user)):
    text = (await request.json()).get("text", "").strip()
    if text:
        db.add_log(text)
    return {"ok": True}


# ---------------------------------------------------------------- 유튜브 조회수

@app.post("/api/youtube/refresh")
def refresh_stats(_=Depends(need_user)):
    if not config.YT_API_KEY:
        raise HTTPException(400, "YT_API_KEY 가 설정되어 있지 않습니다")
    eps = [e for e in db.episodes() if e.get("video_id")]
    found = 0
    for i in range(0, len(eps), 50):
        chunk = eps[i:i + 50]
        r = httpx.get("https://www.googleapis.com/youtube/v3/videos", timeout=20, params={
            "part": "statistics,status", "id": ",".join(e["video_id"] for e in chunk),
            "key": config.YT_API_KEY})
        if r.status_code != 200:
            raise HTTPException(502, f"유튜브 응답 오류: {r.text[:200]}")
        got = {it["id"]: it for it in r.json().get("items", [])}
        for e in chunk:
            it = got.get(e["video_id"])
            if not it:
                continue
            st = it.get("statistics", {})
            db.update_episode(e["id"], {
                "views": int(st.get("viewCount", 0)), "likes": int(st.get("likeCount", 0)),
                "privacy": it.get("status", {}).get("privacyStatus", ""), "stats_at": db.now()})
            found += 1
    return {"ok": True, "updated": found, "total": len(eps)}


def _name(ch):
    return next((c["name"] for c in config.CHANNELS if c["key"] == ch), ch)
