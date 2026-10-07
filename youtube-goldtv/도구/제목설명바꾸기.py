# -*- coding: utf-8 -*-
r"""
이미 올린 영상의 제목·설명·태그만 바꿉니다. 영상을 다시 올리지 않습니다.

사용법
    python 제목설명바꾸기.py "D:\골드TV\_완성"

작업 폴더에 필요한 것
    업로드결과.txt   (업로드.py 가 남긴 영상 주소·번호)
    업로드정보.json  (바꿔 넣을 제목·설명·태그)

권한
    업로드만 하는 권한(youtube.upload)으로는 수정이 안 됩니다.
    처음 한 번은 브라우저가 열려 youtube 권한을 다시 물어봅니다.
"""

import io
import json
import re
import sys
from pathlib import Path

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload
except ImportError:
    sys.exit("[실패] pip install google-api-python-client google-auth-oauthlib")

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

권한범위 = ["https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube"]
도구폴더 = Path(__file__).resolve().parent


def 인증():
    토큰파일 = 도구폴더 / "인증토큰.json"
    비밀파일 = 도구폴더 / "client_secret.json"

    자격 = None
    if 토큰파일.exists():
        try:
            자격 = Credentials.from_authorized_user_file(str(토큰파일), 권한범위)
        except Exception:
            자격 = None
        # 올리기만 하는 권한으로 받아 둔 토큰이면 수정이 안 됩니다.
        # 그냥 두면 403 이 나므로, 모자라면 버리고 다시 받습니다.
        있는권한 = set(getattr(자격, "scopes", None) or [])
        if 자격 and not set(권한범위).issubset(있는권한):
            print("  지난번 권한으로는 수정이 안 됩니다. 권한을 다시 받습니다.")
            자격 = None
    if 자격 and 자격.expired and 자격.refresh_token:
        자격.refresh(Request())
    if not (자격 and 자격.valid):
        if not 비밀파일.exists():
            sys.exit("[실패] client_secret.json 이 없습니다: " + str(비밀파일))
        print("  브라우저가 열립니다. 올릴 때 쓰신 계정으로 로그인해 주세요.")
        자격 = InstalledAppFlow.from_client_secrets_file(
            str(비밀파일), 권한범위).run_local_server(port=0)
    토큰파일.write_text(자격.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=자격)


def 영상번호찾기(작업폴더):
    기록 = 작업폴더 / "업로드결과.txt"
    if not 기록.exists():
        sys.exit("[실패] 업로드결과.txt 가 없습니다: " + str(기록))
    글 = io.open(기록, encoding="utf-8").read()
    찾은것 = re.search(r"영상번호:\s*(\S+)", 글) or re.search(r"youtu\.be/(\S+)", 글)
    if not 찾은것:
        sys.exit("[실패] 업로드결과.txt 에서 영상 번호를 찾지 못했습니다.")
    return 찾은것.group(1).strip()


def 바꾸기(작업폴더):
    작업폴더 = Path(작업폴더).resolve()
    영상번호 = 영상번호찾기(작업폴더)
    정보 = json.load(io.open(작업폴더 / "업로드정보.json", encoding="utf-8"))
    유튜브 = 인증()

    # 기존 값을 먼저 읽어 두고 바꿀 것만 덮어씁니다.
    현재 = 유튜브.videos().list(part="snippet", id=영상번호).execute()
    if not 현재.get("items"):
        sys.exit("[실패] 그런 영상이 없습니다: " + 영상번호)
    조각 = 현재["items"][0]["snippet"]

    조각["title"] = 정보["제목"]
    조각["description"] = 정보.get("설명", "")
    조각["tags"] = 정보.get("태그", [])
    조각["categoryId"] = str(정보.get("카테고리", 10))
    조각["defaultLanguage"] = "ko"

    try:
        유튜브.videos().update(part="snippet",
                            body={"id": 영상번호, "snippet": 조각}).execute()
    except HttpError as e:
        sys.exit("[실패] 수정 중 오류: %s" % e)

    print("  제목을 바꿨습니다: " + 정보["제목"])

    썸네일 = next((작업폴더 / ("썸네일" + 끝) for 끝 in (".jpg", ".png", ".jpeg")
                 if (작업폴더 / ("썸네일" + 끝)).exists()), None)
    if 썸네일:
        크기 = 썸네일.stat().st_size
        if 크기 > 2 * 1024 * 1024:
            print("  [경고] 썸네일이 %.1fMB 라 2MB 한도를 넘습니다. 건너뜁니다."
                  % (크기 / 1048576))
        else:
            try:
                유튜브.thumbnails().set(
                    videoId=영상번호,
                    media_body=MediaFileUpload(str(썸네일))).execute()
                print("  썸네일도 바꿨습니다: " + 썸네일.name)
            except HttpError as e:
                print("  [경고] 썸네일 적용 실패: %s" % e)

    print("[완료] https://youtu.be/%s" % 영상번호)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    바꾸기(sys.argv[1])
