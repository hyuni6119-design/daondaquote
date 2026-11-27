"""네이버카페 챌린지 자동업로드.

사용법:
  python main.py login            # 처음 1번: 브라우저에서 직접 로그인
  python main.py preview          # 오늘 올라갈 글 미리보기 (브라우저 안 염)
  python main.py post --dry-run   # 글쓰기 화면에 입력까지만 (등록 X)
  python main.py post             # 실제 업로드 (예약 실행용)
  python main.py post --date 2026-12-05 --force   # 특정 날짜로/중복이어도 올리기
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import random
import sys
import time
from pathlib import Path

import yaml

from content import build_post, mark_photos_used

BASE_DIR = Path(__file__).resolve().parent
STATE_FILE = BASE_DIR / "state.json"


def setup_logging() -> None:
    (BASE_DIR / "logs").mkdir(exist_ok=True)
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(BASE_DIR / "logs" / "challenge.log", encoding="utf-8"),
        ],
    )


def load_config(path: Path) -> dict:
    if not path.exists():
        sys.exit(f"설정 파일이 없습니다: {path}\n config.example.yaml 을 config.yaml 로 복사해 수정하세요.")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"posted": {}}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def print_post(post) -> None:
    print("=" * 50)
    print(f"[{post.day}일차] 제목: {post.title}")
    print("-" * 50)
    print(post.body)
    print("-" * 50)
    print("첨부 사진:", ", ".join(p.name for p in post.photos) or "(없음)")
    print("=" * 50)


def main() -> None:
    ap = argparse.ArgumentParser(description="네이버카페 챌린지 자동업로드")
    ap.add_argument("command", choices=["login", "preview", "post"])
    ap.add_argument("--config", default=str(BASE_DIR / "config.yaml"))
    ap.add_argument("--date", help="이 날짜 기준으로 글 생성 (YYYY-MM-DD, 기본: 오늘)")
    ap.add_argument("--dry-run", action="store_true", help="입력까지만 하고 등록 버튼은 누르지 않음")
    ap.add_argument("--force", action="store_true", help="오늘 이미 올렸어도 다시 올림")
    ap.add_argument("--no-delay", action="store_true", help="랜덤 대기 없이 바로 실행")
    ap.add_argument("--headless", action="store_true", help="브라우저 창 없이 실행")
    args = ap.parse_args()

    setup_logging()
    log = logging.getLogger("challenge")
    cfg = load_config(Path(args.config))

    if args.command == "login":
        from uploader import CafeUploader

        with CafeUploader(cfg, BASE_DIR, headless=False) as up:
            if up.is_logged_in():
                print("✅ 이미 로그인되어 있습니다.")
                return
            sys.exit(0 if up.interactive_login() else 1)

    today = dt.date.fromisoformat(args.date) if args.date else dt.date.today()
    state = load_state()
    key = today.isoformat()

    if args.command == "post" and not args.force and not args.dry_run and key in state["posted"]:
        log.info("%s 은 이미 업로드했습니다: %s (다시 올리려면 --force)", key, state["posted"][key]["url"])
        return

    post = build_post(cfg, today, BASE_DIR, use_ai=True)
    if post is None:
        log.info("%s 은 챌린지 업로드 날이 아닙니다 (시작 전/종료 후/건너뛰는 요일).", key)
        return
    print_post(post)

    if args.command == "preview":
        return

    delay = int((cfg.get("schedule") or {}).get("random_delay_minutes", 0))
    if delay and not args.no_delay and not args.dry_run:
        wait = random.randint(0, delay * 60)
        log.info("자연스러운 업로드를 위해 %d분 %d초 대기합니다...", wait // 60, wait % 60)
        time.sleep(wait)

    from uploader import CafeUploader

    with CafeUploader(cfg, BASE_DIR, headless=True if args.headless else None) as up:
        url = up.publish(post, dry_run=args.dry_run)

    if url:
        mark_photos_used(post.photos)
        state["posted"][key] = {"day": post.day, "title": post.title, "url": url}
        save_state(state)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n중단했습니다.")
    except Exception as e:  # 예약 실행 시 로그에 남기기
        logging.getLogger("challenge").exception("실패: %s", e)
        sys.exit(1)
