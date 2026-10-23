# -*- coding: utf-8 -*-
r"""
영상 관리 사이트에 보고하기

PC의 Claude가 작업할 때마다 이 도구로 사이트에 "어디까지 했는지"를
올립니다. 사이트에서 사장님이 눌러 둔 일도 이 도구로 받아 갑니다.
파이썬 기본 꾸러미만 써서 따로 설치할 것이 없습니다.

처음 한 번: 이 파일 옆에 「관리사이트.json」을 만듭니다.
    { "주소": "https://video.168-119-152-95.sslip.io", "토큰": "서버의 API_TOKEN 값" }
  ※ 이 파일은 절대 커밋하지 마세요 (.gitignore 에 넣어 두세요).

쓰는 법 (채널은 황금주파수 / 불심명언, 빼면 황금주파수)
  python 보고.py 할일                                   # 사장님이 시켜 둔 일 보기
  python 보고.py 처리 --번호 3 --상태 작업중             # 시킨 일 상태 바꾸기 (작업중/완료/막힘)
  python 보고.py 처리 --번호 3 --상태 완료 --메모 "업로드까지 끝"
  python 보고.py 지금 --상태 일함 --하는일 "불심명언 12편 영상 만드는 중" --다음 "썸네일"
  python 보고.py 지금 --상태 쉼 --마지막 "12편 예약 완료"
  python 보고.py 단계 --채널 불심명언 --편 12 --단계 "영상 만들기" --상태 완료
  python 보고.py 단계 --채널 불심명언 --편 12 --단계 다운로드 --상태 막힘 --메모 "수노 로그인 풀림"
  python 보고.py 편 --채널 불심명언 --편 12 --날짜 2026-10-30 --분 53 --곡 12/12
  python 보고.py 업로드정보 --채널 불심명언 --편 12 --폴더 "D:\불심명언\_완성12"
      → 그 폴더의 업로드정보.json(제목·설명·태그·예약시간), 썸네일.jpg/png,
        업로드결과.txt(영상 주소)를 읽어서 한 번에 올립니다
  python 보고.py 썸네일 --채널 불심명언 --편 12 --파일 "D:\불심명언\_완성12\썸네일.jpg"
  python 보고.py 막힘 --채널 불심명언 --편 12 --이유 "캡컷이 안 열림"     (--이유 "" 로 풀기)
  python 보고.py 기록 "불심명언 12편 업로드 예약 완료"
"""

import argparse
import io
import json
import mimetypes
import os
import re
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

여기 = Path(__file__).resolve().parent
단계들 = ["가사 만들기", "가사 검토", "수노 노래 만들기", "다운로드", "썸네일 이미지 만들기",
         "썸네일 문구 만들기", "영상 이미지 만들기", "영상 만들기", "업로드 예약"]


def 설정():
    주소 = os.environ.get("관리사이트_주소") or os.environ.get("VM_URL")
    토큰 = os.environ.get("관리사이트_토큰") or os.environ.get("VM_TOKEN")
    파일 = 여기 / "관리사이트.json"
    if 파일.exists():
        d = json.load(io.open(파일, encoding="utf-8"))
        주소 = 주소 or d.get("주소")
        토큰 = 토큰 or d.get("토큰")
    if not 주소 or not 토큰:
        sys.exit("[실패] %s 에 주소와 토큰을 적어 주세요." % 파일)
    return 주소.rstrip("/"), 토큰


def 요청(방법, 길, 몸=None, 파일=None):
    주소, 토큰 = 설정()
    머리 = {"Authorization": "Bearer " + 토큰}
    데이터 = None
    if 파일:
        경계 = uuid.uuid4().hex
        조각 = []
        for k, v in (몸 or {}).items():
            조각.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                       % (경계, k, v)).encode("utf-8"))
        p = Path(파일)
        종류 = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        조각.append(("--%s\r\nContent-Disposition: form-data; name=\"file\"; filename=\"thumb%s\"\r\n"
                   "Content-Type: %s\r\n\r\n" % (경계, p.suffix.lower(), 종류)).encode("utf-8"))
        조각.append(p.read_bytes())
        조각.append(("\r\n--%s--\r\n" % 경계).encode("utf-8"))
        데이터 = b"".join(조각)
        머리["Content-Type"] = "multipart/form-data; boundary=" + 경계
    elif 몸 is not None:
        데이터 = json.dumps(몸, ensure_ascii=False).encode("utf-8")
        머리["Content-Type"] = "application/json"
    r = urllib.request.Request(주소 + 길, data=데이터, headers=머리, method=방법)
    try:
        with urllib.request.urlopen(r, timeout=60) as 응답:
            return json.loads(응답.read().decode("utf-8") or "null")
    except urllib.error.HTTPError as e:
        내용 = e.read().decode("utf-8", "replace")
        try:
            내용 = json.loads(내용).get("detail", 내용)
        except ValueError:
            pass
        sys.exit("[실패] 사이트가 거절했습니다 (%s): %s" % (e.code, 내용))
    except urllib.error.URLError as e:
        sys.exit("[실패] 사이트에 연결하지 못했습니다: %s" % e.reason)


def 보고(채널, 편, **값):
    return 요청("POST", "/api/report", dict(channel=채널, ep=편, **값))


def 읽기(경로):
    return json.load(io.open(경로, encoding="utf-8-sig"))


def 영상번호(글):
    m = re.search(r"(?:youtu\.be/|v=|shorts/)([A-Za-z0-9_-]{11})", 글 or "")
    return m.group(1) if m else None


# ---------------------------------------------------------------- 명령들

def 할일(a):
    목록 = 요청("GET", "/api/queue?state=" + urllib.request.quote("요청"))
    if a.json:
        print(json.dumps(목록, ensure_ascii=False, indent=2))
        return
    if not 목록:
        print("시켜 둔 일이 없습니다.")
        return
    for q in 목록:
        편 = q.get("episode") or {}
        어디 = ("%s %s편 · " % ({"A": "황금주파수", "B": "불심명언"}.get(편.get("channel"), ""), 편.get("ep"))) if 편 else ""
        print("[%s] %s — %s%s" % (q["id"], q["kind"], 어디, q.get("label", "")))
        if q.get("payload"):
            print("      내용: " + json.dumps(q["payload"], ensure_ascii=False))


def 처리(a):
    몸 = {"state": a.상태}
    if a.메모 is not None:
        몸["note"] = a.메모
    요청("PATCH", "/api/queue/%d" % a.번호, 몸)
    print("[완료] %s번 → %s" % (a.번호, a.상태))


def 지금(a):
    몸 = {"state": a.상태, "doing": a.하는일, "last": a.마지막, "next": a.다음}
    요청("PUT", "/api/status", {k: v for k, v in 몸.items() if v is not None})
    print("[완료] PC 상태를 올렸습니다")


def 단계(a):
    if a.단계 not in 단계들:
        sys.exit("[실패] 단계 이름은 이 중 하나여야 합니다: " + ", ".join(단계들))
    값 = {"steps": {a.단계: a.상태}}
    if a.메모 is not None:
        값["step_notes"] = {a.단계: a.메모}
    보고(a.채널, a.편, **값)
    print("[완료] %s %s편 · %s → %s" % (a.채널, a.편, a.단계, a.상태))


def 편(a):
    값 = {}
    if a.날짜:
        값["date"] = a.날짜
    if a.분 is not None:
        값["minutes"] = a.분
    if a.곡:
        한, 전체 = a.곡.split("/")
        값.update(songs_done=int(한), songs_total=int(전체))
    if a.영상:
        값["video_id"] = 영상번호(a.영상) or a.영상
    보고(a.채널, a.편, **값)
    print("[완료] %s %s편 정보를 올렸습니다" % (a.채널, a.편))


def 썸네일(a):
    p = Path(a.파일)
    if not p.exists():
        sys.exit("[실패] 파일이 없습니다: %s" % p)
    요청("POST", "/api/report/thumbnail", {"channel": a.채널, "ep": a.편}, 파일=p)
    print("[완료] 썸네일을 올렸습니다")


def 업로드정보(a):
    폴더 = Path(a.폴더)
    값, 한것 = {}, []
    정보파일 = 폴더 / "업로드정보.json"
    if 정보파일.exists():
        d = 읽기(정보파일)
        값.update(title=d.get("제목", ""), description=d.get("설명", ""), tags=d.get("태그", []))
        if d.get("예약시간"):
            값["date"] = d["예약시간"][:10]
        한것.append("제목·설명·태그")
    문구파일 = 폴더 / "썸네일.json"
    if 문구파일.exists():
        d = 읽기(문구파일)
        줄 = d.get("줄") or [d.get(k) for k in ("윗줄", "아랫줄", "아래작은글") if d.get(k)]
        if 줄:
            값["thumb_lines"] = 줄
            한것.append("썸네일 문구")
    결과 = 폴더 / "업로드결과.txt"
    if 결과.exists():
        번호 = 영상번호(결과.read_text(encoding="utf-8", errors="replace"))
        if 번호:
            값["video_id"] = 번호
            값["steps"] = {"업로드 예약": "완료"}
            한것.append("영상 주소")
    수록곡 = 폴더 / "수록곡.json"
    if 수록곡.exists():
        try:
            # 모음집이어붙이기.py 가 남기는 {"전체길이": 마이크로초, "곡들": [{"제목": ...}, ...]}
            d = 읽기(수록곡)
            곡들 = d.get("곡들", []) if isinstance(d, dict) else d
            if isinstance(d, dict) and d.get("전체길이"):
                값["minutes"] = round(d["전체길이"] / 1_000_000 / 60)
                한것.append("길이 %d분" % 값["minutes"])
            if isinstance(곡들, list) and 곡들:
                몇곡 = len({곡.get("제목") for 곡 in 곡들 if isinstance(곡, dict)}) or len(곡들)
                값["songs_done"] = 값["songs_total"] = 몇곡
                한것.append("곡 %d개" % 몇곡)
        except ValueError:
            pass
    if 값:
        보고(a.채널, a.편, log="업로드 정보 올림", **값)
    그림 = next((폴더 / ("썸네일" + 끝) for 끝 in (".jpg", ".png", ".jpeg", ".webp")
               if (폴더 / ("썸네일" + 끝)).exists()), None)
    if 그림:
        if 그림.stat().st_size > 5 * 1024 * 1024:
            print("  [경고] 썸네일이 5MB를 넘어 올리지 않았습니다")
        else:
            요청("POST", "/api/report/thumbnail", {"channel": a.채널, "ep": a.편}, 파일=그림)
            한것.append("썸네일 그림")
    if not 한것:
        sys.exit("[실패] %s 에서 올릴 것을 찾지 못했습니다" % 폴더)
    print("[완료] %s %s편: %s" % (a.채널, a.편, ", ".join(한것)))


def 막힘(a):
    보고(a.채널, a.편, block=a.이유, log=("막힘: " + a.이유) if a.이유 else "막힘 풀림")
    print("[완료] " + ("막힘을 적었습니다" if a.이유 else "막힘을 풀었습니다"))


def 검토요청(a):
    """비공개로 올린 뒤: 사이트에 ‘검토 대기’로 알림 (사장님이 미리보기로 확인하고 승인)"""
    값 = {"review": "검토대기", "log": "비공개로 올림 — 검토 기다림"}
    if a.주소:
        번호 = 영상번호(a.주소)
        if 번호:
            값["video_id"] = 번호
    보고(a.채널, a.편, **값)
    print("[완료] 사이트에 검토 대기로 올렸습니다. 사장님이 승인하면 ‘할일’에 승인이 들어옵니다.")


def 기록(a):
    요청("POST", "/api/log", {"text": a.글})
    print("[완료] 기록을 남겼습니다")


def main():
    p = argparse.ArgumentParser(description="영상 관리 사이트에 보고하기")
    s = p.add_subparsers(dest="명령", required=True)

    def 편인자(x):
        x.add_argument("--채널", default="황금주파수", help="황금주파수 / 불심명언")
        x.add_argument("--편", type=int, required=True)

    x = s.add_parser("할일"); x.add_argument("--json", action="store_true"); x.set_defaults(f=할일)
    x = s.add_parser("처리"); x.add_argument("--번호", type=int, required=True)
    x.add_argument("--상태", required=True, choices=["요청", "작업중", "완료", "막힘"])
    x.add_argument("--메모"); x.set_defaults(f=처리)
    x = s.add_parser("지금"); x.add_argument("--상태", choices=["일함", "쉼", "막힘"])
    x.add_argument("--하는일"); x.add_argument("--마지막"); x.add_argument("--다음"); x.set_defaults(f=지금)
    x = s.add_parser("단계"); 편인자(x); x.add_argument("--단계", required=True)
    x.add_argument("--상태", required=True, choices=["작업대기", "작업중", "완료", "막힘"])
    x.add_argument("--메모"); x.set_defaults(f=단계)
    x = s.add_parser("편"); 편인자(x); x.add_argument("--날짜"); x.add_argument("--분", type=int)
    x.add_argument("--곡", help="12/12 처럼"); x.add_argument("--영상", help="유튜브 주소"); x.set_defaults(f=편)
    x = s.add_parser("썸네일"); 편인자(x); x.add_argument("--파일", required=True); x.set_defaults(f=썸네일)
    x = s.add_parser("업로드정보"); 편인자(x); x.add_argument("--폴더", required=True); x.set_defaults(f=업로드정보)
    x = s.add_parser("막힘"); 편인자(x); x.add_argument("--이유", required=True); x.set_defaults(f=막힘)
    x = s.add_parser("기록"); x.add_argument("글"); x.set_defaults(f=기록)
    x = s.add_parser("검토요청"); 편인자(x); x.add_argument("--주소", help="올린 영상 주소 (youtu.be/...)"); x.set_defaults(f=검토요청)

    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
