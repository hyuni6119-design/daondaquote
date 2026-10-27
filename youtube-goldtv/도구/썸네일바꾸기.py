# -*- coding: utf-8 -*-
r"""
이미 올린 영상의 썸네일만 갈아끼웁니다.

영상을 다시 올리지 않고 그림만 바꿉니다. 문구가 마음에 안 들어 다시
만들었을 때 씁니다.

사용법
    python 썸네일바꾸기.py <동영상ID> "D:\골드TV\_완성\썸네일.jpg"
    python 썸네일바꾸기.py --채널 불심명언 <동영상ID> "...jpg"
"""
import argparse
import sys
from pathlib import Path

from 채널 import 설정읽기, 인자붙이기, 토큰경로, 클라이언트경로

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

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
    파서.add_argument("썸네일")
    인자 = 파서.parse_args()

    설정 = 설정읽기(인자.채널)
    그림 = Path(인자.썸네일)
    if not 그림.exists():
        sys.exit("[실패] 썸네일이 없습니다: %s" % 그림)
    # 캡컷에서 1080P 로 내보내면 2MB 를 넘는 일이 흔합니다. 그때마다
    # 손으로 줄이지 않도록 업로드.py 와 같은 방법으로 알아서 줄입니다.
    from 업로드 import 줄이기
    작은것 = 줄이기(그림)
    if 작은것 is None:
        sys.exit("[실패] 썸네일이 2MB를 넘는데 줄이지 못했습니다. pillow 를 설치하세요.")
    그림 = 작은것
    크기 = 그림.stat().st_size

    유튜브 = 인증(설정)
    유튜브.thumbnails().set(
        videoId=인자.영상아이디,
        media_body=MediaFileUpload(str(그림)),
    ).execute()
    print("[완료] %s 썸네일 교체 (%.2fMB)" % (인자.영상아이디, 크기 / 1e6))


if __name__ == "__main__":
    main()
