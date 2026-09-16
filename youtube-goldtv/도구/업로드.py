# -*- coding: utf-8 -*-
"""
완성된 영상을 제목·설명·태그·썸네일까지 한꺼번에 유튜브에 올립니다.

사용법:
    python 업로드.py "C:\\골드TV\\001-비우니-채워지더라"

작업 폴더에 필요한 것:
    완성.mp4        (필수)
    업로드정보.json  (필수)  ← 제목, 설명, 태그, 공개 설정
    썸네일.png      (선택)

처음 한 번은 브라우저가 열리며 구글 로그인을 묻습니다.
그 다음부터는 인증토큰.json 이 저장되어 묻지 않습니다.
"""
import json
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
    print("[실패] 구글 라이브러리가 필요합니다. 명령 프롬프트에서 아래를 실행하세요.")
    print("       pip install google-api-python-client google-auth-oauthlib")
    sys.exit(1)

권한범위 = ["https://www.googleapis.com/auth/youtube.upload"]
도구폴더 = Path(__file__).parent


def 인증():
    """처음 한 번만 브라우저로 로그인하고, 이후에는 저장된 토큰을 씁니다."""
    토큰파일 = 도구폴더 / "인증토큰.json"
    비밀파일 = 도구폴더 / "client_secret.json"

    자격 = None
    if 토큰파일.exists():
        자격 = Credentials.from_authorized_user_file(str(토큰파일), 권한범위)

    if 자격 and 자격.expired and 자격.refresh_token:
        자격.refresh(Request())
    elif not (자격 and 자격.valid):
        if not 비밀파일.exists():
            print(f"[실패] {비밀파일} 이 없습니다.")
            print("       구글 클라우드 콘솔에서 받은 OAuth 클라이언트 파일을")
            print("       client_secret.json 이라는 이름으로 이 폴더에 넣으세요.")
            print("       자세한 순서는 도구/사용법.md 를 보세요.")
            sys.exit(1)
        흐름 = InstalledAppFlow.from_client_secrets_file(str(비밀파일), 권한범위)
        print("  브라우저가 열립니다. 구글 계정으로 로그인해 주세요.")
        자격 = 흐름.run_local_server(port=0)

    토큰파일.write_text(자격.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=자격)


def 정보읽기(작업폴더):
    파일 = 작업폴더 / "업로드정보.json"
    if not 파일.exists():
        print(f"[실패] {파일} 이 없습니다. 업로드정보-예시.json 을 복사해 쓰세요.")
        sys.exit(1)
    with open(파일, encoding="utf-8") as f:
        return json.load(f)


def 올리기(작업폴더):
    작업폴더 = Path(작업폴더).resolve()
    영상 = 작업폴더 / "완성.mp4"
    if not 영상.exists():
        print(f"[실패] {영상} 이 없습니다. 먼저 영상만들기를 실행하세요.")
        sys.exit(1)

    정보 = 정보읽기(작업폴더)
    유튜브 = 인증()

    공개설정 = {"privacyStatus": 정보.get("공개범위", "private")}
    if 정보.get("예약시간"):
        # 예약을 걸면 그때까지는 비공개 상태로 있어야 합니다.
        공개설정 = {"privacyStatus": "private", "publishAt": 정보["예약시간"]}

    본문 = {
        "snippet": {
            "title": 정보["제목"],
            "description": 정보.get("설명", ""),
            "tags": 정보.get("태그", []),
            "categoryId": str(정보.get("카테고리", 10)),   # 10 = 음악
            "defaultLanguage": "ko",
            "defaultAudioLanguage": "ko",
        },
        "status": {
            **공개설정,
            "selfDeclaredMadeForKids": False,
            "license": "youtube",
        },
    }

    크기 = 영상.stat().st_size / (1024 * 1024)
    print(f"  제목: {정보['제목']}")
    print(f"  파일: {영상.name} ({크기:.0f}MB)")
    print("  올리는 중입니다. 파일이 크면 오래 걸립니다...")

    업로드 = MediaFileUpload(str(영상), chunksize=8 * 1024 * 1024, resumable=True)
    요청 = 유튜브.videos().insert(part="snippet,status", body=본문, media_body=업로드)

    응답 = None
    while 응답 is None:
        try:
            진행, 응답 = 요청.next_chunk()
            if 진행:
                print(f"    {int(진행.progress() * 100)}%", flush=True)
        except HttpError as e:
            print(f"[실패] 업로드 중 오류: {e}")
            sys.exit(1)

    영상번호 = 응답["id"]
    주소 = f"https://youtu.be/{영상번호}"
    print(f"\n  업로드 완료: {주소}")

    썸네일 = 작업폴더 / "썸네일.png"
    if 썸네일.exists():
        print("  썸네일을 올리는 중...")
        try:
            유튜브.thumbnails().set(videoId=영상번호,
                                  media_body=MediaFileUpload(str(썸네일))).execute()
            print("  썸네일 적용 완료")
        except HttpError as e:
            print(f"  [경고] 썸네일 적용 실패: {e}")
            print("         채널 인증이 안 되어 있으면 맞춤 썸네일을 쓸 수 없습니다.")

    기록 = 작업폴더 / "업로드결과.txt"
    기록.write_text(f"{주소}\n영상번호: {영상번호}\n제목: {정보['제목']}\n",
                   encoding="utf-8")

    print(f"\n[완료] {주소}")
    if 정보.get("예약시간"):
        print(f"       {정보['예약시간']} 에 자동 공개됩니다.")
    else:
        print(f"       현재 상태: {정보.get('공개범위', 'private')}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    print(f"\n유튜브 업로드: {sys.argv[1]}\n")
    올리기(sys.argv[1])
