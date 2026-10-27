# -*- coding: utf-8 -*-
"""
수노(Suno) API로 노래를 만들고 mp3까지 내려받습니다.

사용법:
    python 노래만들기.py "C:\\골드TV\\001-비우니-채워지더라"

작업 폴더에 곡정보.json 이 있어야 합니다. 예시는 곡정보-예시.json 을 보세요.
API 키는 이 폴더의 api키.json 에 넣거나 환경변수 SUNO_API_KEY 로 둡니다.

주의: API 제공처마다 주소와 응답 형식이 조금씩 다릅니다.
      처음 한 번은 오류가 날 수 있는데, 화면에 찍히는 응답을 그대로 알려주시면
      맞게 고쳐드립니다.
"""
import json
import os
import sys
import time
from pathlib import Path
from urllib import error, request

기본주소 = "https://api.sunoapi.org"
생성경로 = "/api/v1/generate"
조회경로 = "/api/v1/generate/record-info"


def 키읽기(작업폴더):
    """API 키를 찾습니다. 키는 절대 소스코드에 적지 않습니다."""
    키 = os.environ.get("SUNO_API_KEY")
    if 키:
        return 키.strip()
    for 후보 in (작업폴더 / "api키.json", Path(__file__).parent / "api키.json"):
        if 후보.exists():
            with open(후보, encoding="utf-8") as f:
                자료 = json.load(f)
            키 = 자료.get("suno") or 자료.get("SUNO_API_KEY")
            if 키:
                return 키.strip()
    print("[실패] 수노 API 키를 찾지 못했습니다.")
    print("       도구 폴더에 api키.json 을 만들고 아래처럼 넣으세요.")
    print('       {"suno": "여기에_키", "유튜브_클라이언트파일": "client_secret.json"}')
    sys.exit(1)


def 보내기(주소, 키, 본문=None, 방식="POST"):
    자료 = json.dumps(본문).encode("utf-8") if 본문 is not None else None
    요청 = request.Request(주소, data=자료, method=방식, headers={
        "Authorization": f"Bearer {키}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        # 파이썬 기본 User-Agent 는 클라우드플레어가 1010 으로 막습니다.
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/140.0.0.0 Safari/537.36",
    })
    try:
        with request.urlopen(요청, timeout=60) as 응답:
            return json.loads(응답.read().decode("utf-8"))
    except error.HTTPError as e:
        본문글 = e.read().decode("utf-8", "replace")
        print(f"[실패] 서버가 {e.code} 로 답했습니다.")
        print(본문글[:2000])
        print("\n위 내용을 그대로 알려주시면 주소나 형식을 맞게 고쳐드립니다.")
        sys.exit(1)
    except error.URLError as e:
        print(f"[실패] 서버에 연결하지 못했습니다: {e.reason}")
        sys.exit(1)


def 곡정보읽기(작업폴더):
    파일 = 작업폴더 / "곡정보.json"
    if not 파일.exists():
        print(f"[실패] {파일} 이 없습니다. 곡정보-예시.json 을 복사해 쓰세요.")
        sys.exit(1)
    with open(파일, encoding="utf-8") as f:
        return json.load(f)


def 내려받기(주소, 저장할곳):
    print(f"  내려받는 중: {저장할곳.name}")
    with request.urlopen(주소, timeout=300) as 응답, open(저장할곳, "wb") as f:
        while True:
            덩어리 = 응답.read(1 << 16)
            if not 덩어리:
                break
            f.write(덩어리)


def 음원주소들(자료):
    """제공처마다 응답 구조가 달라서, 오디오 주소로 보이는 값을 전부 훑어 찾습니다."""
    찾은것 = []

    def 훑기(값):
        if isinstance(값, dict):
            for 키, 하위 in 값.items():
                if (isinstance(하위, str) and 하위.startswith("http")
                        and (하위.endswith(".mp3") or "audio" in 키.lower())):
                    찾은것.append(하위)
                else:
                    훑기(하위)
        elif isinstance(값, list):
            for 하위 in 값:
                훑기(하위)

    훑기(자료)
    # 순서를 지키면서 중복만 걸러냅니다.
    return list(dict.fromkeys(찾은것))


def 만들기(작업폴더):
    작업폴더 = Path(작업폴더).resolve()
    작업폴더.mkdir(parents=True, exist_ok=True)

    곡 = 곡정보읽기(작업폴더)
    키 = 키읽기(작업폴더)
    주소 = 곡.get("api주소", 기본주소).rstrip("/")

    본문 = {
        "customMode": True,
        "instrumental": False,
        "prompt": 곡["가사"],
        "style": 곡["스타일"],
        "title": 곡["제목"],
        "model": 곡.get("모델", "V4_5PLUS"),
    }
    if 곡.get("콜백주소"):
        본문["callBackUrl"] = 곡["콜백주소"]

    print(f"  제목  : {곡['제목']}")
    print(f"  스타일: {곡['스타일'][:60]}...")
    print("  수노에 생성을 요청합니다...")

    응답 = 보내기(주소 + 생성경로, 키, 본문)
    작업번호 = (응답.get("data") or {}).get("taskId") or 응답.get("taskId")
    if not 작업번호:
        print("[실패] 작업 번호를 못 받았습니다. 응답은 아래와 같습니다.")
        print(json.dumps(응답, ensure_ascii=False, indent=2)[:2000])
        sys.exit(1)

    print(f"  작업 번호: {작업번호}")
    print("  생성을 기다립니다. 보통 1~3분 걸립니다.")

    마감 = time.time() + 15 * 60
    while time.time() < 마감:
        time.sleep(15)
        상태 = 보내기(f"{주소}{조회경로}?taskId={작업번호}", 키, 방식="GET")
        주소들 = 음원주소들(상태)
        상태글 = json.dumps(상태, ensure_ascii=False)
        if 주소들:
            print(f"  완성됐습니다. {len(주소들)}개 후보를 받았습니다.")
            for 번호, 음원 in enumerate(주소들, 1):
                이름 = "노래.mp3" if 번호 == 1 else f"노래-후보{번호}.mp3"
                내려받기(음원, 작업폴더 / 이름)
            print(f"\n[완료] {작업폴더}")
            print("       여러 개면 들어보고 가장 좋은 것을 '노래.mp3' 로 바꿔두세요.")
            return
        if '"FAILED"' in 상태글 or '"error"' in 상태글.lower():
            print("[실패] 생성이 실패했습니다. 응답은 아래와 같습니다.")
            print(json.dumps(상태, ensure_ascii=False, indent=2)[:2000])
            sys.exit(1)
        print("  아직 만드는 중...", flush=True)

    print("[실패] 15분이 지나도 끝나지 않았습니다. 수노 사이트에서 직접 확인해 보세요.")
    sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    print(f"\n노래 만들기: {sys.argv[1]}\n")
    만들기(sys.argv[1])
