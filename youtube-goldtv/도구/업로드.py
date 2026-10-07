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
그 다음부터는 토큰 파일이 저장되어 묻지 않습니다. 토큰은 채널마다 다릅니다
(황금주파수는 인증토큰.json, 불심명언은 인증토큰-불심명언.json).
"""
import argparse
import json
import sys
from pathlib import Path

from 채널 import 설정읽기, 인자붙이기, 토큰경로, 클라이언트경로

# 윈도우 명령 창은 기본이 cp949 라서 제목의 이모지를 찍다가 멈춥니다.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

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

권한범위 = ["https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube"]

도구폴더 = Path(__file__).parent


def 인증(설정):
    """처음 한 번만 브라우저로 로그인하고, 이후에는 저장된 토큰을 씁니다.

    토큰은 채널마다 따로 둡니다. 한 파일을 돌려쓰면 불심명언에 로그인한
    토큰으로 황금주파수에 올리려다 채널확인에서 막히고, 그때마다 다시
    로그인해야 합니다.
    """
    토큰파일 = 토큰경로(설정)
    비밀파일 = 클라이언트경로(설정)

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
        # prompt="consent" + "select_account" 를 붙여야 채널을 다시 묻습니다.
        # 이걸 빼면 그 구글 계정에 이미 준 권한이 남아 있을 때, 브랜드
        # 채널을 골라도 개인 계정 채널로 토큰이 발급됩니다. 불심명언을
        # 골랐는데 「웃어봐yo」로 잡히는 일이 실제로 세 번 있었습니다.
        자격 = 흐름.run_local_server(port=0, prompt="consent select_account")

    토큰파일.write_text(자격.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=자격)


def 정보읽기(작업폴더):
    파일 = 작업폴더 / "업로드정보.json"
    if not 파일.exists():
        print(f"[실패] {파일} 이 없습니다. 업로드정보-예시.json 을 복사해 쓰세요.")
        sys.exit(1)
    with open(파일, encoding="utf-8") as f:
        return json.load(f)


def 줄이기(그림경로):
    """유튜브 썸네일은 2MB 까지입니다. 넘으면 1280x720 jpg 로 줄여서 씁니다."""
    한도 = 2 * 1024 * 1024
    if not 그림경로.exists() or 그림경로.stat().st_size <= 한도:
        return 그림경로
    try:
        from PIL import Image
    except ImportError:
        print("  [경고] 썸네일이 2MB를 넘는데 pillow 가 없어 줄이지 못했습니다.")
        return None
    원래크기 = 그림경로.stat().st_size
    작은것 = 그림경로.with_name("썸네일-작게.jpg")
    그림 = Image.open(그림경로).convert("RGB")
    if 그림.width > 1280:
        그림 = 그림.resize((1280, round(1280 * 그림.height / 그림.width)),
                        Image.LANCZOS)
    for 품질 in (92, 86, 80, 74, 68):
        그림.save(작은것, "JPEG", quality=품질, optimize=True)
        if 작은것.stat().st_size <= 한도:
            break
    print("  썸네일을 %.1fMB -> %.1fMB 로 줄였습니다." % (
        원래크기 / 1048576, 작은것.stat().st_size / 1048576))
    return 작은것


def 채널확인(유튜브, 설정):
    """지금 인증된 채널이 올려야 할 채널인지 먼저 봅니다.

    계정 선택 화면에서 엉뚱한 채널을 고르면 몇 백 MB를 다 올린 뒤에야
    알게 됩니다. 실제로 두 번 그랬습니다. 그래서 올리기 전에 봅니다.
    """
    올릴채널 = 설정["유튜브"]["채널번호"]
    try:
        내것 = 유튜브.channels().list(part="snippet", mine=True).execute()
    except HttpError as e:
        print(f"  [경고] 채널을 확인하지 못했습니다: {e}")
        return
    항목 = 내것.get("items") or []
    if not 항목:
        sys.exit("[실패] 이 계정에 유튜브 채널이 없습니다.")
    이름 = 항목[0]["snippet"]["title"]
    번호 = 항목[0]["id"]
    if 올릴채널 and 번호 != 올릴채널:
        print(f"[실패] 엉뚱한 채널에 연결되어 있습니다: {이름} ({번호})")
        print(f"       올려야 할 채널: {설정['표시이름']} ({올릴채널})")
        print(f"       도구/{설정['유튜브']['토큰파일']} 을 지우고 다시 실행한 뒤,")
        print("       계정 선택 화면에서 이 채널을 고르세요.")
        print("       (구글 계정을 고르는 화면과 채널을 고르는 화면이")
        print("        차례로 두 번 나옵니다. 두 번째 화면이 채널입니다.)")
        sys.exit(1)
    print(f"  채널: {이름}")


def 인증만하기(설정):
    """영상 없이 그 채널의 인증 토큰만 만들어 둡니다.

    채널을 새로 붙일 때 한 번 씁니다. 브라우저가 열리면 사장님이 직접
    구글 계정과 채널을 고르셔야 합니다. 비밀번호는 제가 다루지 않습니다.
    """
    print("  브라우저가 열립니다.")
    print("  화면이 두 번 나옵니다 - 먼저 구글 계정, 그 다음 채널입니다.")
    print("  두 번째 화면에서 「%s」 를 고르세요." % 설정["표시이름"])
    print()
    유튜브 = 인증(설정)
    채널확인(유튜브, 설정)
    내것 = 유튜브.channels().list(part="snippet,statistics", mine=True).execute()
    항목 = 내것["items"][0]
    print()
    print("[완료] %s 채널로 인증되었습니다." % 항목["snippet"]["title"])
    print("       구독 %s명 · 영상 %s개"
          % (항목["statistics"].get("subscriberCount", "?"),
             항목["statistics"].get("videoCount", "?")))
    print("       토큰: %s" % 토큰경로(설정))


def 올리기(작업폴더, 설정):
    작업폴더 = Path(작업폴더).resolve()
    영상 = 작업폴더 / "완성.mp4"
    if not 영상.exists():
        print(f"[실패] {영상} 이 없습니다. 먼저 영상만들기를 실행하세요.")
        sys.exit(1)

    정보 = 정보읽기(작업폴더)
    유튜브 = 인증(설정)
    채널확인(유튜브, 설정)

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

    # 주소를 먼저 남깁니다. 썸네일에서 실패해도 영상 번호는 남아야 하니까요.
    기록 = 작업폴더 / "업로드결과.txt"
    기록.write_text(f"{주소}\n영상번호: {영상번호}\n제목: {정보['제목']}\n",
                   encoding="utf-8")

    썸네일 = next((작업폴더 / f"썸네일{끝}" for 끝 in (".jpg", ".png", ".jpeg")
                 if (작업폴더 / f"썸네일{끝}").exists()), None)
    썸네일 = 줄이기(썸네일) if 썸네일 else None
    if 썸네일 and 썸네일.exists():
        print("  썸네일을 올리는 중...")
        try:
            유튜브.thumbnails().set(videoId=영상번호,
                                  media_body=MediaFileUpload(str(썸네일))).execute()
            print("  썸네일 적용 완료")
        except HttpError as e:
            print(f"  [경고] 썸네일 적용 실패: {e}")
            print("         채널 인증이 안 되어 있으면 맞춤 썸네일을 쓸 수 없습니다.")

    print(f"\n[완료] {주소}")
    if 정보.get("예약시간"):
        print(f"       {정보['예약시간']} 에 자동 공개됩니다.")
    else:
        print(f"       현재 상태: {정보.get('공개범위', 'private')}")


if __name__ == "__main__":
    파서 = argparse.ArgumentParser(description="완성된 영상을 유튜브에 올립니다")
    파서.add_argument("작업폴더", nargs="?", default="",
                     help="완성.mp4 와 업로드정보.json 이 있는 폴더 "
                          "(생략하면 그 채널의 _완성 폴더)")
    파서.add_argument("--인증만", action="store_true",
                     help="영상은 올리지 않고 그 채널의 인증 토큰만 만듭니다")
    인자붙이기(파서)
    인자 = 파서.parse_args()

    설정 = 설정읽기(인자.채널)
    if 인자.인증만:
        print()
        print("유튜브 인증 [%s]" % 설정["표시이름"])
        print()
        인증만하기(설정)
        sys.exit(0)
    폴더 = 인자.작업폴더 or 설정["폴더"]["완성"]
    print()
    print("유튜브 업로드 [%s]: %s" % (설정["표시이름"], 폴더))
    print()
    올리기(폴더, 설정)
