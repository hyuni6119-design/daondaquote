# -*- coding: utf-8 -*-
r"""
모음집 캡컷 프로젝트 만들기 (채널 공용)

그 채널의 본 영상 프로젝트를 복사해, 그날 만든 곡들을 한 줄로 이어붙인
긴 모음집 프로젝트를 새로 만듭니다. 캡컷 화면을 클릭하지 않고
draft_content.json 을 직접 써서 만듭니다.

    황금주파수 → 「황주영상-복사」
    불심명언   → 「불심명언 노래-복사」

어느 프로젝트를 본으로 삼을지는 `도구/채널/<이름>.json` 에 적혀 있습니다.

들어가는 것
    배경    : 그날 재생화면 그림 한 장 (전체 길이에 깔립니다)
    소리    : 곡 mp3 들을 순서대로 이어붙임
    고정문구: 본 프로젝트의 안내 문구·채널명·인트로 그대로
    곡 제목 : 곡이 바뀔 때마다 아래쪽 제목이 바뀝니다
    가사자막: 넣지 않습니다

사용법
    python 캡컷모음집만들기.py --이름 0922골드 --배경 "D:\골드TV\_오늘이미지\0918-영상용.png" --곡폴더 "D:\골드TV"
"""

import argparse
import copy
import json
import io
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

from 채널 import 설정읽기, 인자붙이기

캡컷루트 = Path(os.environ["LOCALAPPDATA"]) / "CapCut/User Data/Projects/com.lveditor.draft"
# 아래 두 값은 기본(황금주파수)이고, `--채널` 을 주면 그 채널 설정으로
# 갈아 끼웁니다. 코드를 두 벌로 복사하지 않으려고 이렇게 둡니다.
본프로젝트 = "황주영상-복사"      # 구성(트랙과 문구)을 가져올 곳
사진본프로젝트 = "황주썸넬"        # 사진 한 장을 까는 방법을 가져올 곳
소리확장자 = {".mp3", ".wav", ".m4a", ".aac", ".flac"}
제목가로위치 = 0.55              # 곡 제목 가로 위치 (1.0 이 화면 오른쪽 끝)
곡제목크기 = 11                  # 새로 만드는 곡 제목 글자 크기
곡제목세로위치 = -0.62           # 화면 아래쪽 (−1.0 이 맨 아래)
채널명후보 = {"불심명언", "황금주파수 TV", "황금주파수"}
곡제목표시 = True                # `--채널` 설정이 덮어씁니다


def 새아이디():
    return str(uuid.uuid4()).upper()


def 읽기(경로):
    return json.load(io.open(경로, encoding="utf-8"))


def 쓰기(경로, 자료):
    with io.open(경로, "w", encoding="utf-8") as f:
        json.dump(자료, f, ensure_ascii=False)


def 길이재기(파일):
    결과 = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(파일)],
        capture_output=True, text=True)
    return int(round(float(결과.stdout.strip()) * 1000000))


def 재료찾기(원본, 아이디):
    """materials 안 어느 목록에 들어 있는 재료인지 찾아 돌려줍니다."""
    for 이름, 목록 in 원본["materials"].items():
        if isinstance(목록, list):
            for 항목 in 목록:
                if isinstance(항목, dict) and 항목.get("id") == 아이디:
                    return 이름, 항목
    return None, None


def 재료복제(원본, 대상, 아이디):
    """재료 하나를 새 아이디로 복제해 대상에 넣고 새 아이디를 돌려줍니다."""
    이름, 항목 = 재료찾기(원본, 아이디)
    if 항목 is None:
        return None
    사본 = copy.deepcopy(항목)
    사본["id"] = 새아이디()
    대상["materials"].setdefault(이름, []).append(사본)
    return 사본["id"]


def 곡모으기(뿌리):
    폴더들 = sorted(p for p in Path(뿌리).iterdir()
                  if p.is_dir() and not p.name.startswith("_"))
    묶음들 = []
    for 폴더 in 폴더들:
        묶음 = [p for p in 폴더.iterdir()
              if p.is_file() and p.suffix.lower() in 소리확장자]
        # 제목.mp3 가 먼저, 그다음 제목 (1).mp3 순서로 둡니다.
        묶음.sort(key=lambda p: (len(p.stem), p.stem))
        if 묶음:
            묶음들.append(묶음)
    return 곡섞기(묶음들)


def 곡섞기(묶음들):
    """같은 가사에서 나온 곡이 몰리지 않도록 순서를 짭니다.

    수노는 가사 하나로 여러 곡을 뽑아 주기 때문에, 폴더 순서대로 붙이면
    제목이 같은 곡이 여러 개 연달아 나옵니다. 배경에 깔리는 노래라
    반복이 금방 티가 납니다.

    묶음마다 자기 곡들을 전체 길이에 고르게 흩어 놓습니다. 6곡짜리 묶음은
    1/12, 3/12, 5/12 ... 지점에, 2곡짜리 묶음은 1/4, 3/4 지점에 놓는 식입니다.
    그렇게 하면 큰 묶음 둘이 앞부분에서 번갈아 나오는 일도 없습니다.
    마지막에 그래도 이웃이 겹치면 뒤쪽 곡과 자리를 바꿔 풀어 줍니다.
    """
    자리 = []
    for 묶음번호, 묶음 in enumerate(묶음들):
        개수 = len(묶음)
        for 번호, 곡 in enumerate(묶음):
            # 같은 지점에 여러 묶음이 겹칠 때를 대비해 묶음마다 아주 작은
            # 차이를 줘서 늘 같은 순서로 붙지 않게 합니다.
            위치 = (번호 + 0.5) / 개수 + 묶음번호 * 1e-4
            자리.append((위치, 묶음번호, 곡))
    자리.sort(key=lambda x: (x[0], x[1]))

    차례 = [(묶음번호, 곡) for _, 묶음번호, 곡 in 자리]

    # 이웃이 겹치면 뒤쪽에서 바꿔 올 수 있는 곡을 찾아 자리를 바꿉니다.
    for i in range(1, len(차례)):
        if 차례[i][0] != 차례[i - 1][0]:
            continue
        for j in range(i + 1, len(차례)):
            if (차례[j][0] != 차례[i - 1][0]
                    and (i + 1 >= len(차례) or 차례[j][0] != 차례[i + 1][0])
                    and 차례[j - 1][0] != 차례[i][0]
                    and (j + 1 >= len(차례) or 차례[j + 1][0] != 차례[i][0])):
                차례[i], 차례[j] = 차례[j], 차례[i]
                break

    return [곡 for _, 곡 in 차례]


def 곡제목(파일):
    이름 = 파일.stem
    if 이름.endswith(")") and " (" in 이름:
        이름 = 이름[:이름.rindex(" (")]
    return 이름


def 글자내용바꾸기(재료, 새글):
    """텍스트 재료의 글만 바꾸고 서식은 그대로 둡니다."""
    내용 = json.loads(재료["content"])
    내용["text"] = 새글
    for 스타일 in 내용.get("styles", []):
        스타일["range"] = [0, len(새글)]
    재료["content"] = json.dumps(내용, ensure_ascii=False)


def 곡제목트랙만들기(d, 글자트랙들):
    """곡 제목을 띄울 글자 트랙을 새로 만들어 돌려줍니다.

    채널명 글자를 본으로 삼습니다. 이미 만들어 둔 글꼴·색·테두리를 그대로
    물려받으므로 화면이 튀지 않습니다. 자리는 화면 아래쪽 가운데로 잡고
    크기는 채널명보다 조금 키웁니다.

    `제목트랙["segments"][0]` 이 본보기 칸이 되어야 하므로 칸 하나를
    넣어 둡니다. 부르는 쪽에서 곡 수만큼 복제해 갈아 끼웁니다.
    """
    본트랙 = None
    for t in 글자트랙들:
        if len(t["segments"]) != 1:
            continue
        재료 = next((m for m in d["materials"]["texts"]
                  if m["id"] == t["segments"][0]["material_id"]), None)
        if 재료 and json.loads(재료["content"])["text"].strip() in 채널명후보:
            본트랙 = t
            break
    if 본트랙 is None:                       # 채널명을 못 찾으면 첫 트랙으로
        본트랙 = 글자트랙들[0]

    본칸 = copy.deepcopy(본트랙["segments"][0])
    본재료 = next(m for m in d["materials"]["texts"]
               if m["id"] == 본트랙["segments"][0]["material_id"])

    재료 = copy.deepcopy(본재료)
    재료["id"] = 새아이디()
    재료["fixed_width"] = -1.0
    재료["force_apply_line_max_width"] = False
    내용 = json.loads(재료["content"])
    for 스타일 in 내용.get("styles", []):
        스타일["size"] = 곡제목크기
    # 가운데 정렬로 둡니다. 채널명은 왼쪽 정렬이라 그대로 두면 제목이
    # 화면 가운데에서 시작해 오른쪽으로 삐져나가 잘립니다.
    내용["alignment"] = 1
    재료["content"] = json.dumps(내용, ensure_ascii=False)
    재료["alignment"] = 1
    d["materials"]["texts"].append(재료)

    본칸["id"] = 새아이디()
    본칸["material_id"] = 재료["id"]
    본칸["clip"]["transform"]["x"] = 0.0
    본칸["clip"]["transform"]["y"] = 곡제목세로위치
    본칸["clip"]["scale"] = {"x": 1.0, "y": 1.0}
    본칸["target_timerange"] = {"start": 0, "duration": 1000000}
    본칸["extra_material_refs"] = [
        x for x in (재료복제(d, d, r) for r in 본칸.get("extra_material_refs", []))
        if x]

    새트랙 = {
        "attribute": 0,
        "flag": 0,
        "id": 새아이디(),
        "is_default_name": True,
        "name": "",
        "segments": [본칸],
        "type": "text",
    }
    d["tracks"].append(새트랙)
    글자트랙들.append(새트랙)
    return 새트랙


def 만들기(이름, 배경, 곡폴더):
    본 = 캡컷루트 / 본프로젝트
    사진본 = 캡컷루트 / 사진본프로젝트
    새폴더 = 캡컷루트 / 이름

    for p in (본, 사진본):
        if not (p / "draft_content.json").exists():
            sys.exit("[실패] 본 프로젝트를 찾을 수 없습니다: " + str(p))
    if 새폴더.exists():
        sys.exit("[실패] 이미 있는 프로젝트입니다: " + str(새폴더))

    곡들 = 곡모으기(곡폴더)
    if not 곡들:
        sys.exit("[실패] 곡을 찾지 못했습니다: " + str(곡폴더))

    길이들 = [길이재기(곡) for 곡 in 곡들]
    총길이 = sum(길이들)
    print("곡 %d개, 전체 %.1f분" % (len(곡들), 총길이 / 1e6 / 60))

    print("본 프로젝트 복사: %s -> %s" % (본프로젝트, 이름))
    shutil.copytree(본, 새폴더)

    # 캡컷 9.x 는 Timelines 폴더에 타임라인 사본을 두고 열 때 그쪽을 먼저 봅니다.
    # 본에서 딸려온 사본이 남아 있으면 우리가 쓴 내용이 무시되므로 지웁니다.
    shutil.rmtree(새폴더 / "Timelines", ignore_errors=True)

    d = 읽기(본 / "draft_content.json")
    사진d = 읽기(사진본 / "draft_content.json")
    본길이 = d["duration"]

    d["id"] = 새아이디()
    d["name"] = ""
    d["path"] = str(새폴더).replace("\\", "/") + "/draft_content.json"
    d["duration"] = 총길이

    영상트랙 = next(t for t in d["tracks"] if t["type"] == "video")
    소리트랙 = next(t for t in d["tracks"] if t["type"] == "audio")
    글자트랙들 = [t for t in d["tracks"] if t["type"] == "text"]
    스티커트랙 = next((t for t in d["tracks"] if t["type"] == "sticker"), None)

    # ---- 배경 사진 한 장 ----
    사진재료본 = 사진d["materials"]["videos"][0]
    사진칸본 = next(t for t in 사진d["tracks"] if t["type"] == "video")["segments"][0]

    사진재료 = copy.deepcopy(사진재료본)
    사진재료["id"] = 새아이디()
    사진재료["local_material_id"] = str(uuid.uuid4())
    사진재료["path"] = str(Path(배경).resolve()).replace("\\", "/")
    사진재료["material_name"] = Path(배경).name
    d["materials"]["videos"] = [사진재료]
    d["materials"]["transitions"] = []      # 클립이 하나라 전환이 필요 없습니다

    사진칸 = copy.deepcopy(사진칸본)
    사진칸["id"] = 새아이디()
    사진칸["material_id"] = 사진재료["id"]
    사진칸["source_timerange"] = {"start": 0, "duration": 총길이}
    사진칸["target_timerange"] = {"start": 0, "duration": 총길이}
    # 3:2 그림을 16:9 화면에 넣습니다. 가로를 채우고, 넘치는 세로는 아래쪽만
    # 잘라 윗부분(부처님 머리)이 살아남게 합니다.
    캔버스가로 = d["canvas_config"]["width"]
    캔버스세로 = d["canvas_config"]["height"]
    맞춰넣기가로 = 캔버스세로 * 사진재료.get("width", 1536) / 사진재료.get("height", 1024)
    배율 = 캔버스가로 / 맞춰넣기가로
    넘침 = 캔버스세로 * 배율 - 캔버스세로
    사진칸["clip"]["scale"]["x"] = 사진칸["clip"]["scale"]["y"] = round(배율, 4)
    사진칸["clip"]["transform"]["x"] = 0.0
    사진칸["clip"]["transform"]["y"] = round(-(넘침 / 2) / (캔버스세로 / 2), 4)
    사진칸["extra_material_refs"] = [
        x for x in (재료복제(사진d, d, r) for r in 사진칸본["extra_material_refs"]) if x]
    영상트랙["segments"] = [사진칸]

    # ---- 곡 이어붙이기 ----
    소리재료본 = d["materials"]["audios"][0]
    소리칸본 = copy.deepcopy(소리트랙["segments"][0])

    d["materials"]["audios"] = []
    새소리칸들 = []
    시작 = 0
    for 곡, 길이 in zip(곡들, 길이들):
        재료 = copy.deepcopy(소리재료본)
        재료["id"] = 새아이디()
        재료["local_material_id"] = str(uuid.uuid4())
        재료["music_id"] = str(uuid.uuid4())
        재료["name"] = 곡.name
        재료["path"] = str(곡).replace("\\", "/")
        재료["duration"] = 길이
        d["materials"]["audios"].append(재료)

        칸 = copy.deepcopy(소리칸본)
        칸["id"] = 새아이디()
        칸["material_id"] = 재료["id"]
        칸["source_timerange"] = {"start": 0, "duration": 길이}
        칸["target_timerange"] = {"start": 시작, "duration": 길이}
        칸["extra_material_refs"] = [
            x for x in (재료복제(d, d, r) for r in 소리칸본["extra_material_refs"]) if x]
        새소리칸들.append(칸)
        시작 += 길이
    소리트랙["segments"] = 새소리칸들

    # ---- 글자 ----
    # 칸이 가장 많은 글자 트랙이 가사 자막입니다. 통째로 뺍니다.
    자막트랙 = max(글자트랙들, key=lambda t: len(t["segments"]))
    if len(자막트랙["segments"]) > 5:
        d["tracks"].remove(자막트랙)
        글자트랙들.remove(자막트랙)

    # 곡 제목 트랙: 인트로가 끝난 뒤부터 끝까지 한 칸으로 깔려 있던 트랙
    제목트랙 = next((t for t in 글자트랙들
                 if len(t["segments"]) == 1
                 and t["segments"][0]["target_timerange"]["start"] > 0), None)

    # 본 프로젝트에 곡 제목 트랙이 아예 없는 채널이 있습니다(불심명언).
    # 그때는 채널명 글자를 본으로 삼아 새 트랙을 하나 만들어 줍니다.
    # 사장님 지시로 **두 채널 모두 영상에 곡 제목을 띄웁니다.**
    새로만든제목트랙 = False
    if 제목트랙 is None and 곡제목표시:
        제목트랙 = 곡제목트랙만들기(d, 글자트랙들)
        새로만든제목트랙 = True

    for t in 글자트랙들:
        if t is 제목트랙:
            continue
        for 칸 in t["segments"]:
            tr = 칸["target_timerange"]
            if tr["start"] == 0 and tr["duration"] >= 본길이 - 200000:
                tr["duration"] = 총길이

    if 스티커트랙:
        for 칸 in 스티커트랙["segments"]:
            tr = 칸["target_timerange"]
            if tr["start"] == 0 and tr["duration"] >= 본길이 - 200000:
                tr["duration"] = 총길이

    if 제목트랙:
        제목칸본 = copy.deepcopy(제목트랙["segments"][0])
        제목재료본 = next(m for m in d["materials"]["texts"]
                      if m["id"] == 제목칸본["material_id"])
        첫시작 = 제목칸본["target_timerange"]["start"]   # 인트로가 끝나는 시각

        새제목칸들 = []
        시작 = 0
        for 번호, (곡, 길이) in enumerate(zip(곡들, 길이들)):
            치우침 = 첫시작 if 번호 == 0 else 0
            재료 = copy.deepcopy(제목재료본)
            재료["id"] = 새아이디()
            글자내용바꾸기(재료, 곡제목(곡))
            # 본의 글상자는 「천수의 자비」 여섯 글자에 맞춰 폭이 고정되어
            # 있습니다. 우리 제목은 더 길어서 두 줄로 깨지므로 폭을 풉니다.
            재료["fixed_width"] = -1.0
            재료["force_apply_line_max_width"] = False
            d["materials"]["texts"].append(재료)

            칸 = copy.deepcopy(제목칸본)
            칸["id"] = 새아이디()
            칸["material_id"] = 재료["id"]
            # 황금주파수는 본 프로젝트의 제목 자리가 오른쪽이라 안쪽으로
            # 당겨 줍니다. 우리가 새로 만든 트랙(불심명언)은 이미 가운데
            # 정렬로 잡아 두었으므로 건드리지 않습니다. 건드리면 가운데
            # 정렬한 제목이 오른쪽으로 밀려 화면 밖으로 잘립니다.
            if not 새로만든제목트랙:
                칸["clip"]["transform"]["x"] = 제목가로위치
            칸["target_timerange"] = {"start": 시작 + 치우침,
                                     "duration": 길이 - 치우침}
            칸["extra_material_refs"] = [
                x for x in (재료복제(d, d, r) for r in 제목칸본["extra_material_refs"]) if x]
            새제목칸들.append(칸)
            시작 += 길이
        제목트랙["segments"] = 새제목칸들

    쓰기(새폴더 / "draft_content.json", d)
    쓰기(새폴더 / "draft_content.json.bak", d)
    if (새폴더 / "template-2.tmp").exists():
        쓰기(새폴더 / "template-2.tmp", d)

    # ---- 목록 정보 ----
    메타 = 읽기(새폴더 / "draft_meta_info.json")
    지금 = int(time.time() * 1000000)
    메타["draft_id"] = 새아이디()
    메타["draft_name"] = 이름
    메타["draft_fold_path"] = str(새폴더).replace("\\", "/")
    메타["tm_duration"] = 총길이
    메타["tm_draft_create"] = 지금
    메타["tm_draft_modified"] = 지금

    for 묶음 in 메타.get("draft_materials", []):
        if 묶음.get("type") != 0:
            continue
        항목들 = 묶음.setdefault("value", [])
        for 곡, 길이 in zip(곡들, 길이들):
            항목들.append({
                "create_time": int(time.time()), "duration": 길이,
                "extra_info": 곡.name,
                "file_Path": str(곡).replace("\\", "/"),
                "height": 0, "id": str(uuid.uuid4()),
                "import_time": int(time.time()), "import_time_ms": 지금,
                "item_source": 1, "md5": "", "metetype": "music",
                "roughcut_time_range": {"duration": 길이, "start": 0},
                "sub_time_range": {"duration": -1, "start": -1},
                "type": 0, "width": 0})
        항목들.append({
            "create_time": int(time.time()), "duration": 5000000,
            "extra_info": Path(배경).name,
            "file_Path": str(Path(배경).resolve()).replace("\\", "/"),
            "height": 사진재료.get("height", 1080), "id": str(uuid.uuid4()),
            "import_time": int(time.time()), "import_time_ms": 지금,
            "item_source": 1, "md5": "", "metetype": "photo",
            "roughcut_time_range": {"duration": -1, "start": -1},
            "sub_time_range": {"duration": -1, "start": -1},
            "type": 0, "width": 사진재료.get("width", 1920)})
        break
    쓰기(새폴더 / "draft_meta_info.json", 메타)

    print("\n[완료] 캡컷 프로젝트 %s" % 이름)
    print("       %.1f분 / 곡 %d개" % (총길이 / 1e6 / 60, len(곡들)))
    print("       %s" % 새폴더)
    print("       캡컷을 껐다 켜면 홈 화면 목록에 보입니다.")


if __name__ == "__main__":
    파서 = argparse.ArgumentParser()
    파서.add_argument("--이름", required=True, help="새 캡컷 프로젝트 이름 (예: 0922골드)")
    파서.add_argument("--배경", required=True, help="그날 재생화면 그림 png")
    파서.add_argument("--곡폴더", default="",
                     help="곡 폴더들이 들어있는 뿌리 폴더 (없으면 채널 작업 폴더)")
    인자붙이기(파서)
    인자 = 파서.parse_args()

    설정 = 설정읽기(인자.채널)
    본프로젝트 = 설정["캡컷"]["본영상"]
    사진본프로젝트 = 설정["캡컷"]["사진깔기본"]
    곡제목표시 = 설정.get("영상", {}).get("곡제목표시", True)
    곡폴더 = 인자.곡폴더 or 설정["폴더"]["작업"]
    print("채널: %s   본 영상: 「%s」   곡 제목 %s" % (
        설정["표시이름"], 본프로젝트, "표시" if 곡제목표시 else "숨김"))
    만들기(인자.이름, 인자.배경, 곡폴더)
