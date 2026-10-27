# -*- coding: utf-8 -*-
r"""
캡컷을 열지 않고 썸네일을 그립니다.

캡컷 프로젝트(「황주썸넬」·「불심명언썸넬」)는 **모양을 정하는 숫자를 전부
파일로 들고 있습니다** — 글꼴, 크기, 색, 테두리, 줄 자리, 자간, 배경 그림을
어떻게 맞출지까지. 그래서 캡컷이 하는 일은 사실 그 숫자대로 글자를 얹는
것뿐입니다.

이 도구는 그 숫자를 그대로 읽어 Pillow 로 같은 그림을 그립니다. 캡컷 창을
띄울 필요가 없으니 사장님 화면을 쓰지 않습니다.

**캡컷 프로젝트는 손대지 않습니다.** 사장님이 캡컷에서 글꼴이나 색을
바꾸시면 다음에 읽을 때 저절로 따라갑니다.

사용법
    python 썸네일그리기.py --줄 "오늘 꼭 틀어놓으세요" ^
        --줄 "우리 집안에" --줄 "복이" --줄 "찾아옵니다" ^
        --배경 "D:\골드TV\_오늘이미지\1004-썸네일.png" ^
        --저장 "D:\골드TV\_완성11\썸네일.jpg"

    불심명언은 --채널 불심명언 을 붙입니다.
    대괄호로 한 구절만 다른 색을 주는 것도 캡컷과 똑같이 됩니다.
"""
import argparse
import io
import json
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from 채널 import 설정읽기, 인자붙이기

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

캡컷루트 = Path(os.environ["LOCALAPPDATA"]) / "CapCut/User Data/Projects/com.lveditor.draft"

# 유튜브 썸네일 규격
가로, 세로 = 1920, 1080

# 캡컷이 뽑은 썸네일과 글자 너비를 재서 맞춘 값입니다.
#   글자보정 : 캡컷의 size 1 이 화면에서 몇 픽셀인지
#   상자보정 : 캡컷의 fixed_width 1 이 화면에서 몇 픽셀인지
# 둘은 캡컷 안에서 단위가 달라 따로 둡니다.
글자보정_기본 = 11.16
상자보정_기본 = 2.566

# 캡컷은 글자를 줄 상자 가운데에 두는데, Pillow 의 글꼴 높이와 조금 다릅니다.
# 캡컷 결과와 재서 맞춘 올림값입니다 (글자 크기에 견준 비율).
올림비율 = 0.076

# 테두리 두께도 캡컷 결과와 재서 맞췄습니다.
테두리보정 = 0.95

# 글자 뒤 띠(캡컷의 「배경」)도 캡컷 결과와 재서 맞춘 값입니다.
띠가로보정 = 2.36
띠세로보정 = 1.33
띠켜짐비트 = 16          # check_flag 의 이 자리가 서 있으면 띠를 그립니다


def 색(쌍):
    """캡컷의 0~1 짜리 색을 0~255 로 바꿉니다."""
    return tuple(int(round(max(0.0, min(1.0, v)) * 255)) for v in 쌍)


def 나누기(글):
    """`앞[강조]뒤` 를 (조각, 강조인가) 목록으로 가릅니다."""
    조각들, 남은 = [], 글
    while "[" in 남은 and "]" in 남은[남은.index("["):]:
        앞, 나머지 = 남은.split("[", 1)
        가운데, 남은 = 나머지.split("]", 1)
        if 앞:
            조각들.append((앞, False))
        if 가운데:
            조각들.append((가운데, True))
    if 남은:
        조각들.append((남은, False))
    return 조각들 or [(글, False)]


def 설계읽기(프로젝트):
    """캡컷 프로젝트에서 줄마다의 모양을 읽어 옵니다."""
    파일 = 캡컷루트 / 프로젝트 / "draft_content.json"
    if not 파일.exists():
        sys.exit("[실패] 캡컷 프로젝트를 찾을 수 없습니다: " + str(파일.parent))
    d = json.load(io.open(파일, encoding="utf-8"))

    칸 = d.get("canvas_config") or {}
    캔버스 = (칸.get("width") or 가로, 칸.get("height") or 세로)

    글자칸 = []
    for t in d["tracks"]:
        if t["type"] == "text":
            글자칸 += t["segments"]
    글자칸.sort(key=lambda s: -s["clip"]["transform"]["y"])   # 캡컷은 +y 가 위
    재료표 = {m["id"]: m for m in d["materials"]["texts"]}

    줄들 = []
    for s in 글자칸:
        m = 재료표[s["material_id"]]
        c = json.loads(m["content"])
        스타일 = c["styles"]
        바탕 = 스타일[0]
        바탕색 = (바탕.get("fill") or {}).get("content", {}).get("solid", {}).get("color")
        강조 = None
        for st in 스타일[1:]:
            여기색 = (st.get("fill") or {}).get("content", {}).get("solid", {}).get("color")
            if 여기색 and 여기색 != 바탕색:
                강조 = st
                break

        def 꾸밈(st):
            테 = (st.get("strokes") or [{}])[0]
            테색 = (테.get("content") or {}).get("solid", {}).get("color")
            return {
                "글꼴": (st.get("font") or {}).get("path") or m.get("font_path"),
                "크기": st.get("size") or m.get("font_size") or 14,
                "색": 색(((st.get("fill") or {}).get("content", {})
                        .get("solid", {}).get("color")) or [1, 1, 1]),
                "테두리색": 색(테색) if 테색 else None,
                "테두리두께": 테.get("width") or 0,
            }

        깃발 = m.get("check_flag") or 0
        줄들.append({
            "띠": {
                "켜짐": bool(깃발 & 띠켜짐비트),
                "색": m.get("background_color") or "#000000",
                "진하기": m.get("background_alpha", 1.0),
                "가로": m.get("background_width", 0.14),
                "세로": m.get("background_height", 0.14),
                "둥글기": m.get("background_round_radius", 0.0),
            },
            "기울임": m.get("italic_degree", 0) or 0,
            "글": c.get("text", ""),
            "y": s["clip"]["transform"]["y"],
            "x": s["clip"]["transform"]["x"],
            "배율": s["clip"]["scale"]["x"],
            "정렬": m.get("alignment", 0),
            "자간": m.get("letter_spacing") or 0.0,
            "상자너비": m.get("fixed_width") or 0,
            "바탕": 꾸밈(바탕),
            "강조": 꾸밈(강조) if 강조 else None,
        })

    배경맞춤 = None
    for t in d["tracks"]:
        if t["type"] == "video" and t["segments"]:
            cl = t["segments"][0]["clip"]
            배경맞춤 = {"배율": cl["scale"]["x"],
                     "x": cl["transform"]["x"], "y": cl["transform"]["y"]}
            break

    return {"캔버스": 캔버스, "줄들": 줄들, "배경맞춤": 배경맞춤}


def 배경깔기(그림경로, 맞춤, 캔버스):
    """캡컷이 하던 대로 배경 그림을 깔고 배율·위치를 적용합니다.

    캡컷은 그림을 **캔버스 안에 맞춰 넣은 뒤**(가로·세로 중 작은 비율)
    클립의 scale 을 곱합니다. 채우기(cover)가 아니라 맞춰넣기(contain)
    입니다 — 캡컷이 뽑은 썸네일과 재서 확인했습니다.
    """
    칸가로, 칸세로 = 캔버스
    바탕 = Image.new("RGB", (칸가로, 칸세로), (0, 0, 0))
    원본 = Image.open(그림경로).convert("RGB")

    기본 = min(칸가로 / 원본.width, 칸세로 / 원본.height)
    배율 = 기본 * (맞춤["배율"] if 맞춤 else 1.0)
    새크기 = (max(1, int(round(원본.width * 배율))),
            max(1, int(round(원본.height * 배율))))
    큰그림 = 원본.resize(새크기, Image.LANCZOS)

    # transform 은 캔버스 절반을 1 로 센 값입니다. +y 가 위쪽입니다.
    밀기x = (맞춤["x"] if 맞춤 else 0.0) * (칸가로 / 2)
    밀기y = -(맞춤["y"] if 맞춤 else 0.0) * (칸세로 / 2)
    왼쪽 = int(round((칸가로 - 새크기[0]) / 2 + 밀기x))
    위쪽 = int(round((칸세로 - 새크기[1]) / 2 + 밀기y))
    바탕.paste(큰그림, (왼쪽, 위쪽))
    return 바탕


def 글꼴불러오기(경로, 픽셀):
    try:
        return ImageFont.truetype(경로, 픽셀)
    except Exception:
        return ImageFont.truetype("malgunbd.ttf", 픽셀)


def 글자너비(글꼴, 글, 자간픽셀):
    if not 글:
        return 0
    너비 = sum(글꼴.getlength(ㄱ) for ㄱ in 글)
    return 너비 + 자간픽셀 * (len(글) - 1)


def 한줄그리기(판, 줄, 글, 글자보정, 상자보정, 캔버스):
    조각들 = 나누기(글)
    if 줄["강조"] is None:
        조각들 = [("".join(ㄱ for ㄱ, _ in 조각들), False)]

    바탕 = 줄["바탕"]
    픽셀 = int(round(바탕["크기"] * 줄["배율"] * 글자보정))
    글꼴 = 글꼴불러오기(바탕["글꼴"], 픽셀)
    자간픽셀 = 줄["자간"] * 픽셀

    전체너비 = sum(글자너비(글꼴, ㄱ, 자간픽셀) + 자간픽셀 for ㄱ, _ in 조각들) - 자간픽셀
    상자너비 = 줄["상자너비"] * 줄["배율"] * 상자보정 if 줄["상자너비"] else 전체너비

    칸가로, 칸세로 = 캔버스
    가운데x = 칸가로 / 2 + 줄["x"] * (칸가로 / 2)
    if 줄["정렬"] == 0:            # 왼쪽 맞춤
        시작x = 가운데x - 상자너비 / 2
    elif 줄["정렬"] == 2:          # 오른쪽 맞춤
        시작x = 가운데x + 상자너비 / 2 - 전체너비
    else:                          # 가운데 맞춤 (캡컷 alignment 1)
        시작x = 가운데x - 전체너비 / 2

    가운데y = 칸세로 / 2 - 줄["y"] * (칸세로 / 2)
    오름, 내림 = 글꼴.getmetrics()
    기준y = 가운데y - (오름 + 내림) / 2 - 픽셀 * 올림비율

    띠 = 줄.get("띠") or {}
    if 띠.get("켜짐"):
        여백가로 = 띠["가로"] * 픽셀 * 띠가로보정
        여백세로 = 띠["세로"] * 픽셀 * 띠세로보정
        높이 = (오름 + 내림) + 2 * 여백세로
        네모 = [시작x - 여백가로, 가운데y - 높이 / 2,
              시작x + 전체너비 + 여백가로, 가운데y + 높이 / 2]
        반지름 = max(0, int(round(띠["둥글기"] * 높이 / 2)))
        띠판 = Image.new("RGBA", 판.size, (0, 0, 0, 0))
        ImageDraw.Draw(띠판).rounded_rectangle(
            네모, radius=반지름,
            fill=띠["색"] + "%02x" % int(round(max(0.0, min(1.0, 띠["진하기"])) * 255)))
        판.paste(띠판, (0, 0), 띠판)

    글자판 = Image.new("RGBA", 판.size, (0, 0, 0, 0))
    그리개 = ImageDraw.Draw(글자판)
    x = 시작x
    for 조각, 강조인가 in 조각들:
        꾸 = 줄["강조"] if (강조인가 and 줄["강조"]) else 바탕
        테두께 = int(round(꾸["테두리두께"] * 픽셀 * 테두리보정))
        for ㄱ in 조각:
            if 꾸["테두리색"] and 테두께 > 0:
                그리개.text((x, 기준y), ㄱ, font=글꼴, fill=꾸["색"],
                          stroke_width=테두께, stroke_fill=꾸["테두리색"])
            else:
                그리개.text((x, 기준y), ㄱ, font=글꼴, fill=꾸["색"])
            x += 글꼴.getlength(ㄱ) + 자간픽셀

    기울 = (줄.get("기울임") or 0) / 100.0
    if 기울:
        글자판 = 글자판.transform(
            글자판.size, Image.AFFINE,
            (1, 기울, -기울 * 가운데y, 0, 1, 0), resample=Image.BICUBIC)
    판.paste(글자판, (0, 0), 글자판)
    return 전체너비


def 그리기(프로젝트, 줄글들, 배경, 저장, 글자보정, 상자보정):
    설계 = 설계읽기(프로젝트)
    if len(줄글들) > len(설계["줄들"]):
        sys.exit("[실패] 이 프로젝트의 글자 줄은 %d개인데 %d줄을 주셨습니다."
                 % (len(설계["줄들"]), len(줄글들)))

    캔버스 = 설계["캔버스"]
    판 = 배경깔기(배경, 설계["배경맞춤"], 캔버스)
    for 번호, 글 in enumerate(줄글들):
        줄 = 설계["줄들"][번호]
        한줄그리기(판, 줄, 글, 글자보정, 상자보정, 캔버스)
        print("  %d줄  %s" % (번호 + 1, 글))

    # 캡컷 캔버스(1920x1077)에서 그린 뒤 유튜브 규격으로 폅니다.
    if 판.size != (가로, 세로):
        판 = 판.resize((가로, 세로), Image.LANCZOS)

    Path(저장).parent.mkdir(parents=True, exist_ok=True)
    판.save(저장, "JPEG", quality=92, subsampling=0)
    print()
    print("[완료] %s  (%dx%d)" % (저장, 가로, 세로))


if __name__ == "__main__":
    파서 = argparse.ArgumentParser(description="캡컷 없이 썸네일을 그립니다")
    파서.add_argument("--줄", action="append", default=[],
                     help="화면 위에서 아래 순서로. 대괄호 안은 강조색")
    파서.add_argument("--배경", required=True, help="배경으로 깔 그림 파일")
    파서.add_argument("--저장", required=True, help="나갈 jpg 경로")
    파서.add_argument("--프로젝트", default="", help="캡컷 프로젝트 이름")
    파서.add_argument("--글자보정", type=float, default=글자보정_기본,
                     help="글자 크기를 캡컷 결과에 맞추는 수")
    파서.add_argument("--상자보정", type=float, default=상자보정_기본,
                     help="글상자 너비를 캡컷 결과에 맞추는 수")
    인자붙이기(파서)
    인자 = 파서.parse_args()

    설정 = 설정읽기(인자.채널)
    프로젝트 = 인자.프로젝트 or 설정["캡컷"]["본썸네일"]
    print()
    print("썸네일 그리기 [%s] <- 「%s」" % (설정["표시이름"], 프로젝트))
    그리기(프로젝트, 인자.줄, 인자.배경, 인자.저장, 인자.글자보정, 인자.상자보정)
