"""SQLite 저장소. 파일 하나(/data/manager.db)에 다 들어갑니다."""

import json
import re
import sqlite3
import threading
from datetime import datetime, timedelta, timezone

from . import config

KST = timezone(timedelta(hours=9))
_lock = threading.Lock()
_conn = None

JSON_FIELDS = ("steps", "step_notes", "thumb_lines", "tags", "ai_titles")

SCHEMA = """
CREATE TABLE IF NOT EXISTS episodes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  channel TEXT NOT NULL,
  ep INTEGER NOT NULL,
  date TEXT DEFAULT '',
  minutes INTEGER,
  songs_done INTEGER,
  songs_total INTEGER,
  steps TEXT DEFAULT '{}',
  step_notes TEXT DEFAULT '{}',
  title TEXT DEFAULT '',
  description TEXT DEFAULT '',
  thumb_lines TEXT DEFAULT '[]',
  tags TEXT DEFAULT '[]',
  thumb TEXT DEFAULT '',
  block TEXT DEFAULT '',
  note TEXT DEFAULT '',
  video_id TEXT DEFAULT '',
  privacy TEXT DEFAULT '',
  views INTEGER,
  likes INTEGER,
  stats_at TEXT DEFAULT '',
  created_at TEXT,
  updated_at TEXT,
  UNIQUE(channel, ep)
);
CREATE TABLE IF NOT EXISTS queue (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL,
  episode_id INTEGER,
  label TEXT DEFAULT '',
  payload TEXT DEFAULT '{}',
  state TEXT DEFAULT '요청',
  note TEXT DEFAULT '',
  created_at TEXT,
  updated_at TEXT
);
CREATE TABLE IF NOT EXISTS status (
  k TEXT PRIMARY KEY,
  data TEXT DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  at TEXT,
  text TEXT
);
"""


def now():
    return datetime.now(KST).isoformat(timespec="seconds")


def today():
    return datetime.now(KST).strftime("%Y-%m-%d")


def conn():
    global _conn
    if _conn is None:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        config.THUMB_DIR.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.executescript(SCHEMA)
        # 검토 칸 (검토대기 · 승인 · 다시만들기) — 예전 DB에도 붙여 줌
        _conn.executescript(UPLOAD_SCHEMA)
        _conn.executescript(CHANNEL_SCHEMA)
        load_channels(_conn)
        for col in ("review TEXT DEFAULT ''", "publish_at TEXT DEFAULT ''",  # 예전 DB에도 붙여 줌
                    "shop_tags INTEGER DEFAULT 0", "shop_checked_at TEXT DEFAULT ''",   # 쇼핑 태그 개수 · 마지막 확인
                    "ai_state TEXT DEFAULT ''", "ai_titles TEXT DEFAULT '[]'", "ai_desc TEXT DEFAULT ''", "ai_note TEXT DEFAULT ''"):  # AI 제목·설명
            try:
                _conn.execute("ALTER TABLE episodes ADD COLUMN " + col)
            except sqlite3.OperationalError:
                pass
    return _conn


def q(sql, args=()):
    with _lock:
        cur = conn().execute(sql, args)
        conn().commit()
        return cur


def rows(sql, args=()):
    with _lock:
        return [dict(r) for r in conn().execute(sql, args).fetchall()]


def one(sql, args=()):
    r = rows(sql, args)
    return r[0] if r else None


# ---------------------------------------------------------------- 편(episode)

def _decode(ep):
    if not ep:
        return ep
    for f in JSON_FIELDS:
        try:
            ep[f] = json.loads(ep.get(f) or ("[]" if f in ("thumb_lines", "tags", "ai_titles") else "{}"))
        except ValueError:
            ep[f] = [] if f in ("thumb_lines", "tags", "ai_titles") else {}
    ep["badge"] = badge(ep)
    ep["done_steps"] = sum(1 for s in config.STEPS if ep["steps"].get(s) == "완료")
    return ep


def badge(ep):
    """한눈에 보는 상태 딱지"""
    steps = ep.get("steps") or {}
    # PC가 일부 공개로 올리고 확인을 기다리는 편 (사이트에서 승인해야 예약 공개)
    if ep.get("review") == "검토대기":
        return "검토대기"
    if ep.get("review") == "다시만들기":
        return "다시만들기"
    if ep.get("review") == "고치는중":
        return "고치는중"
    if ep.get("video_id") or steps.get("업로드 예약") == "완료":
        # 유튜브에서 읽어 온 실제 상태가 있으면 그것대로 (조회수 채우기가 3시간마다 privacy·publish_at 을 넣음)
        pv = ep.get("privacy") or ""
        if pv == "public":
            return "공개됨"
        if pv == "private" and not ep.get("publish_at"):
            return "비공개"
        if pv == "unlisted":
            return "일부공개"
        if pv == "private":
            return "예약됨"
        if ep.get("date") and ep["date"] > today():
            return "예약됨"
        return "공개됨"
    if ep.get("block") or any(v == "막힘" for v in steps.values()):
        return "막힘"
    done = sum(1 for s in config.STEPS if steps.get(s) == "완료")
    if done == len(config.STEPS):
        return "완료"
    if done or any(v == "작업중" for v in steps.values()):
        return "제작중"
    return "준비"


def episodes(channel=None):
    if channel:
        r = rows("SELECT * FROM episodes WHERE channel=? ORDER BY date DESC, ep DESC", (channel,))
    else:
        r = rows("SELECT * FROM episodes ORDER BY date DESC, ep DESC")
    # SHOW_FROM 보다 앞선 편은 숨김 (날짜가 아직 없는 새 편은 보임)
    if config.SHOW_FROM:
        r = [e for e in r if not e["date"] or e["date"] >= config.SHOW_FROM]
    return [_decode(e) for e in r]


def episode(eid):
    return _decode(one("SELECT * FROM episodes WHERE id=?", (eid,)))


def episode_by_date(channel, date):
    return _decode(one("SELECT * FROM episodes WHERE channel=? AND date=? ORDER BY ep DESC", (channel, date)))


def episode_by(channel, ep):
    return _decode(one("SELECT * FROM episodes WHERE channel=? AND ep=?", (channel, ep)))


def next_ep(channel):
    r = one("SELECT MAX(ep) AS m FROM episodes WHERE channel=?", (channel,))
    return (r["m"] or 0) + 1


def create_episode(channel, ep, **fields):
    t = now()
    steps = {s: "작업대기" for s in config.STEPS}
    q("INSERT INTO episodes (channel, ep, steps, created_at, updated_at) VALUES (?,?,?,?,?)",
      (channel, ep, json.dumps(steps, ensure_ascii=False), t, t))
    e = episode_by(channel, ep)
    if fields:
        update_episode(e["id"], fields)
    return episode(e["id"])


EDITABLE = {"date", "minutes", "songs_done", "songs_total", "steps", "step_notes", "title",
            "description", "thumb_lines", "tags", "thumb", "block", "note", "video_id",
            "privacy", "views", "likes", "stats_at", "review", "publish_at",
            "shop_tags", "shop_checked_at", "ai_state", "ai_titles", "ai_desc", "ai_note"}


def update_episode(eid, fields):
    cur = episode(eid)
    if not cur:
        return None
    sets, args = [], []
    for k, v in fields.items():
        if k not in EDITABLE or v is None:
            continue
        if k in ("steps", "step_notes"):
            merged = dict(cur[k])
            merged.update(v)
            v = merged
        if k in JSON_FIELDS:
            v = json.dumps(v, ensure_ascii=False)
        sets.append(f"{k}=?")
        args.append(v)
    if sets:
        sets.append("updated_at=?")
        args += [now(), eid]
        q(f"UPDATE episodes SET {', '.join(sets)} WHERE id=?", args)
    return episode(eid)


def delete_episode(eid):
    q("DELETE FROM episodes WHERE id=?", (eid,))
    q("DELETE FROM queue WHERE episode_id=?", (eid,))


# ---------------------------------------------------------------- 시킨 일(queue)

def _qdecode(r):
    if r:
        try:
            r["payload"] = json.loads(r.get("payload") or "{}")
        except ValueError:
            r["payload"] = {}
    return r


def queue(state=None, limit=50):
    if state:
        r = rows("SELECT * FROM queue WHERE state=? ORDER BY id", (state,))
    else:
        r = rows("SELECT * FROM queue ORDER BY id DESC LIMIT ?", (limit,))
    return [_qdecode(x) for x in r]


def add_queue(kind, episode_id=None, label="", payload=None):
    t = now()
    cur = q("INSERT INTO queue (kind, episode_id, label, payload, state, created_at, updated_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (kind, episode_id, label, json.dumps(payload or {}, ensure_ascii=False), "요청", t, t))
    return _qdecode(one("SELECT * FROM queue WHERE id=?", (cur.lastrowid,)))


def update_queue(qid, state=None, note=None):
    if state is not None:
        q("UPDATE queue SET state=?, updated_at=? WHERE id=?", (state, now(), qid))
    if note is not None:
        q("UPDATE queue SET note=?, updated_at=? WHERE id=?", (note, now(), qid))
    return _qdecode(one("SELECT * FROM queue WHERE id=?", (qid,)))


def delete_queue(qid):
    q("DELETE FROM queue WHERE id=?", (qid,))


# ---------------------------------------------------------------- PC 상태 / 기록

def get_status():
    r = one("SELECT data FROM status WHERE k='now'")
    return json.loads(r["data"]) if r else {}


def set_status(data):
    cur = get_status()
    cur.update({k: v for k, v in data.items() if v is not None})
    cur["at"] = now()
    q("INSERT INTO status (k, data) VALUES ('now', ?) ON CONFLICT(k) DO UPDATE SET data=excluded.data",
      (json.dumps(cur, ensure_ascii=False),))
    return cur


def add_log(text):
    q("INSERT INTO log (at, text) VALUES (?,?)", (now(), text))


def logs(limit=30):
    return rows("SELECT * FROM log ORDER BY id DESC LIMIT ?", (limit,))


# ---------------------------------------------------------------- 처음 한 번: 기존 대시보드 기록 옮기기

YT_ID = re.compile(r"(?:youtu\.be/|v=)([A-Za-z0-9_-]{11})")


def seed_if_empty():
    if one("SELECT id FROM episodes LIMIT 1") or not config.SEED_DIR.is_dir():
        return 0
    n = 0
    for f in sorted(config.SEED_DIR.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        ch = config.channel_key(d.get("channel"))
        if not ch or not d.get("ep"):
            continue
        text = d.get("text") or {}
        fields = {
            "date": d.get("date", ""),
            "minutes": d.get("minutes"),
            "songs_done": (d.get("songs") or {}).get("done"),
            "songs_total": (d.get("songs") or {}).get("total"),
            # 예전 대시보드는 단계 이름이 달랐던 때가 있어, 예약까지 끝난 편은 아홉 단계를 다 채웁니다
            "steps": ({s: "완료" for s in config.STEPS} if d.get("badge") == "예약됨"
                      else d.get("steps") or {}),
            "step_notes": d.get("stepNotes") or {},
            "block": d.get("block") or "",
        }
        if isinstance(text, dict):
            fields.update(title=text.get("title", ""), description=text.get("desc", ""),
                          thumb_lines=text.get("thumbLines") or [])
        else:
            fields["note"] = str(text)
        m = YT_ID.search(json.dumps(d, ensure_ascii=False))
        if m:
            fields["video_id"] = m.group(1)
        create_episode(ch, int(d["ep"]), **fields)
        n += 1
    if n:
        add_log(f"기존 작업 대시보드에서 {n}편을 옮겨 왔습니다")
    return n


# ---------------------------------------------------------------- 사이트에서 직접 올리기
# state: 받는중(파일 받는 중) → 준비(파일 다 받음) → 대기(유튜브로 보낼 차례) → 올리는중 → 올림 / 실패
# draft: '' · 요청(AI 초안 기다림) · 완료 · 실패

UPLOAD_SCHEMA = """
CREATE TABLE IF NOT EXISTS uploads (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  channel TEXT NOT NULL,
  date TEXT DEFAULT '',
  filename TEXT DEFAULT '',
  size INTEGER DEFAULT 0,
  received INTEGER DEFAULT 0,
  state TEXT DEFAULT '받는중',
  progress INTEGER DEFAULT 0,
  title TEXT DEFAULT '',
  description TEXT DEFAULT '',
  tags TEXT DEFAULT '[]',
  thumb TEXT DEFAULT '',
  chapters TEXT DEFAULT '[]',
  draft TEXT DEFAULT '',
  draft_note TEXT DEFAULT '',
  youtube_id TEXT DEFAULT '',
  episode_id INTEGER,
  error TEXT DEFAULT '',
  created_at TEXT,
  updated_at TEXT
);
"""
UPLOAD_JSON = ("tags", "chapters")


def _udecode(u):
    if not u:
        return u
    for f in UPLOAD_JSON:
        try:
            u[f] = json.loads(u.get(f) or "[]")
        except ValueError:
            u[f] = []
    return u


def upload(uid):
    return _udecode(one("SELECT * FROM uploads WHERE id=?", (uid,)))


def uploads(limit=30):
    return [_udecode(u) for u in rows("SELECT * FROM uploads ORDER BY id DESC LIMIT ?", (limit,))]


def create_upload(channel, date, filename, size):
    t = now()
    cur = q("INSERT INTO uploads (channel, date, filename, size, created_at, updated_at) VALUES (?,?,?,?,?,?)",
            (channel, date, filename, size, t, t))
    return upload(cur.lastrowid)


def update_upload(uid, fields):
    sets, args = [], []
    for k, v in fields.items():
        if k in UPLOAD_JSON:
            v = json.dumps(v, ensure_ascii=False)
        sets.append(f"{k}=?")
        args.append(v)
    if sets:
        q(f"UPDATE uploads SET {', '.join(sets)}, updated_at=? WHERE id=?", (*args, now(), uid))
    return upload(uid)


def delete_upload(uid):
    q("DELETE FROM uploads WHERE id=?", (uid,))


# ---------------------------------------------------------------- 채널 (사이트에서 늘릴 수 있음)
# 처음에는 config.CHANNELS(황금주파수 A · 불심명언 B)로 채우고, 그 뒤로는 이 표가 기준.
# 이름(name)은 라이브 관리자의 채널 이름과 같아야 조회수 채우기·올리기 일꾼이 그 채널 구글 계정을 찾습니다.

CHANNEL_SCHEMA = """
CREATE TABLE IF NOT EXISTS channels (
  key TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  display TEXT DEFAULT '',
  color TEXT DEFAULT '#7c5cff',
  sort INTEGER DEFAULT 0
);
"""


def load_channels(c=None):
    """채널 표 → config.CHANNELS (다른 곳은 그대로 config.CHANNELS 를 봄)"""
    c = c or conn()
    if not c.execute("SELECT COUNT(*) FROM channels").fetchone()[0]:
        for i, ch in enumerate(config.CHANNELS):
            c.execute("INSERT INTO channels (key, name, display, color, sort) VALUES (?,?,?,?,?)",
                      (ch["key"], ch["name"], ch.get("display") or ch["name"], ch.get("color") or "#7c5cff", i))
        c.commit()
    got = [dict(r) for r in c.execute("SELECT key, name, display, color FROM channels ORDER BY sort, key")]
    config.CHANNELS[:] = got
    return got


def _next_key():
    used = {c["key"] for c in config.CHANNELS}
    n = 0
    while True:
        k, x = "", n
        while True:
            k = chr(65 + x % 26) + k
            x = x // 26 - 1
            if x < 0:
                break
        if k not in used:
            return k
        n += 1


def add_channel(name, display="", color="#7c5cff"):
    key = _next_key()
    with _lock:
        r = conn().execute("SELECT COALESCE(MAX(sort), 0) + 1 FROM channels").fetchone()[0]
        conn().execute("INSERT INTO channels (key, name, display, color, sort) VALUES (?,?,?,?,?)", (key, name, display or name, color, r))
        conn().commit()
    load_channels()
    return next(c for c in config.CHANNELS if c["key"] == key)


def update_channel(key, fields):
    sets = [(k, v) for k, v in fields.items() if k in ("name", "display", "color") and v]
    if sets:
        q(f"UPDATE channels SET {', '.join(k + '=?' for k, _ in sets)} WHERE key=?", (*[v for _, v in sets], key))
    load_channels()
    return next((c for c in config.CHANNELS if c["key"] == key), None)


# ---------------------------------------------------------------- 값 보관 (만들기 규칙 · 제목 규칙 · 서버 상태)
# status 표를 열쇠-값으로 같이 씀: 'rules:A' · 'system'

DEFAULT_RULES = {
    "songs": 8,              # 서로 다른 곡 개수 (1바퀴)
    "loops": 3,              # 1바퀴를 몇 번 이어 붙이나
    "min_minutes": 75,       # 목표 길이 (분)
    "max_minutes": 100,
    "song_seconds": 250,     # 곡 하나 평균 길이 (예상 길이 계산용 · 약 4분 10초)
    "publish_time": "21:00", # 공개 시각 (한국 시간)
    "every_days": 2,         # 며칠마다 한 편
    "privacy": "unlisted",   # 처음 올릴 때 (일부 공개 → 검토 → 승인하면 예약)
    "title_rules": "",       # 제목 짓는 규칙 (AI가 따름)
    "desc_rules": "",        # 설명 첫머리 규칙
    "examples": "",          # 잘된 제목 예시 (한 줄에 하나)
    "thumb_prompt": "",      # 썸네일 그림 프롬프트
    "image_prompt": "",      # 영상 배경 그림 프롬프트
    "lyrics_prompt": "",     # 노래 가사 프롬프트
    "ref_note": "",          # 어느 레퍼런스 채널 분석에서 왔는지
}


# ------------------------------------------------------------ 레퍼런스 채널 분석
# 사이트에서 채널 주소를 넣으면 '요청' → 서버 일꾼(라이브 관리자 tools/vm-upload.js)이 유튜브에서 읽고
# AI로 제목·설명·썸네일·영상 그림·가사 프롬프트를 만들어 '완료' 로 적음
_ref_lock = threading.Lock()  # kv_get/kv_set 이 _lock 을 쓰므로 따로


def refs():
    return kv_get("refs", []) or []


def ref(rid):
    return next((r for r in refs() if r["id"] == rid), None)


def add_ref(url, note=""):
    with _ref_lock:
        lst = refs()
        rid = max([r["id"] for r in lst] + [0]) + 1
        item = {"id": rid, "url": url, "note": note, "state": "요청", "error": "", "channel": {}, "result": {},
                "created_at": now(), "updated_at": now()}
        kv_set("refs", [item] + lst[:29])
    return item


def update_ref(rid, data):
    with _ref_lock:
        lst = refs()
        for r in lst:
            if r["id"] == rid:
                r.update({k: v for k, v in data.items() if k in ("state", "error", "channel", "result", "note", "sample", "sample_state", "sample_topic", "sample_error")})
                r["updated_at"] = now()
                kv_set("refs", lst)
                return r
    return None


# ------------------------------------------------------------ 수노 가사 만들기
# 사장님이 참고 가사를 넣으면 '요청' → 서버 일꾼이 구조·말투를 분석해서 수노에 바로 넣을 스타일·가사·가사 프롬프트를 만듦
LYRIC_FIELDS = ("state", "error", "result", "topic", "channel", "ref_lyrics", "title")


def lyric_jobs():
    return kv_get("lyrics", []) or []


def lyric_job(jid):
    return next((r for r in lyric_jobs() if r["id"] == jid), None)


def add_lyric_job(data):
    with _ref_lock:
        lst = lyric_jobs()
        jid = max([r["id"] for r in lst] + [0]) + 1
        item = {"id": jid, "state": "요청", "error": "", "result": {}, "created_at": now(), "updated_at": now()}
        item.update({k: data.get(k, "") for k in ("topic", "channel", "ref_lyrics", "title")})
        kv_set("lyrics", [item] + lst[:29])
    return item


def update_lyric_job(jid, data):
    with _ref_lock:
        lst = lyric_jobs()
        for r in lst:
            if r["id"] == jid:
                r.update({k: v for k, v in data.items() if k in LYRIC_FIELDS})
                r["updated_at"] = now()
                kv_set("lyrics", lst)
                return r
    return None


def delete_lyric_job(jid):
    with _ref_lock:
        kv_set("lyrics", [r for r in lyric_jobs() if r["id"] != jid])


def delete_ref(rid):
    with _ref_lock:
        kv_set("refs", [r for r in refs() if r["id"] != rid])


def kv_get(k, default=None):
    r = one("SELECT data FROM status WHERE k=?", (k,))
    return json.loads(r["data"]) if r else default


def kv_set(k, data):
    q("INSERT INTO status (k, data) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET data=excluded.data",
      (k, json.dumps(data, ensure_ascii=False)))
    return data


def rules(key):
    return {**DEFAULT_RULES, **(kv_get("rules:" + key, {}) or {})}


def set_rules(key, data):
    cur = rules(key)
    for k, v in data.items():
        if k not in DEFAULT_RULES:
            continue
        if isinstance(DEFAULT_RULES[k], int):
            try:
                v = max(0, min(1000, int(v)))
            except (TypeError, ValueError):
                continue
        else:
            v = str(v)[:4000]
        cur[k] = v
    return kv_set("rules:" + key, cur)
