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

JSON_FIELDS = ("steps", "step_notes", "thumb_lines", "tags")

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
        for col in ("review TEXT DEFAULT ''", "publish_at TEXT DEFAULT ''"):  # 예전 DB에도 붙여 줌
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
            ep[f] = json.loads(ep.get(f) or ("[]" if f in ("thumb_lines", "tags") else "{}"))
        except ValueError:
            ep[f] = [] if f in ("thumb_lines", "tags") else {}
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
            "privacy", "views", "likes", "stats_at", "review", "publish_at"}


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
