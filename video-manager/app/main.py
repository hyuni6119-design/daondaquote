"""영상 관리 사이트 — 서버 본체"""

import hmac
import time
from pathlib import Path
from typing import Optional

import httpx
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from . import config, db
from .uploads import make_router

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


app.include_router(make_router(need_user))  # 사이트에서 직접 올리기 (uploads.py)


# ---------------------------------------------------------------- 화면

def _page(name):
    """화면 파일을 줄 때 app.js·style.css 주소에 고친 시각을 붙임 — 브라우저가 예전 파일을 기억해 화면이 깨지는 일 방지"""
    html = (STATIC / name).read_text(encoding="utf-8")
    for f in ("style.css", "app.js"):
        v = int((STATIC / f).stat().st_mtime)
        html = html.replace(f'/static/{f}"', f'/static/{f}?v={v}"')
    return HTMLResponse(html, headers={"Cache-Control": "no-cache"})


@app.get("/")
def home(request: Request):
    if not request.session.get("ok"):
        return RedirectResponse("/login")
    return _page("index.html")


@app.get("/login")
def login_page():
    return _page("login.html")


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

@app.post("/api/channels")
async def add_channel(request: Request, _=Depends(need_user)):
    b = await request.json()
    name = str(b.get("name") or "").strip()[:40]
    if not name:
        raise HTTPException(400, "채널 이름을 써 주세요")
    if any(c["name"] == name for c in config.CHANNELS):
        raise HTTPException(409, "같은 이름의 채널이 이미 있습니다")
    color = str(b.get("color") or "#7c5cff")[:9]
    c = db.add_channel(name, str(b.get("display") or "").strip()[:60], color)
    db.add_log(f"채널 ‘{name}’을 넣었습니다")
    return c


@app.patch("/api/channels/{key}")
async def patch_channel(key: str, request: Request, _=Depends(need_user)):
    if not any(c["key"] == key for c in config.CHANNELS):
        raise HTTPException(404)
    b = await request.json()
    return db.update_channel(key, {k: str(b.get(k) or "").strip()[:60] for k in ("name", "display", "color")})


@app.get("/api/rules")
def get_rules(_=Depends(need_user)):
    """채널마다 만들기 규칙 · 제목 규칙"""
    return {c["key"]: db.rules(c["key"]) for c in config.CHANNELS}


@app.put("/api/rules/{key}")
async def put_rules(key: str, request: Request, _=Depends(need_user)):
    if not any(c["key"] == key for c in config.CHANNELS):
        raise HTTPException(404)
    body = await request.json()
    r = db.set_rules(key, body)
    if "songs" in body:
        db.add_log(f"{_name(key)} 만들기 규칙을 바꿨습니다 (곡 {r['songs']}개 × {r['loops']}바퀴 · {r['min_minutes']}~{r['max_minutes']}분)")
    else:
        db.add_log(f"{_name(key)} 프롬프트를 바꿨습니다")
    return r


@app.get("/api/refs")
def get_refs(_=Depends(need_user)):
    return db.refs()


@app.post("/api/refs")
async def post_ref(request: Request, _=Depends(need_user)):
    b = await request.json()
    url = str(b.get("url") or "").strip()[:300]
    if not url:
        raise HTTPException(400, "채널 주소를 넣어 주세요")
    item = db.add_ref(url, str(b.get("note") or "").strip()[:500])
    db.add_log(f"레퍼런스 채널 분석을 맡겼습니다: {url}")
    return item


@app.patch("/api/refs/{rid}")
async def patch_ref(rid: int, request: Request, _=Depends(need_user)):
    r = db.update_ref(rid, await request.json())
    if not r:
        raise HTTPException(404)
    return r


@app.post("/api/refs/{rid}/retry")
def retry_ref(rid: int, _=Depends(need_user)):
    r = db.update_ref(rid, {"state": "요청", "error": ""})
    if not r:
        raise HTTPException(404)
    return r


@app.post("/api/refs/{rid}/apply/{key}")
def apply_ref(rid: int, key: str, _=Depends(need_user)):
    """분석 결과 프롬프트를 이 채널 프롬프트로 넣음 (넣은 뒤 프롬프트 메뉴에서 고칠 수 있음)"""
    r = db.ref(rid)
    if not r or r.get("state") != "완료":
        raise HTTPException(404)
    if not any(c["key"] == key for c in config.CHANNELS):
        raise HTTPException(404)
    res = r.get("result") or {}
    src = (r.get("channel") or {}).get("title") or r["url"]
    names = db.ref_names_of(r)
    me = next((c.get("display") or c["name"] for c in config.CHANNELS if c["key"] == key), key)
    data = {k: db.swap_names(res.get(k, ""), names, me) for k in ("title_rules", "desc_rules", "examples", "thumb_prompt", "image_prompt", "lyrics_prompt")}
    data["ref_note"] = src
    data["ref_names"] = ",".join(n for n in names if n)
    out = db.set_rules(key, data)
    db.add_log(f"{_name(key)} 프롬프트를 레퍼런스 ‘{src}’ 분석 결과로 바꿨습니다")
    return out


@app.post("/api/refs/{rid}/sample")
async def sample_ref(rid: int, request: Request, _=Depends(need_user)):
    """분석 결과 프롬프트로 예시 한 편(제목·설명·곡 목록·가사·썸네일 문구)을 시험으로 만들어 봄"""
    r = db.ref(rid)
    if not r or r.get("state") != "완료":
        raise HTTPException(404)
    b = await request.json()
    return db.update_ref(rid, {"sample_state": "요청", "sample_error": "", "sample_topic": str(b.get("topic") or "").strip()[:200]})


@app.get("/api/lyrics")
def get_lyrics(_=Depends(need_user)):
    return db.lyric_jobs()


@app.post("/api/lyrics")
async def post_lyrics(request: Request, _=Depends(need_user)):
    """참고 가사 → 수노용 스타일·새 가사·가사 프롬프트 (서버 일꾼이 1분 안에 씀)"""
    b = await request.json()
    ref = str(b.get("ref_lyrics") or "").strip()[:8000]
    if not ref:
        raise HTTPException(400, "참고 가사를 넣어 주세요")
    item = db.add_lyric_job({"ref_lyrics": ref, "topic": str(b.get("topic") or "").strip()[:300],
                             "channel": str(b.get("channel") or "")[:10], "title": str(b.get("title") or "").strip()[:100]})
    db.add_log("수노 가사 만들기를 맡겼습니다" + (f" ({item['title']})" if item["title"] else ""))
    return item


@app.patch("/api/lyrics/{jid}")
async def patch_lyrics(jid: int, request: Request, _=Depends(need_user)):
    r = db.update_lyric_job(jid, await request.json())
    if not r:
        raise HTTPException(404)
    return r


@app.post("/api/lyrics/{jid}/retry")
async def retry_lyrics(jid: int, request: Request, _=Depends(need_user)):
    b = await request.json()
    data = {"state": "요청", "error": ""}
    if "topic" in b:
        data["topic"] = str(b.get("topic") or "").strip()[:300]
    r = db.update_lyric_job(jid, data)
    if not r:
        raise HTTPException(404)
    return r


@app.post("/api/lyrics/{jid}/apply/{key}")
def apply_lyrics(jid: int, key: str, _=Depends(need_user)):
    """만든 가사 프롬프트를 이 채널의 가사 프롬프트로 넣음"""
    r = db.lyric_job(jid)
    if not r or r.get("state") != "완료" or not any(c["key"] == key for c in config.CHANNELS):
        raise HTTPException(404)
    out = db.set_rules(key, {"lyrics_prompt": (r.get("result") or {}).get("lyrics_prompt", "")})
    db.add_log(f"{_name(key)} 가사 프롬프트를 ‘수노 가사 만들기’ 결과로 바꿨습니다")
    return out


@app.delete("/api/lyrics/{jid}")
def del_lyrics(jid: int, _=Depends(need_user)):
    db.delete_lyric_job(jid)
    return {"ok": True}


@app.post("/api/refs/{rid}/save")
async def save_ref(rid: int, request: Request, _=Depends(need_user)):
    """💾 분석 결과를 📚 레퍼런스 채널로 저장"""
    r = db.ref(rid)
    if not r or r.get("state") != "완료":
        raise HTTPException(404)
    b = await request.json()
    name = str(b.get("name") or (r.get("channel") or {}).get("title") or r["url"]).strip()[:80]
    item = db.save_ref(r, name)
    db.add_log(f"레퍼런스 채널 ‘{name}’을 저장했습니다")
    return item


@app.get("/api/saved-refs")
def get_saved_refs(_=Depends(need_user)):
    return db.saved_refs()


@app.patch("/api/saved-refs/{sid}")
async def patch_saved_ref(sid: int, request: Request, _=Depends(need_user)):
    r = db.update_saved_ref(sid, await request.json())
    if not r:
        raise HTTPException(404)
    return r


@app.delete("/api/saved-refs/{sid}")
def del_saved_ref(sid: int, _=Depends(need_user)):
    db.delete_saved_ref(sid)
    for c in config.CHANNELS:  # 이걸 쓰던 채널은 표시만 지움 (프롬프트는 그대로)
        if db.rules(c["key"]).get("ref_id") == sid:
            db.set_rules(c["key"], {"ref_id": 0})
    return {"ok": True}


@app.post("/api/saved-refs/{sid}/apply/{key}")
def apply_saved_ref(sid: int, key: str, _=Depends(need_user)):
    """이 채널의 레퍼런스를 바꿈 → 제목·설명·예시·썸네일·영상 그림·가사 프롬프트를 이 레퍼런스 것으로"""
    r = db.saved_ref(sid)
    if not r or not any(c["key"] == key for c in config.CHANNELS):
        raise HTTPException(404)
    res = r.get("result") or {}
    names = db.ref_names_of(r)
    me = next((c.get("display") or c["name"] for c in config.CHANNELS if c["key"] == key), key)
    # 느낌만 가져오고 이름은 우리 채널 것으로
    data = {k: db.swap_names(res.get(k, ""), names, me) for k in ("title_rules", "desc_rules", "examples", "thumb_prompt", "image_prompt", "lyrics_prompt")}
    data.update({"ref_id": sid, "ref_note": r["name"], "ref_names": ",".join(n for n in names if n)})
    out = db.set_rules(key, data)
    db.add_log(f"{_name(key)} 레퍼런스 채널을 ‘{r['name']}’로 바꿨습니다")
    return out


@app.delete("/api/refs/{rid}")
def del_ref(rid: int, _=Depends(need_user)):
    db.delete_ref(rid)
    return {"ok": True}


@app.get("/api/system")
def get_system(_=Depends(need_user)):
    """서버 일꾼이 1분마다 적는 상태 (채널 연결 · 유튜브 사용량 · 저장 공간 · 마지막 실행)"""
    return db.kv_get("system", {}) or {}


@app.put("/api/system")
async def put_system(request: Request, who=Depends(need_user)):
    if who != "pc":
        raise HTTPException(403)
    return db.kv_set("system", await request.json())


@app.post("/api/episodes/{eid}/make")
async def make_update(eid: int, request: Request, _=Depends(need_user)):
    """🎬 새 영상 만들기: 주제·단계 체크를 고치거나 AI 일(job: thumb=썸네일 프롬프트, songs=곡 목록·가사)을 맡김"""
    e = db.episode(eid)
    if not e:
        raise HTTPException(404)
    b = await request.json()
    mk = dict(e.get("make") or {})
    if "topic" in b:
        mk["topic"] = str(b.get("topic") or "").strip()[:300]
    if isinstance(b.get("done"), dict):
        mk["done"] = {**(mk.get("done") or {}), **{str(k)[:20]: bool(v) for k, v in b["done"].items()}}
    if isinstance(b.get("song_done"), dict):
        mk["song_done"] = {**(mk.get("song_done") or {}), **{str(k)[:5]: bool(v) for k, v in b["song_done"].items()}}
    if b.get("job") in ("thumb", "songs"):
        mk.setdefault("jobs", {})[b["job"]] = {"state": "요청", "error": ""}
    if isinstance(b.get("pc"), dict):  # 🌙 PC 밤 작업 진행 상황 (밤작업.py 가 적음)
        mk["pc"] = {"state": str(b["pc"].get("state") or "")[:20], "note": str(b["pc"].get("note") or "")[:300], "at": db.now()}
    if b.get("job") == "image":  # 🖼 썸네일 그림 AI (고른 모델 · 유료)
        mk.setdefault("jobs", {})["image"] = {"state": "요청", "error": "", "model": str(b.get("model") or "gpt-image-1-mini")[:40],
                                            "quality": b.get("quality") if b.get("quality") in ("low", "medium", "high") else "medium"}
    if b.get("job") == "all":  # ✨ 한 번에 다 만들기: 주제 → 썸네일 → 곡 목록 → 제목·설명 → 가사
        mk.setdefault("jobs", {})["all"] = {"state": "요청", "error": "", "stage": "topic", "keep_topic": bool(mk.get("topic"))}
    return db.update_episode(eid, {"make": mk})


@app.post("/api/episodes/{eid}/ai")
def ai_request(eid: int, _=Depends(need_user)):
    """이 편의 제목 후보 3개 · 설명 첫머리를 AI에게 (서버 일꾼이 1분 안에 씀)"""
    if not db.episode(eid):
        raise HTTPException(404)
    return db.update_episode(eid, {"ai_state": "요청", "ai_note": ""})


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
    """검토 대기 편을 승인 → 서버 일꾼(라이브 관리자 tools/vm-upload.js)이 1분 안에 공개 날짜 21:00 예약 공개로 바꿈"""
    e = db.episode(eid)
    if not e:
        raise HTTPException(404)
    db.update_episode(eid, {"review": "승인"})
    db.add_log(f"{_name(e['channel'])} {e['ep']}편을 승인했습니다 (1분 안에 {e.get('date') or '공개 날짜'} 21:00 예약 공개로 바뀝니다)")
    return db.add_queue("승인", eid, f"{_name(e['channel'])} {e['ep']}편 승인 — 예약 공개로 바꾸기",
                        {"video_id": e.get("video_id"), "date": e.get("date")})


@app.post("/api/episodes/{eid}/redo")
async def redo(eid: int, request: Request, _=Depends(need_user)):
    """검토해 보니 마음에 안 듦 → PC가 예전 영상을 삭제하고 이유를 보고 다시 만듦"""
    e = db.episode(eid)
    if not e:
        raise HTTPException(404)
    body = await request.json()
    why = str(body.get("note", "")).strip()[:500]
    db.update_episode(eid, {"review": "다시만들기"})
    db.add_log(f"{_name(e['channel'])} {e['ep']}편 다시 만들기를 시켰습니다" + (f" — {why}" if why else ""))
    return db.add_queue("다시만들기", eid, f"{_name(e['channel'])} {e['ep']}편 다시 만들기 (예전 영상 삭제)", {"note": why, "video_id": e.get("video_id")})


REVIEW_PARTS = ("썸네일", "제목", "설명", "영상")


@app.post("/api/episodes/{eid}/review")
async def review_done(eid: int, request: Request, _=Depends(need_user)):
    """검토 완료: 썸네일 · 제목 · 설명 · 영상을 하나씩 OK / 고치기로 체크
    - 모두 OK → 승인 (예약 공개)
    - 영상이 별로 → 다시만들기 (예전 영상 삭제 후 새로 올림)
    - 영상은 괜찮고 썸네일·제목·설명만 별로 → 고치기 (같은 영상에서 그것만 바꿈)"""
    e = db.episode(eid)
    if not e:
        raise HTTPException(404)
    body = await request.json()
    checks = body.get("checks") or {}
    notes = body.get("notes") or {}
    bad = [p for p in REVIEW_PARTS if checks.get(p) is False]
    if any(checks.get(p) is None for p in REVIEW_PARTS):
        raise HTTPException(400, "썸네일 · 제목 · 설명 · 영상을 모두 체크해 주세요")
    fix = {p: str(notes.get(p, "")).strip()[:500] for p in bad}
    name = f"{_name(e['channel'])} {e['ep']}편"
    if not bad:
        return approve(eid)
    if "영상" in bad:
        db.update_episode(eid, {"review": "다시만들기"})
        db.add_log(f"{name} 다시 만들기를 시켰습니다 — " + " · ".join(f"{p}: {n or '별로'}" for p, n in fix.items()))
        return db.add_queue("다시만들기", eid, f"{name} 다시 만들기 (예전 영상 삭제)",
                            {"fix": fix, "note": " / ".join(f"{p}: {n}" for p, n in fix.items() if n), "video_id": e.get("video_id")})
    db.update_episode(eid, {"review": "고치는중"})
    db.add_log(f"{name} {' · '.join(bad)} 고치기를 시켰습니다 (영상은 그대로)")
    return db.add_queue("고치기", eid, f"{name} {' · '.join(bad)} 고치기 (영상은 그대로)",
                        {"fix": fix, "video_id": e.get("video_id"), "date": e.get("date")})


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
    if kind not in ("이어서", "멈춤", "진행", "글고침", "메모", "승인", "다시만들기", "고치기"):
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
