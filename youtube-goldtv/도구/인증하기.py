# -*- coding: utf-8 -*-
"""유튜브 올리기 권한을 다시 받습니다 (황금주파수 전용).

`업로드.py` 가 쓰는 인증 토큰은 때가 지나면 만료됩니다. 그러면
`invalid_grant: Token has been expired or revoked` 가 나면서 올리기가
막힙니다. 이 도구를 한 번 돌려 다시 받으면 그 뒤로는 묻지 않습니다.

**사장님이 직접 돌리셔야 합니다.** 구글 로그인은 제가 대신 할 수 없습니다.

    python youtube-goldtv\도구\인증하기.py

브라우저가 열리면
  1. **gmahyun0915@gmail.com** 으로 로그인합니다
  2. 채널을 고르는 화면에서 **「황금 주파수 TV」** 를 고릅니다
  3. 권한 묻는 화면에서 「허용」을 누릅니다

끝나면 이 창에 어느 채널로 잡혔는지 찍힙니다. 「황금 주파수 TV」가
맞으면 토큰이 저장되고, 아니면 저장하지 않고 다시 하라고 알려 줍니다.

불심명언도 같은 방법으로 해 봅니다.

    python youtube-goldtv\도구\인증하기.py --채널 불심명언

전에 세 번 실패하고 「소유 계정이 없어서 안 된다」고 적어 두었는데,
2026-10-02 에 황금주파수를 다시 인증하면서 **진짜 원인은 브랜드 채널
고르는 화면을 건너뛴 것**일 수 있다는 걸 알았습니다. 그때도 개인 채널
(`myJukebox`)로 잡혔다가, 화면에서 브랜드 채널을 고르니 바로 됐습니다.
그래서 사장님 말씀대로 다시 시도합니다.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from 채널 import 설정읽기, 인자붙이기, 토큰경로, 클라이언트경로

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
except ImportError:
    sys.exit("[실패] 구글 라이브러리가 없습니다.\n"
             "       pip install google-api-python-client google-auth-oauthlib")

권한범위 = ["https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube"]


def 받기(설정):
    비밀파일 = 클라이언트경로(설정)
    토큰파일 = 토큰경로(설정)
    원하는채널 = 설정["유튜브"]["채널번호"]

    if not 비밀파일.exists():
        sys.exit("[실패] %s 이 없습니다." % 비밀파일)

    계정 = 설정["유튜브"].get("계정") or "gmahyun0915@gmail.com"
    print()
    print("브라우저가 열립니다.")
    print("  1. %s 으로 로그인" % 계정)
    print("     (이 계정이 아니면 그 채널이 붙어 있는 계정으로 하세요)")
    print("  2. **채널 고르는 화면**에서 「%s」 를 꼭 고릅니다" % 설정["표시이름"])
    print("     여기를 그냥 넘기면 그 계정의 개인 채널로 잡힙니다")
    print("  3. 「허용」")
    print()

    흐름 = InstalledAppFlow.from_client_secrets_file(str(비밀파일), 권한범위)
    자격 = 흐름.run_local_server(port=0, prompt="consent select_account")

    유튜브 = build("youtube", "v3", credentials=자격)
    답 = 유튜브.channels().list(part="snippet", mine=True).execute()
    항목 = 답.get("items") or []
    if not 항목:
        sys.exit("[실패] 이 계정에 채널이 없습니다. 다시 해 주세요.")

    잡힌번호 = 항목[0]["id"]
    잡힌이름 = 항목[0]["snippet"]["title"]
    print()
    print("잡힌 채널 : %s  (%s)" % (잡힌이름, 잡힌번호))
    print("원하는 채널: %s" % 원하는채널)

    if 잡힌번호 != 원하는채널:
        print()
        print("[멈춤] 다른 채널로 잡혔습니다. 토큰을 저장하지 않았습니다.")
        print("       다시 돌리시고, 채널 고르는 화면에서 「%s」 를" % 설정["표시이름"])
        print("       골라 주세요.")
        print()
        print("       그 화면이 아예 안 나오면 구글이 지난 권한을 기억하는")
        print("       것입니다. myaccount.google.com/permissions 에서 이 앱의")
        print("       액세스 권한을 지우고 다시 하세요.")
        sys.exit(1)

    토큰파일.write_text(자격.to_json(), encoding="utf-8")
    print()
    print("[완료] %s 에 저장했습니다." % 토큰파일)
    print("       이제 업로드.py 가 화면 없이 올립니다.")


if __name__ == "__main__":
    파서 = argparse.ArgumentParser(description="유튜브 올리기 권한 다시 받기")
    인자붙이기(파서)
    인자 = 파서.parse_args()
    설정 = 설정읽기(인자.채널)
    if 설정["이름"] != "황금주파수":
        sys.exit("[멈춤] 이 도구는 황금주파수 전용입니다.\n"
                 "       불심명언은 API 인증이 되지 않습니다 "
                 "(구글계정-채널-대응표.md 참고).")
    print("유튜브 권한 다시 받기 [%s]" % 설정["표시이름"])
    받기(설정)
