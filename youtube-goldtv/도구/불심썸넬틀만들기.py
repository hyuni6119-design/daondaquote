# -*- coding: utf-8 -*-
r"""
캡컷 「불심명언썸넬」 프로젝트 만들기 (한 번만 돌립니다)

사장님이 보내주신 참고 채널의 고정틀을 그대로 옮깁니다. 이 프로젝트가
만들어지면 날마다 문구만 갈아끼우고 Ctrl+S 로 내보냅니다.

    1줄  오늘 꼭 틀어놓으세요            작게 · 흰 글씨 · 빨간 라운드 박스 · 왼쪽
    2줄  우리 집안에                   아주 크게 · 흰 글씨 · 두꺼운 검정 테두리 · 왼쪽
    3줄  복이 옵니다                   아주 크게 · 노란 글씨 · 두꺼운 검정 테두리 · 왼쪽
    4줄  틀어만 놓아도 집안에 복이 찾아옵니다  작게 · 흰 글씨 · 가로 반투명 검정 띠 · 가운데

「황주썸넬」을 본으로 복사합니다. 칸 배치(사진 한 장 + 글자 트랙 4개)가
같고, 그 프로젝트의 값들은 이미 렌더해서 검증된 것들이기 때문입니다.

글자를 GPT 로 굽지 않는 이유는 `images-via-gpt-api` 메모에 적어 두었습니다.
글꼴과 크기가 장마다 똑같아야 채널이 한 덩어리로 보입니다.
"""

import argparse
import io
import json
import os
import shutil
import sys
import time
import uuid
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

캡컷루트 = Path(os.environ["LOCALAPPDATA"]) / "CapCut/User Data/Projects/com.lveditor.draft"
본 = 캡컷루트 / "황주썸넬"
새이름 = "불심명언썸넬"
새폴더 = 캡컷루트 / 새이름

배경 = r"D:/불심명언/_오늘이미지/0923-썸네일배경.png"

빨강 = "#e11414"
노랑 = "#ffd400"
흰색 = "#ffffff"

# (글, 글자크기, 색, 정렬, 테두리두께, 배경띠)
#   정렬 0=왼쪽 1=가운데
#   배경띠 None 이거나 (색, 투명도, 둥글기, 좌우여백, 위아래여백)
줄들 = [
    ("오늘 꼭 틀어놓으세요", 7.0, 흰색, 0, 0.0, (빨강, 1.00, 0.50, 0.34, 0.36)),
    ("우리 집안에", 19.5, 흰색, 0, 0.145, None),
    ("복이 옵니다", 19.5, 노랑, 0, 0.145, None),
    ("틀어만 놓아도 집안에 복이 찾아옵니다", 6.5, 흰색, 1, 0.0, ("#000000", 0.55, 0.0, 6.00, 0.50)),
]

# 화면 위아래 자리 (캡컷 값: +1 이 위쪽 끝). 참고 이미지의 비율에 맞췄습니다.
자리 = [0.760, 0.270, -0.130, -0.735]

# 큰 글씨 두 줄의 글상자 폭입니다. 본(황주썸넬)의 616 을 그대로 씁니다.
# 이 값을 -1(자동)로 풀면 글상자가 글자에 딱 붙어 왼쪽 정렬이 가운데
# 정렬처럼 보이고, 글자가 오른쪽 부처님까지 침범합니다.
큰글상자 = 616.128504663636
작은글상자 = 520.0
아랫줄글상자 = 900.0


def 새아이디():
    return str(uuid.uuid4()).upper()


def 읽기(경로):
    return json.load(io.open(경로, encoding="utf-8"))


def 쓰기(경로, 자료):
    with io.open(경로, "w", encoding="utf-8") as f:
        json.dump(자료, f, ensure_ascii=False)


def _rgb(색):
    return [int(색[1:3], 16) / 255, int(색[3:5], 16) / 255, int(색[5:7], 16) / 255]


def 글바꾸기(재료, 새글, 색, 크기, 테두리):
    """글자 내용·색·크기·테두리를 바꿉니다.

    캡컷이 실제로 보는 값은 재료 바깥의 `font_size` 가 아니라
    `content` 안 `styles[0]["size"]` 입니다. 바깥만 고치면 화면은 그대로라
    처음에 크기가 안 먹는 줄 알았습니다. 테두리도 마찬가지로
    `styles[0]["strokes"]` 쪽이 진짜입니다.

    한 줄에 스타일이 여러 개 겹쳐 있으면 첫 번째만 남깁니다. 전부에 전체
    범위를 씌우면 마지막 스타일이 앞의 색을 덮어버립니다. 예전에 썸네일
    둘째 줄이 흰색으로 변한 것이 이 때문이었습니다.
    """
    c = json.loads(재료["content"])
    스타일 = c["styles"][0]
    스타일["range"] = [0, len(새글)]
    스타일["size"] = 크기
    스타일.setdefault("fill", {}).setdefault("content", {})["solid"] = {"color": _rgb(색)}
    스타일["fill"]["content"]["render_type"] = "solid"

    if 테두리:
        스타일["strokes"] = [{
            "content": {"render_type": "solid", "solid": {"color": [0, 0, 0]}},
            "width": 테두리, "mode": 0}]
    else:
        스타일.pop("strokes", None)

    c["styles"] = [스타일]
    c["text"] = 새글
    재료["content"] = json.dumps(c, ensure_ascii=False)
    재료["text_color"] = 색
    재료["font_size"] = 크기


def 만들기(덮어쓰기=False):
    if not (본 / "draft_content.json").exists():
        sys.exit("[실패] 본 프로젝트가 없습니다: " + str(본))
    if not Path(배경).exists():
        sys.exit("[실패] 배경 그림이 없습니다: " + 배경)
    if 새폴더.exists():
        if not 덮어쓰기:
            print("[멈춤] 「%s」 프로젝트가 이미 있습니다." % 새이름)
            print("       사장님이 캡컷에서 손봐 두신 것일 수 있어, 그냥 지우지")
            print("       않습니다. 정말로 처음 틀부터 다시 만들려면")
            print("       --다시 를 붙여 주세요.")
            print("       %s" % 새폴더)
            sys.exit(1)
        shutil.rmtree(새폴더)
        print("이미 있던 %s 를 지우고 다시 만듭니다." % 새이름)

    print("본 프로젝트 복사: 황주썸넬 -> %s" % 새이름)
    shutil.copytree(본, 새폴더)
    # 캡컷 9.x 는 Timelines 폴더의 사본을 먼저 봅니다. 남아 있으면 우리가
    # 쓴 내용이 무시됩니다.
    shutil.rmtree(새폴더 / "Timelines", ignore_errors=True)

    d = 읽기(본 / "draft_content.json")
    d["id"] = 새아이디()
    d["name"] = ""
    d["path"] = str(새폴더).replace("\\", "/") + "/draft_content.json"

    글자트랙들 = [t for t in d["tracks"] if t["type"] == "text"]
    # 본은 아래에서 위로 쌓여 있습니다. 위에서부터 보려고 자리순으로 세웁니다.
    글자트랙들.sort(key=lambda t: -t["segments"][0]["clip"]["transform"]["y"])
    재료표 = {m["id"]: m for m in d["materials"]["texts"]}
    폭들 = [작은글상자, 큰글상자, 큰글상자, 아랫줄글상자]

    for 번호, 트랙 in enumerate(글자트랙들):
        칸 = 트랙["segments"][0]
        재료 = 재료표[칸["material_id"]]
        글, 크기, 색, 정렬, 테두리, 띠 = 줄들[번호]

        글바꾸기(재료, 글, 색, 크기, 테두리)
        재료["alignment"] = 정렬
        재료["fixed_width"] = 폭들[번호]
        재료["force_apply_line_max_width"] = False

        재료["border_color"] = "#000000"
        재료["border_alpha"] = 1.0
        재료["border_width"] = 테두리
        재료["border_mode"] = 0 if 테두리 else 1     # 1 = 테두리 끔

        # 배경 띠는 `background_style` 만으로는 켜지지 않습니다. 재료의
        # `check_flag` 에 16 비트가 서 있어야 캡컷이 그립니다. 저장소 안
        # 프로젝트 4천여 개를 훑어보니 예외가 하나도 없었습니다.
        if 띠:
            띠색, 투명, 둥글기, 좌우, 위아래 = 띠
            재료["check_flag"] = 재료.get("check_flag", 47) | 16
            재료["background_style"] = 1
            재료["background_color"] = 띠색
            재료["background_alpha"] = 투명
            재료["background_round_radius"] = 둥글기
            재료["background_width"] = 좌우
            재료["background_height"] = 위아래
            재료["background_horizontal_offset"] = 0.0
            재료["background_vertical_offset"] = 0.0
        else:
            재료["check_flag"] = 재료.get("check_flag", 47) & ~16
            재료["background_style"] = 0

        칸["clip"]["transform"]["x"] = 0.0
        칸["clip"]["transform"]["y"] = 자리[번호]
        print("  %d줄  %-20s 크기 %4.1f  %s  %s  %s"
              % (번호 + 1, 글[:20], 크기, 색,
                 "가운데" if 정렬 else "왼쪽 ",
                 "띠 " + 띠[0] if 띠 else "테두리"))

    # ---- 배경 사진 ----
    사진재료 = d["materials"]["videos"][0]
    사진재료["path"] = str(Path(배경)).replace("\\", "/")
    사진재료["material_name"] = Path(배경).name

    쓰기(새폴더 / "draft_content.json", d)
    쓰기(새폴더 / "draft_content.json.bak", d)
    if (새폴더 / "template-2.tmp").exists():
        쓰기(새폴더 / "template-2.tmp", d)

    메타 = 읽기(새폴더 / "draft_meta_info.json")
    지금 = int(time.time() * 1000000)
    메타["draft_id"] = 새아이디()
    메타["draft_name"] = 새이름
    메타["draft_fold_path"] = str(새폴더).replace("\\", "/")
    메타["tm_draft_create"] = 지금
    메타["tm_draft_modified"] = 지금
    쓰기(새폴더 / "draft_meta_info.json", 메타)

    print()
    print("[완료] %s" % 새폴더)


if __name__ == "__main__":
    파서 = argparse.ArgumentParser(
        description="캡컷 「불심명언썸넬」 틀을 처음 한 번 만듭니다")
    파서.add_argument("--다시", action="store_true",
                     help="이미 있는 프로젝트를 지우고 처음 틀부터 다시 만듭니다 "
                          "(캡컷에서 손본 것이 있으면 사라집니다)")
    인자 = 파서.parse_args()
    만들기(인자.다시)
