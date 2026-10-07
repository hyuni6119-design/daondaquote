# -*- coding: utf-8 -*-
r"""
곡당 영상들을 이어붙여 모음집 한 편을 만듭니다.

다시 인코딩하지 않습니다(`-c copy`). 곡당 영상이 이미 만들어져 있으면
1시간짜리 모음집이 **2초** 만에 나옵니다. 캡컷으로 통째로 렌더하면 5분이
걸리고 파일도 8배 커집니다(3GB 대 360MB). 올리는 시간이 34분에서 4분으로
줄어듭니다.

앞에 붙는 14초 인트로만 새로 만듭니다.

필요한 것
    곡당 mp4 가 `노래영상만들기.py` 로 이미 만들어져 있어야 합니다.
    모두 같은 규격(1920x1080·30fps·H.264·AAC 48kHz)이라야 그냥 붙습니다.

사용법
    python 모음집이어붙이기.py --배경 "D:\골드TV\_오늘이미지\영상용.png" ^
        --곡폴더 "D:\골드TV" --저장 "D:\골드TV\_완성\완성.mp4"

    인트로 없이 곡만 붙이려면 --인트로없이
"""

import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import 영상문구
from 노래영상만들기 import 길이재기 as 초길이재기   # 이쪽은 '초' 를 돌려줍니다
# 곡 순서를 정하는 규칙(같은 가사끼리 안 붙게 섞기)은 한 군데에만 두고 함께 씁니다.
from 캡컷모음집만들기 import 곡모으기, 곡제목
from 채널 import 설정읽기, 인자붙이기

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

가로, 세로, 초당프레임 = 1920, 1080, 30


def 실행(명령, 일하는곳=None):
    결과 = subprocess.run(명령, capture_output=True, text=True,
                        encoding="utf-8", errors="replace", cwd=일하는곳)
    if 결과.returncode != 0:
        print(결과.stderr[-2000:])
        sys.exit("[실패] " + " ".join(str(c) for c in 명령[:6]) + " ...")
    return 결과


def 인트로만들기(배경, 낼곳):
    """맨 앞 14초. 뒤에 붙는 곡 영상과 규격을 똑같이 맞춥니다."""
    임시 = tempfile.mkdtemp(prefix="goldtv_intro_")
    try:
        조각, 길이 = 영상문구.인트로필터(임시)
        if not 조각:
            return None
        필터 = ",".join([
            "scale=%d:%d:force_original_aspect_ratio=increase" % (가로, 세로),
            "crop=%d:%d" % (가로, 세로),
            "format=yuv420p",
            *조각,
            "fade=t=in:st=0:d=1",
        ])
        실행(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
             "-loop", "1", "-framerate", str(초당프레임), "-i", str(배경),
             "-f", "lavfi", "-t", "%.3f" % 길이,
             "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
             "-vf", 필터,
             "-map", "0:v:0", "-map", "1:a:0",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
             "-pix_fmt", "yuv420p", "-r", str(초당프레임),
             "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
             "-t", "%.3f" % 길이, str(낼곳)], 일하는곳=임시)
        print("  인트로 %.1f초" % 길이)
        return 낼곳
    finally:
        shutil.rmtree(임시, ignore_errors=True)


def 붙이기(조각들, 낼곳):
    임시 = Path(tempfile.mkdtemp(prefix="goldtv_cat_"))
    try:
        목록 = 임시 / "list.txt"
        목록.write_text(
            "\n".join("file '%s'" % str(p).replace("\\", "/").replace("'", r"'\''")
                      for p in 조각들), encoding="utf-8")
        실행(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
             "-f", "concat", "-safe", "0", "-i", str(목록),
             "-c", "copy", "-movflags", "+faststart", str(낼곳)])
    finally:
        shutil.rmtree(임시, ignore_errors=True)


def 만들기(배경, 곡폴더, 저장, 인트로넣기):
    곡들 = 곡모으기(곡폴더)           # 같은 가사끼리 붙지 않게 이미 섞여 나옵니다
    영상들 = [곡.with_suffix(".mp4") for 곡 in 곡들]
    없는것 = [p for p in 영상들 if not p.exists()]
    if 없는것:
        print("[실패] 곡당 영상이 아직 없습니다. 먼저 노래영상만들기.py 를 돌리세요.")
        for p in 없는것[:5]:
            print("   없음:", p.name)
        sys.exit(1)

    저장 = Path(저장)
    저장.parent.mkdir(parents=True, exist_ok=True)
    임시 = Path(tempfile.mkdtemp(prefix="goldtv_head_"))
    try:
        조각들 = []
        if 인트로넣기:
            머리 = 인트로만들기(배경, 임시 / "intro.mp4")
            if 머리:
                조각들.append(머리)
        조각들 += 영상들

        print("  곡 %d개를 이어붙입니다..." % len(영상들))
        붙이기(조각들, 저장)
    finally:
        shutil.rmtree(임시, ignore_errors=True)

    # 챕터를 만들려면 곡이 몇 분에 시작하는지가 필요합니다. 붙인 순서대로
    # 길이를 더해가며 적어 두면, 업로드정보만들기.py 가 그대로 읽어 씁니다.
    시작 = sum(l for _, l in 영상문구.인트로들) if 인트로넣기 else 0.0
    목록 = []
    for 곡, 영상 in zip(곡들, 영상들):
        목록.append({"시작": int(round(시작 * 1_000_000)),
                    "제목": 곡제목(곡),
                    "파일": 영상.name})
        시작 += 초길이재기(영상)

    수록곡파일 = 저장.with_name("수록곡.json")
    with io.open(수록곡파일, "w", encoding="utf-8") as f:
        json.dump({"전체길이": int(round(시작 * 1_000_000)), "곡들": 목록},
                  f, ensure_ascii=False, indent=2)

    크기 = 저장.stat().st_size / (1024 * 1024)
    print("\n[완료] %s" % 저장)
    print("       %.0fMB · %.0f분 · 곡 %d개" % (크기, 시작 / 60, len(영상들)))
    print("       수록곡 목록: %s" % 수록곡파일.name)
    print("\n수록곡 (챕터용 · 같은 곡은 처음 한 번만)")
    센것 = set()
    for 항 in 목록:
        if 항["제목"] in 센것:
            continue
        센것.add(항["제목"])
        전체초 = 항["시작"] // 1_000_000
        시, 나머지 = divmod(전체초, 3600)
        분, 초 = divmod(나머지, 60)
        때 = ("%d:%02d:%02d" % (시, 분, 초)) if 시 else ("%d:%02d" % (분, 초))
        print("  %s %s" % (때, 항["제목"]))


if __name__ == "__main__":
    파서 = argparse.ArgumentParser()
    파서.add_argument("--배경", required=True, help="인트로에 깔 그림")
    파서.add_argument("--곡폴더", required=True, help="곡 폴더들이 든 뿌리 폴더")
    파서.add_argument("--저장", required=True, help="만들 mp4 경로")
    파서.add_argument("--인트로없이", action="store_true")
    인자붙이기(파서)
    인자 = 파서.parse_args()
    영상문구.채널적용(설정읽기(인자.채널))
    만들기(인자.배경, 인자.곡폴더, 인자.저장, not 인자.인트로없이)
