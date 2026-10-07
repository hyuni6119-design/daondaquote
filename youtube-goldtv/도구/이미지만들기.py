# -*- coding: utf-8 -*-
"""
골드TV 이미지 생성기 (OpenAI 이미지 API)

용도가 둘입니다. 프롬프트가 서로 다르니 --용도 로 고릅니다.

    썸네일    : 천수관음상만. 사람 없음. 목록에 보이는 그림
    재생화면  : 동자승 수채화. 노래 나오는 동안 깔리는 그림

둘 다 오른쪽에 대상을 두고 왼쪽은 제목 글씨 자리로 비워 둡니다.

사용법
    python 이미지만들기.py --용도 썸네일   "장면 설명" "저장경로.png"
    python 이미지만들기.py --용도 재생화면 "장면 설명" "저장경로.png"

한 용도에 한 장만 만듭니다. 시안을 여러 장 뽑지 않습니다.
키는 같은 폴더의 api키.json 의 "openai" 항목에서 읽습니다.
"""

import argparse
import base64
import io
import json
import os
import sys
import urllib.error
import urllib.request

여기 = os.path.dirname(os.path.abspath(__file__))
키파일 = os.path.join(여기, "api키.json")

모델 = "gpt-image-2.5-sunburst"
크기 = "1536x1024"   # API 가 주는 가로 크기 (3:2)

# API 는 3:2(1536x1024)로만 줍니다. 유튜브 화면은 16:9 라서 차이가 나는데,
# 비율 맞추는 일은 캡컷 안에서 배율·위치로 합니다(사장님 지시). 그림 파일
# 자체는 손대지 않습니다. 꼭 미리 잘라 두고 싶을 때만 --자르기 를 씁니다.
내보낼비율 = 16 / 9
자르는곳 = {"썸네일": "위", "재생화면": "가운데"}

# 사장님이 정하신 문장입니다. 임의로 고치지 않습니다.
썸네일_프롬프트 = (
    "A serene storybook watercolor illustration for a Korean Buddhist YouTube "
    "thumbnail. Place only a majestic golden Thousand-Armed Avalokiteshvara "
    "Buddha statue on the right side, enlarged and visually dominant, with "
    "delicate golden arms arranged gracefully behind the statue and a radiant "
    "golden halo. The Buddha should look clean, sharp, elegant, peaceful, and "
    "highly detailed.\n\n"
    "Use a bright, warm, uncluttered watercolor background on the left side "
    "with soft beige, muted gold, light brown, and gentle sunset tones. Keep "
    "the entire left half open and simple for adding Korean thumbnail text "
    "later. Do not make the left side too dark.\n\n"
    "Include a traditional Korean temple roof, subtle lotus flowers, gentle "
    "incense smoke, and warm golden light. Peaceful and sacred atmosphere, "
    "soft watercolor washes, hand-painted paper texture, cinematic lighting, "
    "rich gold and red accents, horizontal 16:9 composition.\n\n"
    "No monk, no people, no extra statues, no animals, no text, no Korean "
    "letters, no English letters, no numbers, no captions, no logo, no "
    "watermark, no calligraphy, no signboard, no written decorations."
)

재생화면_프롬프트 = (
    "A gentle storybook watercolor illustration of a young Korean Buddhist "
    "novice monk (dongja-seung) in simple gray robes, seen from a "
    "three-quarter rear view, kneeling respectfully with hands clasped in "
    "prayer before a serene golden Buddha statue inside a quiet traditional "
    "Korean temple. "
    "COMPOSITION IS IMPORTANT: place the golden Buddha statue and the novice "
    "monk in the CENTER of the frame, balanced and well proportioned, with "
    "comfortable margins on both the left and the right. The Buddha statue "
    "must be well rendered, clearly visible and dignified. Keep the overall "
    "image bright and warm; do not make it dark. "
    "A natural landscape sits behind the scene but stays subtle: distant "
    "mountains or trees seen faintly through wooden lattice windows, softly "
    "blurred and low in contrast so it never competes with the foreground. "
    "Warm candlelight and soft sunlight, delicate incense smoke, lotus "
    "flowers and subtle temple details, peaceful spiritual atmosphere, "
    "tender childlike fairy-tale mood, soft watercolor washes, hand-painted "
    "paper texture, muted warm pastel palette, elegant composition, high "
    "detail, cinematic horizontal 16:9 aspect ratio. "
    "No text, no letters, no logos, no watermark, no modern objects, "
    "respectful non-photorealistic art."
)

프롬프트표 = {
    "썸네일": 썸네일_프롬프트,
    "재생화면": 재생화면_프롬프트,
}


def 키읽기():
    if not os.path.exists(키파일):
        sys.exit("api키.json 이 없습니다: " + 키파일)
    키 = json.load(io.open(키파일, encoding="utf-8")).get("openai", "").strip()
    if not 키:
        sys.exit('api키.json 에 "openai" 키가 비어 있습니다.')
    return 키


def 만들기(용도, 장면, 저장경로, 미리자르기=False):
    바탕 = 프롬프트표[용도]
    프롬프트 = 바탕 + ("\n\nScene for this song: " + 장면 if 장면 else "")

    본문 = json.dumps({
        "model": 모델,
        "prompt": 프롬프트,
        "size": 크기,
        "n": 1,
    }).encode("utf-8")

    요청 = urllib.request.Request(
        "https://api.openai.com/v1/images/generations",
        data=본문,
        headers={
            "Authorization": "Bearer " + 키읽기(),
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(요청, timeout=300) as 응답:
            결과 = json.load(응답)
    except urllib.error.HTTPError as e:
        sys.exit("API 오류 %s: %s" % (e.code, e.read().decode()[:500]))

    os.makedirs(os.path.dirname(저장경로) or ".", exist_ok=True)
    with open(저장경로, "wb") as f:
        f.write(base64.b64decode(결과["data"][0]["b64_json"]))

    if 미리자르기:
        자르기(저장경로, 자르는곳.get(용도, "가운데"))
    print("saved:", 저장경로, "%.1fMB" % (os.path.getsize(저장경로) / 1048576))
    return 저장경로


def 자르기(경로, 어디):
    """받은 그림을 16:9 로 잘라 둡니다. 썸네일은 머리가 잘리지 않게 위쪽을 남깁니다."""
    try:
        from PIL import Image
    except ImportError:
        print("  (pillow 가 없어 16:9 자르기를 건너뜁니다: pip install pillow)")
        return
    그림 = Image.open(경로)
    목표높이 = int(round(그림.width / 내보낼비율))
    if 목표높이 >= 그림.height:
        return
    남는것 = 그림.height - 목표높이
    위 = 0 if 어디 == "위" else (남는것 if 어디 == "아래" else 남는것 // 2)
    그림.crop((0, 위, 그림.width, 위 + 목표높이)).save(경로)
    print("  16:9 로 잘랐습니다: %dx%d (%s 남김)" % (그림.width, 목표높이, 어디))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--용도", choices=list(프롬프트표), required=True)
    p.add_argument("장면", help="이 곡에 맞는 장면 설명 (영어). 없으면 빈 문자열")
    p.add_argument("저장경로", help="저장할 png 경로")
    p.add_argument("--자르기", action="store_true",
                   help="받은 그림을 16:9 로 미리 잘라 둡니다 (기본은 안 자름)")
    a = p.parse_args()
    만들기(a.용도, a.장면, a.저장경로, a.자르기)
