# -*- coding: utf-8 -*-
"""
배경 사진 위에 문구를 얹어 유튜브 썸네일(1280x720 PNG)을 만듭니다.

사용법:
    python 썸네일만들기.py "C:\\골드TV\\001-비우니-채워지더라"

작업 폴더에 필요한 것:
    배경.jpg (또는 배경.png)   ← 없으면 금빛 그러데이션으로 대신합니다
    썸네일.json                ← 문구 설정. 없으면 기본 문구가 들어갑니다

결과: 작업 폴더에 썸네일.png
"""
import json
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except ImportError:
    print("[실패] Pillow 가 필요합니다. 명령 프롬프트에서 아래를 실행하세요.")
    print("       pip install pillow")
    sys.exit(1)

가로, 세로 = 1280, 720

# 윈도우에 기본으로 깔려 있는 한글 글꼴들. 위에서부터 있는 것을 씁니다.
글꼴후보 = [
    r"C:\Windows\Fonts\malgunbd.ttf",   # 맑은 고딕 굵게
    r"C:\Windows\Fonts\malgun.ttf",
    r"C:\Windows\Fonts\NanumGothicBold.ttf",
    r"C:\Windows\Fonts\batang.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]

기본설정 = {
    "윗줄": "비우니",
    "아랫줄": "채워지더라",
    "아래작은글": "반야심경",
    "글자색": "#FFF4D6",
    "어둡게": 0.45,
}


def 글꼴찾기(크기):
    for 경로 in 글꼴후보:
        if Path(경로).exists():
            try:
                return ImageFont.truetype(경로, 크기)
            except OSError:
                continue
    print("[경고] 한글 글꼴을 못 찾아 기본 글꼴로 그립니다. 글자가 깨질 수 있습니다.")
    return ImageFont.load_default()


def 배경만들기(작업폴더, 설정):
    for 이름 in ("배경.jpg", "배경.png", "배경.jpeg", "배경.webp"):
        경로 = 작업폴더 / 이름
        if 경로.exists():
            그림 = Image.open(경로).convert("RGB")
            # 비율을 유지한 채 잘라서 화면을 꽉 채웁니다.
            배율 = max(가로 / 그림.width, 세로 / 그림.height)
            새크기 = (int(그림.width * 배율 + 1), int(그림.height * 배율 + 1))
            그림 = 그림.resize(새크기, Image.LANCZOS)
            왼쪽 = (그림.width - 가로) // 2
            위 = (그림.height - 세로) // 2
            return 그림.crop((왼쪽, 위, 왼쪽 + 가로, 위 + 세로))

    print("  배경 사진이 없어 금빛 그러데이션으로 만듭니다.")
    그림 = Image.new("RGB", (가로, 세로))
    그리기 = ImageDraw.Draw(그림)
    for y in range(세로):
        비율 = y / 세로
        빨강 = int(28 + (150 - 28) * 비율)
        초록 = int(22 + (104 - 22) * 비율)
        파랑 = int(18 + (38 - 18) * 비율)
        그리기.line([(0, y), (가로, y)], fill=(빨강, 초록, 파랑))
    return 그림


def 어둡게하기(그림, 세기):
    """글자가 묻히지 않도록 아래쪽을 더 어둡게 덮습니다."""
    덮개 = Image.new("L", (가로, 세로), 0)
    그리기 = ImageDraw.Draw(덮개)
    for y in range(세로):
        비율 = y / 세로
        그리기.line([(0, y), (가로, y)], fill=int(255 * 세기 * (0.35 + 0.65 * 비율)))
    덮개 = 덮개.filter(ImageFilter.GaussianBlur(30))
    return Image.composite(Image.new("RGB", (가로, 세로), (0, 0, 0)), 그림, 덮개)


def 외곽선글자(그리기, 위치, 글, 글꼴, 색, 외곽=6):
    x, y = 위치
    for dx in range(-외곽, 외곽 + 1, 2):
        for dy in range(-외곽, 외곽 + 1, 2):
            if dx * dx + dy * dy <= 외곽 * 외곽:
                그리기.text((x + dx, y + dy), 글, font=글꼴, fill=(0, 0, 0), anchor="mm")
    그리기.text((x, y), 글, font=글꼴, fill=색, anchor="mm")


def 두줄글꼴(윗줄, 아랫줄, 최대폭, 시작크기=175):
    """두 줄을 같은 크기로 맞춥니다. 긴 쪽을 기준으로 잡아야 균형이 잡힙니다."""
    크기 = 시작크기
    while 크기 > 44:
        글꼴 = 글꼴찾기(크기)
        가장긴폭 = max(글꼴.getbbox(글)[2] - 글꼴.getbbox(글)[0]
                     for 글 in (윗줄, 아랫줄) if 글)
        if 가장긴폭 <= 최대폭:
            return 글꼴, 크기
        크기 -= 5
    return 글꼴찾기(44), 44


def 만들기(작업폴더):
    작업폴더 = Path(작업폴더).resolve()
    설정 = dict(기본설정)
    설정파일 = 작업폴더 / "썸네일.json"
    if 설정파일.exists():
        with open(설정파일, encoding="utf-8") as f:
            설정.update(json.load(f))
        print("  썸네일.json 을 읽었습니다.")

    그림 = 배경만들기(작업폴더, 설정)
    그림 = 어둡게하기(그림, float(설정["어둡게"]))
    그리기 = ImageDraw.Draw(그림)

    최대폭 = 가로 - 160
    글꼴, 크기 = 두줄글꼴(설정["윗줄"], 설정["아랫줄"], 최대폭)
    줄간격 = int(크기 * 1.25)
    중심 = 세로 // 2 - 25

    외곽선글자(그리기, (가로 // 2, 중심 - 줄간격 // 2), 설정["윗줄"], 글꼴, 설정["글자색"])
    외곽선글자(그리기, (가로 // 2, 중심 + 줄간격 // 2), 설정["아랫줄"], 글꼴, 설정["글자색"])

    if 설정.get("아래작은글"):
        작은글꼴 = 글꼴찾기(46)
        외곽선글자(그리기, (가로 // 2, 세로 - 72), 설정["아래작은글"],
                 작은글꼴, "#E8D9A8", 외곽=4)

    결과 = 작업폴더 / "썸네일.png"
    그림.save(결과, "PNG")
    print(f"\n[완료] {결과}")
    print(f"       {가로}x{세로} / 유튜브 권장 규격입니다.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    print(f"\n썸네일 만들기: {sys.argv[1]}\n")
    만들기(sys.argv[1])
