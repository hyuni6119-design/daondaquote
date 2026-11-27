"""챌린지 글 내용(제목/본문/사진) 만들기."""
from __future__ import annotations

import datetime as dt
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("challenge")

WEEKDAYS_KR = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".bmp"}


@dataclass
class Post:
    day: int
    title: str
    body: str
    photos: list[Path] = field(default_factory=list)


def challenge_day(cfg: dict, today: dt.date) -> int | None:
    """오늘이 몇 일차인지. 올리지 않는 날이면 None."""
    ch = cfg["challenge"]
    start = dt.date.fromisoformat(str(ch["start_date"]))
    skip = set(ch.get("skip_weekdays") or [])
    if today < start or today.weekday() in skip:
        return None
    if ch.get("count_only_posting_days"):
        day = sum(
            1
            for i in range((today - start).days + 1)
            if (start + dt.timedelta(days=i)).weekday() not in skip
        )
    else:
        day = (today - start).days + 1
    if day > int(ch["total_days"]):
        return None
    return day


def generate_ai_text(cfg: dict, day: int, today: dt.date) -> str:
    ai = cfg.get("ai") or {}
    fallback = ai.get("fallback_text", "")
    if not ai.get("enabled"):
        return fallback
    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.warning("ANTHROPIC_API_KEY 가 없어 AI 문구 대신 fallback_text 를 사용합니다.")
        return fallback

    try:
        import anthropic
    except ImportError:
        log.warning("anthropic 패키지가 없어 fallback_text 를 사용합니다. (pip install anthropic)")
        return fallback

    ch = cfg["challenge"]
    prompt = (
        f"네이버 카페 챌린지 인증글에 들어갈 짧은 본문 문구를 한국어로 써 주세요.\n"
        f"- 챌린지: {ch['name']}\n"
        f"- 오늘: {today.isoformat()} ({WEEKDAYS_KR[today.weekday()]}), "
        f"{day}일차 / 총 {ch['total_days']}일\n"
        f"- 말투: {ai.get('tone', '밝고 짧게')}\n"
        f"- 참고: {ai.get('extra_instructions', '')}\n"
        "매일 다른 표현을 쓰고, 회차에 맞는 느낌(시작/중반/막바지)을 살려 주세요. "
        "제목·인사말·따옴표 없이 본문 문구만 출력하세요."
    )
    try:
        client = anthropic.Anthropic()
        resp = client.beta.messages.create(
            model=ai.get("model", "claude-opus-5-5"),
            max_tokens=2000,
            output_config={"effort": "low"},
            # 안전 필터가 거절하면 서버가 자동으로 다른 모델로 다시 시도
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": prompt}],
        )
        if resp.stop_reason == "refusal":
            log.warning("AI가 요청을 거절해 fallback_text 를 사용합니다.")
            return fallback
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        return text or fallback
    except anthropic.APIConnectionError as e:
        log.warning("AI 서버 연결 실패(%s) → fallback_text 사용", e)
    except anthropic.RateLimitError:
        log.warning("AI 사용량 한도 초과 → fallback_text 사용")
    except anthropic.APIStatusError as e:
        log.warning("AI 오류 %s: %s → fallback_text 사용", e.status_code, e.message)
    return fallback


def pick_photos(cfg: dict, day: int, base_dir: Path) -> list[Path]:
    ph = cfg.get("photos") or {}
    if not ph.get("enabled"):
        return []
    folder = (base_dir / ph.get("folder", "photos")).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    files = sorted(
        (p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS),
        key=lambda p: p.stat().st_mtime,
    )
    limit = int(ph.get("max_per_post", 1))

    def starts_with_day(p: Path) -> bool:
        stem = p.stem
        num = ""
        for c in stem:
            if c.isdigit():
                num += c
            else:
                break
        return num != "" and int(num) == day

    matched = [p for p in files if starts_with_day(p)]
    chosen = (matched or files)[:limit]
    if not chosen and ph.get("required"):
        raise RuntimeError(f"사진 폴더({folder})에 올릴 사진이 없습니다.")
    return chosen


def mark_photos_used(photos: list[Path]) -> None:
    for p in photos:
        used = p.parent / "used"
        used.mkdir(exist_ok=True)
        target = used / p.name
        if target.exists():
            target = used / f"{p.stem}_{dt.datetime.now():%Y%m%d%H%M%S}{p.suffix}"
        p.rename(target)


def build_post(cfg: dict, today: dt.date, base_dir: Path, use_ai: bool = True) -> Post | None:
    day = challenge_day(cfg, today)
    if day is None:
        return None
    ch = cfg["challenge"]
    ai_text = generate_ai_text(cfg, day, today) if use_ai else (cfg.get("ai") or {}).get("fallback_text", "")
    values = {
        "challenge": ch["name"],
        "day": day,
        "total": ch["total_days"],
        "date": today.isoformat(),
        "date_kr": f"{today.month}월 {today.day}일",
        "weekday": WEEKDAYS_KR[today.weekday()],
        "ai_text": ai_text,
    }
    post_cfg = cfg["post"]
    return Post(
        day=day,
        title=post_cfg["title_template"].format(**values).strip(),
        body=post_cfg["body_template"].format(**values).strip(),
        photos=pick_photos(cfg, day, base_dir),
    )
