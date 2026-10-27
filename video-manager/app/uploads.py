"""사이트에서 직접 올리기 — 영상 파일을 조각으로 받아 두고, 서버의 올리기 일꾼이 유튜브로 보냅니다.

흐름
  1. 새 올리기 만들기 (채널 · 공개 날짜 · 파일 크기)          POST /api/uploads
  2. 영상 파일을 조각(8MB)으로 받기 — 끊기면 이어서 받음      PUT  /api/uploads/{id}/video?offset=
  3. 썸네일 · 수록곡.json 넣기, 제목·설명·태그 쓰기 (AI 초안)  POST /api/uploads/{id}/thumb · /chapters · /draft, PATCH
  4. 「유튜브로 올리기」 → 대기                                POST /api/uploads/{id}/go
  5. 라이브 관리자 서버의 일꾼(tools/vm-upload.js)이 일부 공개로 올리고 편에 붙임 → 검토대기
파일은 UPLOAD_DIR(/srv/vm-uploads)/<번호>/ 에 두고, 유튜브에 올린 뒤 일꾼이 지웁니다.
"""

import json
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from . import config, db

MAX_VIDEO = 8 * 1024 ** 3          # 8GB (100분짜리도 넉넉)
MAX_CHUNK = 64 * 1024 ** 2
IMG = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}

# 사용자가 바꿀 수 있는 칸 · 일꾼만 바꾸는 칸
USER_FIELDS = {"title", "description", "tags", "date"}
WORKER_FIELDS = USER_FIELDS | {"state", "progress", "youtube_id", "error", "draft", "draft_note", "episode_id"}


def make_router(need_user):
    r = APIRouter(prefix="/api/uploads")

    def get(uid):
        u = db.upload(uid)
        if not u:
            raise HTTPException(404, "그런 올리기가 없습니다")
        return u

    def folder(uid):
        p = config.UPLOAD_DIR / str(uid)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @r.get("")
    def list_uploads(_=Depends(need_user)):
        return db.uploads()

    @r.post("")
    async def create(request: Request, _=Depends(need_user)):
        b = await request.json()
        ch = config.channel_key(b.get("channel"))
        if not ch:
            raise HTTPException(400, "채널을 골라 주세요")
        size = int(b.get("size") or 0)
        if size <= 0 or size > MAX_VIDEO:
            raise HTTPException(400, "영상 파일 크기가 이상합니다 (8GB까지)")
        free = shutil.disk_usage(config.UPLOAD_DIR).free
        if free < size + 2 * 1024 ** 3:
            raise HTTPException(507, f"서버 저장 공간이 모자랍니다 (남은 {free / 1024 ** 3:.1f}GB)")
        u = db.create_upload(ch, str(b.get("date") or ""), str(b.get("filename") or "video.mp4")[:200], size)
        folder(u["id"])
        db.add_log(f"{config.channel_name(ch)} 영상 올리기를 시작했습니다 ({size / 1024 ** 3:.2f}GB)")
        return u

    @r.get("/{uid}")
    def one(uid: int, _=Depends(need_user)):
        return get(uid)

    @r.put("/{uid}/video")
    async def video_chunk(uid: int, request: Request, offset: int = 0, _=Depends(need_user)):
        u = get(uid)
        if u["state"] not in ("받는중", "준비"):
            raise HTTPException(409, "이미 유튜브로 보낸 올리기입니다")
        if offset != u["received"]:
            raise HTTPException(409, json.dumps({"received": u["received"]}))
        p = folder(uid) / "video.mp4"
        n = 0
        with open(p, "ab") as f:
            try:
                async for chunk in request.stream():
                    n += len(chunk)
                    if n > MAX_CHUNK or u["received"] + n > u["size"]:
                        raise HTTPException(400, "조각이 너무 큽니다")
                    f.write(chunk)
            except BaseException:
                # 받다 끊긴 조각은 버림 (다음에 같은 자리부터 다시 받음)
                f.truncate(u["received"])
                raise
        got = u["received"] + n
        return db.update_upload(uid, {"received": got, "state": "준비" if got >= u["size"] else "받는중"})

    @r.post("/{uid}/thumb")
    async def thumb(uid: int, file: UploadFile = File(...), _=Depends(need_user)):
        get(uid)
        ext = Path(file.filename or "").suffix.lower()
        if ext not in IMG:
            raise HTTPException(400, "jpg, png 그림만 넣을 수 있습니다")
        data = await file.read()
        if len(data) > 10 * 1024 ** 2:
            raise HTTPException(400, "그림이 10MB를 넘습니다")
        for old in folder(uid).glob("thumb.*"):
            old.unlink()
        (folder(uid) / f"thumb{ext}").write_bytes(data)
        return db.update_upload(uid, {"thumb": f"thumb{ext}"})

    @r.get("/{uid}/thumb")
    def thumb_file(uid: int, _=Depends(need_user)):
        u = get(uid)
        p = config.UPLOAD_DIR / str(uid) / (u.get("thumb") or "-")
        if not u.get("thumb") or not p.is_file():
            raise HTTPException(404)
        return FileResponse(p)

    @r.post("/{uid}/chapters")
    async def chapters(uid: int, file: UploadFile = File(...), _=Depends(need_user)):
        """수록곡.json (두번붙이기.py 가 남긴 것) → 챕터"""
        get(uid)
        try:
            raw = json.loads((await file.read()).decode("utf-8-sig"))
            songs = [{"start": int(s["시작"]) // 1_000_000, "title": str(s["제목"])} for s in raw["곡들"]]
        except Exception:
            raise HTTPException(400, "수록곡.json 형식이 아닙니다 ({전체, 곡들:[{시작, 제목}]})")
        if not songs or songs[0]["start"] != 0:
            raise HTTPException(400, "첫 곡이 0:00 에서 시작해야 유튜브가 챕터를 만듭니다")
        return db.update_upload(uid, {"chapters": songs})

    @r.patch("/{uid}")
    async def patch(uid: int, request: Request, who=Depends(need_user)):
        get(uid)
        b = await request.json()
        allowed = WORKER_FIELDS if who == "pc" else USER_FIELDS
        return db.update_upload(uid, {k: v for k, v in b.items() if k in allowed})

    @r.post("/{uid}/draft")
    def draft(uid: int, _=Depends(need_user)):
        """AI 초안(제목 후보 · 첫머리 글 · 태그) — 일꾼이 1분 안에 씀"""
        get(uid)
        return db.update_upload(uid, {"draft": "요청", "draft_note": ""})

    @r.post("/{uid}/go")
    def go(uid: int, _=Depends(need_user)):
        u = get(uid)
        if u["state"] not in ("준비", "실패") or u["received"] < u["size"]:
            raise HTTPException(409, "영상 파일이 아직 다 올라오지 않았습니다")
        if not (u.get("title") or "").strip():
            raise HTTPException(400, "제목을 써 주세요")
        if not u.get("date"):
            raise HTTPException(400, "공개 날짜를 골라 주세요")
        # 같은 채널·날짜의 편이 있으면 거기에 붙이고, 없으면 새 편
        e = db.episode_by_date(u["channel"], u["date"]) or db.create_episode(u["channel"], db.next_ep(u["channel"]), date=u["date"])
        db.update_upload(uid, {"state": "대기", "episode_id": e["id"], "error": ""})
        db.add_log(f"{config.channel_name(u['channel'])} {e['ep']}편 영상을 유튜브로 보내기 시작했습니다 (일부 공개로 올라갑니다)")
        return db.upload(uid)

    @r.delete("/{uid}")
    def remove(uid: int, _=Depends(need_user)):
        u = get(uid)
        if u["state"] == "올리는중":
            raise HTTPException(409, "유튜브로 보내는 중에는 지울 수 없습니다")
        shutil.rmtree(config.UPLOAD_DIR / str(uid), ignore_errors=True)
        db.delete_upload(uid)
        return {"ok": True}

    return r
