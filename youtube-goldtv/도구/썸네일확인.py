# -*- coding: utf-8 -*-
"""올린 영상에 내 썸네일이 실제로 걸렸는지 봅니다.

유튜브가 돌려주는 미리보기 이미지를 받아서, 그 영상의 _완성N 폴더에
있는 썸네일.jpg 와 견줍니다. 닮지 않았으면 안 올라간 것입니다.

    python 썸네일확인.py             # 황금주파수
    python 썸네일확인.py --채널 불심명언
"""
import sys, os, re, io, glob, json, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image

이름 = "황금주파수"
if "--채널" in sys.argv:
    이름 = sys.argv[sys.argv.index("--채널") + 1]
뿌리 = r"D:\불심명언" if 이름 == "불심명언" else r"D:\골드TV"

def 지문(그림):
    """32x32 흑백으로 줄여 평균보다 밝은 칸을 1로 — 비슷한 그림은 지문도 비슷합니다."""
    작 = 그림.convert("L").resize((32, 32), Image.LANCZOS)
    값 = list(작.getdata())
    평 = sum(값) / float(len(값))
    return [1 if ㅂ > 평 else 0 for ㅂ in 값]

def 닮은정도(ㄱ, ㄴ):
    같 = sum(1 for a, b in zip(ㄱ, ㄴ) if a == b)
    return 같 * 100.0 / len(ㄱ)

# _완성N 폴더에서 영상번호를 긁어 옵니다
짝 = {}
for 폴 in glob.glob(os.path.join(뿌리, "_완성*")):
    번호 = None
    for 이 in ("캡컷판완료.txt", "업로드결과.txt"):
        길 = os.path.join(폴, 이)
        if os.path.exists(길):
            ㅈ = re.search(r"([A-Za-z0-9_-]{11})", io.open(길, encoding="utf-8").read())
            if ㅈ:
                번호 = ㅈ.group(1)
                break
    썸 = os.path.join(폴, "썸네일.jpg")
    if 번호 and os.path.exists(썸):
        짝[번호] = (os.path.basename(폴), 썸)

print("== %s ==  견줄 수 있는 편: %d\n" % (이름, len(짝)))
탈 = []
for 번호, (폴이름, 썸) in sorted(짝.items(), key=lambda x: x[1][0]):
    내것 = 지문(Image.open(썸))
    최고, 어디 = 0, ""
    for 종류 in ("maxresdefault", "hqdefault"):
        try:
            주소 = "https://i.ytimg.com/vi/%s/%s.jpg" % (번호, 종류)
            자료 = urllib.request.urlopen(주소, timeout=20).read()
            점 = 닮은정도(내것, 지문(Image.open(io.BytesIO(자료))))
            if 점 > 최고:
                최고, 어디 = 점, 종류
        except Exception:
            continue
    판 = "걸렸음" if 최고 >= 85 else ("애매함" if 최고 >= 72 else "안 걸렸음")
    print("%-8s %-12s %s  (닮은정도 %.0f%%, %s)" % (폴이름, 번호, 판, 최고, 어디 or "못 받음"))
    if 최고 < 85:
        탈.append((폴이름, 번호, 최고))
print("\n걸린 것: %d / 못 걸린 것: %d" % (len(짝) - len(탈), len(탈)))
for ㅍ, ㅂ, ㅈ in 탈:
    print("  ↳ %s %s (%.0f%%)" % (ㅍ, ㅂ, ㅈ))
