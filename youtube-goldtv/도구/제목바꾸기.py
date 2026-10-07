# -*- coding: utf-8 -*-
r"""
이미 올린 영상의 제목만 바꿉니다.

설명·태그는 건드리지 않습니다. videos.update 는 보낸 항목으로 통째
덮어쓰기 때문에, 먼저 videos.list 로 지금 값을 읽어 와 제목만 갈아
끼운 뒤 되돌려 보냅니다.

사용법
    python 제목바꾸기.py <동영상ID> "새 제목"
    python 제목바꾸기.py --채널 불심명언 <동영상ID> "새 제목"
"""
import argparse
import sys

from 채널 import 설정읽기, 인자붙이기, 토큰경로

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

권한범위 = ["https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube"]


def 인증(설정):
    토큰파일 = 토큰경로(설정)
    if not 토큰파일.exists():
        sys.exit("[실패] 토큰이 없습니다: %s" % 토큰파일)
    자격 = Credentials.from_authorized_user_file(str(토큰파일), 권한범위)
    if 자격 and 자격.expired and 자격.refresh_token:
        자격.refresh(Request())
        토큰파일.write_text(자격.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=자격)


def main():
    파서 = argparse.ArgumentParser()
    인자붙이기(파서)
    파서.add_argument("영상아이디")
    파서.add_argument("새제목")
    인자 = 파서.parse_args()

    if len(인자.새제목) > 100:
        sys.exit("[실패] 제목이 100자를 넘습니다: %d자" % len(인자.새제목))

    유튜브 = 인증(설정읽기(인자.채널))
    응답 = 유튜브.videos().list(part="snippet", id=인자.영상아이디).execute()
    if not 응답.get("items"):
        sys.exit("[실패] 영상을 찾지 못했습니다: %s" % 인자.영상아이디)

    조각 = 응답["items"][0]["snippet"]
    옛제목 = 조각["title"]
    조각["title"] = 인자.새제목

    유튜브.videos().update(
        part="snippet",
        body={"id": 인자.영상아이디, "snippet": 조각},
    ).execute()

    print("[완료] %s" % 인자.영상아이디)
    print("  전 : %s" % 옛제목)
    print("  후 : %s (%d자)" % (인자.새제목, len(인자.새제목)))


if __name__ == "__main__":
    main()
