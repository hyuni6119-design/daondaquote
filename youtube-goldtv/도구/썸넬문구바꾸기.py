# -*- coding: utf-8 -*-
r"""
캡컷 썸넬 프로젝트의 문구와 배경 그림만 갈아끼웁니다.

사장님이 캡컷에서 잡아 놓으신 **글꼴·크기·색·자리·테두리·배경 띠는 손대지
않습니다.** 글자 내용과 배경 사진만 바꿉니다. 그래야 썸네일이 장마다 똑같이
나옵니다. 글자를 GPT 로 굽지 않는 이유도 같습니다 — 그림은 GPT,
글자는 캡컷입니다.

사용법
    python 썸넬문구바꾸기.py --채널 불심명언 ^
        --줄 "오늘 꼭 틀어놓으세요" ^
        --줄 "우리 집안에" ^
        --줄 "복이 찾아옵니다" ^
        --줄 "틀어만 놓아도 [집안에 복]이 찾아옵니다" ^
        --배경 "D:\불심명언\_오늘이미지\0924-썸네일배경.png"

    --줄 은 **화면 위에서 아래 순서**로 줍니다. 적게 주면 나머지 줄은
    그대로 둡니다.

대괄호로 한 구절만 다른 색
    `틀어만 놓아도 [집안에 복]이 찾아옵니다` 처럼 쓰면 대괄호 안이
    강조색이 됩니다. 강조색은 제가 정하지 않고, **그 줄에 이미 들어 있는
    두 번째 색을 그대로 씁니다.** 사장님이 캡컷에서 초록을 노랑으로
    바꾸시면 다음부터 노랑으로 나옵니다.

    강조색이 없는 줄에 대괄호를 쓰면 그냥 무시하고 한 색으로 씁니다.

끝난 뒤
    캡컷에서 프로젝트를 열고 Ctrl+S 로 스틸 프레임을 내보냅니다.
    (해상도 1080P, 형식 JPEG)
"""

import argparse
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from 채널 import 설정읽기, 인자붙이기

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

캡컷루트 = Path(os.environ["LOCALAPPDATA"]) / "CapCut/User Data/Projects/com.lveditor.draft"


def 읽기(경로):
    return json.load(io.open(경로, encoding="utf-8"))


def 쓰기(경로, 자료):
    with io.open(경로, "w", encoding="utf-8") as f:
        json.dump(자료, f, ensure_ascii=False)


def 캡컷켜져있나():
    결과 = subprocess.run(["tasklist", "/FI", "IMAGENAME eq CapCut.exe"],
                        capture_output=True, text=True, errors="replace")
    return "CapCut.exe" in 결과.stdout


def 색뽑기(스타일):
    c = (스타일.get("fill") or {}).get("content", {}).get("solid", {}).get("color")
    return tuple(round(v, 6) for v in c) if c else None


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


def 줄바꾸기(재료, 새글):
    """한 줄의 글자만 바꿉니다. 꾸밈은 있던 것을 그대로 물려받습니다.

    캡컷의 한 줄은 스타일 여러 개로 쪼개질 수 있고, 스타일마다 `range` 가
    글자 구간을 가리킵니다. 예전에 모든 스타일에 전체 범위를 씌웠다가
    마지막 스타일(흰색)이 앞의 색을 덮어써서 썸네일 둘째 줄이 흰색으로
    변한 적이 있습니다. 그래서 여기서는 **구간을 새로 계산해서** 넣습니다.
    """
    c = json.loads(재료["content"])
    있던스타일 = c["styles"]
    바탕 = 있던스타일[0]
    바탕색 = 색뽑기(바탕)
    강조 = next((s for s in 있던스타일[1:] if 색뽑기(s) != 바탕색), None)

    조각들 = 나누기(새글)
    if 강조 is None:
        # 강조색이 없는 줄입니다. 대괄호는 글자로 치지 않고 떼어냅니다.
        조각들 = [("".join(글 for 글, _ in 조각들), False)]

    새글자 = "".join(글 for 글, _ in 조각들)
    새스타일들, 자리 = [], 0
    for 글, 강조인가 in 조각들:
        본 = json.loads(json.dumps(강조 if (강조인가 and 강조) else 바탕))
        본["range"] = [자리, 자리 + len(글)]
        새스타일들.append(본)
        자리 += len(글)

    c["styles"] = 새스타일들
    c["text"] = 새글자
    재료["content"] = json.dumps(c, ensure_ascii=False)
    return 새글자, sum(1 for _, 강 in 조각들 if 강)


def 바꾸기(프로젝트, 줄들, 배경):
    폴더 = 캡컷루트 / 프로젝트
    파일 = 폴더 / "draft_content.json"
    if not 파일.exists():
        sys.exit("[실패] 캡컷 프로젝트를 찾을 수 없습니다: " + str(폴더))
    if 배경 and not Path(배경).exists():
        sys.exit("[실패] 배경 그림이 없습니다: " + 배경)
    if 캡컷켜져있나():
        print("[멈춤] 캡컷이 켜져 있습니다. 먼저 캡컷을 닫아 주세요.")
        print("       열어 둔 채로 고치면 캡컷이 껐다 켤 때 옛 내용으로")
        print("       덮어씁니다.")
        sys.exit(1)

    d = 읽기(파일)
    글자칸들 = []
    for t in d["tracks"]:
        if t["type"] == "text":
            글자칸들 += t["segments"]
    # 화면 위에서 아래로 세웁니다 (캡컷은 +y 가 위쪽입니다).
    글자칸들.sort(key=lambda s: -s["clip"]["transform"]["y"])
    재료표 = {m["id"]: m for m in d["materials"]["texts"]}

    if len(줄들) > len(글자칸들):
        sys.exit("[실패] 이 프로젝트의 글자 줄은 %d개인데 %d줄을 주셨습니다."
                 % (len(글자칸들), len(줄들)))

    for 번호, 글 in enumerate(줄들):
        재료 = 재료표[글자칸들[번호]["material_id"]]
        썼다, 강조수 = 줄바꾸기(재료, 글)
        print("  %d줄  %s%s" % (번호 + 1, 썼다,
                              "   (강조 %d군데)" % 강조수 if 강조수 else ""))

    if 배경:
        사진 = d["materials"]["videos"][0]
        사진["path"] = str(Path(배경).resolve()).replace("\\", "/")
        사진["material_name"] = Path(배경).name
        print("  배경  " + Path(배경).name)

    쓰기(파일, d)
    쓰기(폴더 / "draft_content.json.bak", d)
    if (폴더 / "template-2.tmp").exists():
        쓰기(폴더 / "template-2.tmp", d)
    # 캡컷 9.x 는 Timelines 폴더의 사본을 먼저 봅니다. 남겨 두면 우리가 쓴
    # 내용이 무시됩니다.
    shutil.rmtree(폴더 / "Timelines", ignore_errors=True)

    print()
    print("[완료] 캡컷에서 「%s」 를 열고 Ctrl+S 로 내보내세요." % 프로젝트)


if __name__ == "__main__":
    파서 = argparse.ArgumentParser(
        description="캡컷 썸넬 프로젝트의 문구와 배경만 갈아끼웁니다")
    파서.add_argument("--줄", action="append", default=[],
                     help="화면 위에서 아래 순서로. 대괄호 안은 강조색")
    파서.add_argument("--배경", default="", help="배경으로 깔 그림 파일")
    파서.add_argument("--프로젝트", default="",
                     help="캡컷 프로젝트 이름 (없으면 채널 설정의 본썸네일)")
    인자붙이기(파서)
    인자 = 파서.parse_args()

    설정 = 설정읽기(인자.채널)
    프로젝트 = 인자.프로젝트 or 설정["캡컷"]["본썸네일"]
    if not 인자.줄 and not 인자.배경:
        sys.exit("[실패] --줄 이나 --배경 중 하나는 주셔야 합니다.")

    print()
    print("썸넬 문구 바꾸기 [%s] -> 「%s」" % (설정["표시이름"], 프로젝트))
    바꾸기(프로젝트, 인자.줄, 인자.배경)
