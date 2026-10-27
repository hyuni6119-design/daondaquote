"""설정값. 전부 환경변수로 바꿀 수 있습니다."""

import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
DB_PATH = DATA_DIR / "manager.db"
THUMB_DIR = DATA_DIR / "thumbs"
# 사이트에서 직접 올리는 영상을 잠깐 두는 곳 (라이브 관리자 서버의 올리기 일꾼과 같이 씀 · 올린 뒤 지움)
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "/srv/vm-uploads"))

# 사이트에 들어갈 때 쓰는 비밀번호
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
# PC의 Claude(보고.py)가 쓰는 열쇠. 비밀번호와 다르게 길게 만드세요.
API_TOKEN = os.environ.get("API_TOKEN", "")
# 로그인 쿠키를 서명하는 값
SECRET_KEY = os.environ.get("SECRET_KEY", "") or (API_TOKEN + ADMIN_PASSWORD) or "change-me"
# 조회수 가져오기용 (선택). 구글 클라우드 콘솔의 "API 키"
YT_API_KEY = os.environ.get("YT_API_KEY", "")
# 이 날짜(YYYY-MM-DD)부터 공개되는 편만 사이트에 보여 줌 (그 전 편은 지우지 않고 숨김 · 비우면 모두 보임)
SHOW_FROM = os.environ.get("SHOW_FROM", "")

SEED_DIR = Path(os.environ.get("SEED_DIR", Path(__file__).resolve().parent.parent / "seed"))

# 채널 — 기존 작업 대시보드와 같은 A/B 열쇠를 씁니다
CHANNELS = [
    {"key": "A", "name": "황금주파수", "display": "황금주파수 TV", "color": "#a87a12"},
    {"key": "B", "name": "불심명언", "display": "불심명언", "color": "#7a3f8f"},
]

# 한 편을 만드는 아홉 단계 — 기존 작업 대시보드와 똑같습니다
STEPS = [
    "가사 만들기",
    "가사 검토",
    "수노 노래 만들기",
    "다운로드",
    "썸네일 이미지 만들기",
    "썸네일 문구 만들기",
    "영상 이미지 만들기",
    "영상 만들기",
    "업로드 예약",
]
STEP_STATES = ["작업대기", "작업중", "완료", "막힘"]


def channel_name(key):
    return next((c["name"] for c in CHANNELS if c["key"] == key), key)


def channel_key(value):
    """'A', '황금주파수', '황금주파수 TV' 무엇으로 불러도 열쇠를 돌려줍니다."""
    if value is None:
        return None
    v = str(value).strip()
    for ch in CHANNELS:
        if v in (ch["key"], ch["name"], ch["display"]):
            return ch["key"]
    return None
