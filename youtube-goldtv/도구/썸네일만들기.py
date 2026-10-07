# -*- coding: utf-8 -*-
r"""
골드TV 썸네일 만들기

잘 나가는 불교 채널 썸네일을 뜯어보고 맞춘 형태입니다.

    · 줄마다 반투명 검은 띠를 깔아 그림 위에서도 글자가 또렷합니다
    · 줄마다 크기를 달리해 강약을 줍니다 (핵심 줄이 가장 큽니다)
    · 큰따옴표로 감싼 말은 색을 달리해 튀게 합니다
    · 두꺼운 검은 외곽선, 왼쪽 정렬, 오른쪽은 불상 자리로 비웁니다

사용법
    python 썸네일만들기.py 배경.png 출력.png ^
        --줄 "지금 꼭 틀어놓으세요" --줄 "뿌린 대로 거두어" ^
        --줄 "\"큰 복\" 쏟아집니다"

    여러 장을 한 번에
    python 썸네일만들기.py 배경.png --목록 문구들.json
    [{"줄":["1줄","2줄","3줄"], "출력":"D:/.../안1.png"}, ...]
"""

import argparse
import io
import json
import os
import re
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.exit("pillow 가 없습니다:  pip install pillow")

가로, 세로 = 1280, 720

사용자글꼴 = os.path.join(
    os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts")

글꼴표 = {
    "안성탕면": os.path.join(사용자글꼴, "Ansungtangmyun-Bold.ttf"),
    "안성탕면ESG": os.path.join(사용자글꼴, "Ansungtangmyun-ESG.ttf"),
    "을지로": os.path.join(사용자글꼴, "BMEULJIRO.otf"),
    "지마켓": os.path.join(사용자글꼴, "GmarketSansTTFBold.ttf"),
    "어그로": os.path.join(사용자글꼴, "SB 어그로 B.ttf"),
    "한나": os.path.join(사용자글꼴, "BMHANNAProOTF.otf"),
    "도현": os.path.join(사용자글꼴, "BMDOHYEON_ttf.ttf"),
    "맑은고딕": r"C:\Windows\Fonts\malgunbd.ttf",
}

# 줄 색 (강조어가 아닌 보통 글자)
줄색 = ["#FFFFFF", "#7CFF4A", "#FFFFFF", "#FFE400"]
# 큰따옴표로 감싼 말에 쓰는 색 — 같은 줄에서 확 튀게 합니다
강조색 = ["#FFE400", "#FFE400", "#FF4A6E", "#FF4A6E"]
외곽색 = (8, 6, 4)

# 줄마다 크기 비율 (평평하지 않게 강약을 줍니다)
크기비율 = [0.92, 1.0, 1.0, 1.08]

왼쪽여백 = 34
위여백 = 22
아래여백 = 22
글상자폭 = 720          # 오른쪽은 불상 자리로 비웁니다
최소자간비율 = -0.12
띠투명도 = 170          # 0=없음, 255=완전 검정
띠여백 = 12
줄틈 = 10            # 줄과 줄 사이 간격


def 글꼴열기(이름, 크기):
    경로 = 글꼴표.get(이름)
    if not 경로 or not os.path.exists(경로):
        경로 = next(p for p in 글꼴표.values() if os.path.exists(p))
    return ImageFont.truetype(경로, max(8, int(크기)))


def 조각내기(글):
    """큰따옴표를 기준으로 (글자, 강조인가) 로 쪼갭니다."""
    조각 = []
    for 부분 in re.split(r'("[^"]*")', 글):
        if not 부분:
            continue
        조각.append((부분, 부분.startswith('"') and 부분.endswith('"')))
    return 조각 or [(글, False)]


def 줄폭(글, 글꼴, 자간):
    return sum(글꼴.getlength(c) for c in 글) + max(0, len(글) - 1) * 자간


def 자간계산(글, 글꼴, 최대폭):
    자연폭 = sum(글꼴.getlength(c) for c in 글)
    틈 = len(글) - 1
    if 틈 <= 0 or 자연폭 <= 최대폭:
        return 0.0
    return max((최대폭 - 자연폭) / 틈, 글꼴.size * 최소자간비율)


def 한줄그리기(그리기, x, y, 글, 글꼴, 보통색, 튀는색, 자간, 외곽):
    """한 글자씩 그리며 자간을 적용하고, 따옴표 안은 색을 바꿉니다."""
    좌표 = []
    커서 = x
    for 부분, 강조인가 in 조각내기(글):
        for c in 부분:
            좌표.append((커서, c, 튀는색 if 강조인가 else 보통색))
            커서 += 글꼴.getlength(c) + 자간

    보폭 = max(2, 외곽 // 3)
    for dx in range(-외곽, 외곽 + 1, 보폭):
        for dy in range(-외곽, 외곽 + 1, 보폭):
            if dx or dy:
                for cx, c, _ in 좌표:
                    그리기.text((cx + dx, y + dy), c, font=글꼴,
                              fill=외곽색, anchor="ls")
    for cx, c, 색 in 좌표:
        그리기.text((cx, y), c, font=글꼴, fill=색, anchor="ls")
    return 커서 - x


def 배경열기(경로):
    그림 = Image.open(경로).convert("RGB")
    비율 = max(가로 / 그림.width, 세로 / 그림.height)
    새 = (int(그림.width * 비율 + 0.5), int(그림.height * 비율 + 0.5))
    그림 = 그림.resize(새, Image.LANCZOS)
    좌 = (그림.width - 가로) // 2
    상 = (그림.height - 세로) // 2
    return 그림.crop((좌, 상, 좌 + 가로, 상 + 세로))


def 기본크기(줄들, 글꼴이름):
    """줄들이 세로로 딱 들어가는 기준 크기를 찾습니다."""
    쓸높이 = 세로 - 위여백 - 아래여백
    비율들 = [크기비율[i % len(크기비율)] for i in range(len(줄들))]
    크기 = int(쓸높이 / max(1, sum(비율들)) * 0.95)
    while 크기 > 24:
        총높이 = 0
        넘침 = False
        for 글, 비율 in zip(줄들, 비율들):
            글꼴 = 글꼴열기(글꼴이름, 크기 * 비율)
            민글 = 글.replace('"', "")
            최소폭 = (sum(글꼴.getlength(c) for c in 민글)
                   + (len(민글) - 1) * 글꼴.size * 최소자간비율)
            if 최소폭 > 글상자폭:
                넘침 = True
                break
            총높이 += (글꼴.getbbox("한김")[3] - 글꼴.getbbox("한김")[1]) + 띠여백 * 2
        if not 넘침 and 총높이 <= 쓸높이:
            return 크기
        크기 -= 2
    return 24


def 만들기(배경경로, 출력경로, 줄들, 글꼴이름="안성탕면"):
    줄들 = [s.strip() for s in 줄들 if s and s.strip()]
    if not 줄들:
        sys.exit("문구가 비어 있습니다.")

    그림 = 배경열기(배경경로)
    띠판 = Image.new("RGBA", 그림.size, (0, 0, 0, 0))
    띠그리기 = ImageDraw.Draw(띠판)

    기준 = 기본크기(줄들, 글꼴이름)
    비율들 = [크기비율[i % len(크기비율)] for i in range(len(줄들))]
    글꼴들 = [글꼴열기(글꼴이름, 기준 * b) for b in 비율들]
    높이들 = [f.getbbox("한김")[3] - f.getbbox("한김")[1] for f in 글꼴들]

    칸높이들 = [h + 띠여백 * 2 for h in 높이들]
    # 줄끼리 바짝 붙여 한 덩어리로 보이게 하고, 그 덩어리를 세로 가운데에 둡니다.
    덩어리높이 = sum(칸높이들) + 줄틈 * max(0, len(줄들) - 1)
    자리들 = []
    y = max(위여백, (세로 - 덩어리높이) // 2)
    틈 = 줄틈
    for 글, 글꼴, 칸높이, 글자높이 in zip(줄들, 글꼴들, 칸높이들, 높이들):
        민글 = 글.replace('"', "")
        자간 = 자간계산(민글, 글꼴, 글상자폭)
        폭 = 줄폭(민글, 글꼴, 자간)
        띠그리기.rounded_rectangle(
            [왼쪽여백 - 띠여백, y, 왼쪽여백 + 폭 + 띠여백, y + 칸높이],
            radius=10, fill=(0, 0, 0, 띠투명도))
        자리들.append((글, 글꼴, 자간, y + 띠여백 + 글자높이))
        y += 칸높이 + 틈

    그림 = Image.alpha_composite(그림.convert("RGBA"), 띠판).convert("RGB")
    그리기 = ImageDraw.Draw(그림)

    # 2) 그 위에 글자를 얹습니다
    for 번호, (글, 글꼴, 자간, 밑선) in enumerate(자리들):
        한줄그리기(그리기, 왼쪽여백, 밑선, 글, 글꼴,
                줄색[번호 % len(줄색)], 강조색[번호 % len(강조색)],
                자간, 외곽=max(6, int(글꼴.size * 0.11)))

    os.makedirs(os.path.dirname(출력경로) or ".", exist_ok=True)
    그림.save(출력경로, "PNG")
    print("saved:", 출력경로, "기준 글자크기", 기준)
    return 출력경로


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("배경")
    p.add_argument("출력", nargs="?", default="")
    p.add_argument("--줄", action="append", default=[])
    p.add_argument("--글꼴", default="안성탕면", choices=list(글꼴표))
    p.add_argument("--목록", default="")
    a = p.parse_args()

    if a.목록:
        for 항 in json.load(io.open(a.목록, encoding="utf-8")):
            만들기(a.배경, 항["출력"], 항["줄"], a.글꼴)
    else:
        만들기(a.배경, a.출력, a.줄, a.글꼴)
