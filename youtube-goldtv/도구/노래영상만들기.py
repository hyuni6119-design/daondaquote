# -*- coding: utf-8 -*-
r"""
골드TV 하루치 영상 만들기

그날 뽑은 재생화면 그림 한 장을 배경으로 깔고, 곡(mp3) 하나마다 mp4를
하나씩 만듭니다. 결과물은 mp3 바로 옆에 같은 이름으로 생깁니다.

    D:\골드TV\007-다시만날인연이라\
        다시 만날 인연이라.mp3
        다시 만날 인연이라.mp4   <- 이렇게 생깁니다

사용법
    한 폴더만:
        python 노래영상만들기.py --배경 "D:\골드TV\_오늘이미지\0918-영상용.png" ^
            "D:\골드TV\007-다시만날인연이라"

    그날 폴더 전부 (하위 폴더를 훑습니다. _로 시작하는 폴더는 건너뜁니다):
        python 노래영상만들기.py --배경 "D:\골드TV\_오늘이미지\0918-영상용.png" ^
            --전체 "D:\골드TV"

    이미 만든 mp4 는 건너뜁니다. 다시 만들려면 --다시.
    그림을 완전히 정지시키려면 --정지.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import 영상문구

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

소리확장자 = {".mp3", ".wav", ".m4a", ".aac", ".flac"}

가로, 세로 = 1920, 1080
초당프레임 = 30
움직임_배율 = 1.12      # 그림을 이만큼 키워두고 그 안에서 천천히 움직입니다
움직임_주기 = 45        # 초. 이 시간마다 한 번 왕복합니다
시작_페이드 = 1.0
끝맺음_페이드 = 3.0


def 도구확인():
    for 이름 in ("ffmpeg", "ffprobe"):
        if shutil.which(이름) is None:
            sys.exit(f"[실패] {이름} 을(를) 찾을 수 없습니다. winget install Gyan.FFmpeg")


def 길이재기(파일):
    결과 = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(파일)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if 결과.returncode != 0:
        sys.exit("[실패] 길이를 읽지 못했습니다: " + str(파일))
    return float(결과.stdout.strip())


def 영상필터(길이, 정지, 임시폴더=None, 곡제목=""):
    큰가로 = int(가로 * 움직임_배율) // 2 * 2
    큰세로 = int(세로 * 움직임_배율) // 2 * 2

    조각 = [f"scale={큰가로}:{큰세로}:force_original_aspect_ratio=increase",
           f"crop={큰가로}:{큰세로}"]

    if 정지:
        조각.append(f"crop={가로}:{세로}")
    else:
        # 그림을 조금 키워두고 잘라내는 창만 천천히 왕복시킵니다.
        # 확대를 매 프레임 다시 계산하는 zoompan 보다 훨씬 빠릅니다.
        흔들 = f"sin(2*PI*t/{움직임_주기})"
        조각.append(
            f"crop={가로}:{세로}:x='(iw-ow)/2*(1+{흔들})':y='(ih-oh)/2*(1+{흔들})'")

    조각.append("format=yuv420p")
    # 황주 고정 문구를 여기서 구워 넣습니다. 그래야 나중에 모음집으로 이어붙일 때
    # 다시 인코딩하지 않고 그대로 붙일 수 있습니다.
    if 임시폴더:
        조각 += 영상문구.고정문구필터(임시폴더, 곡제목)
    if 시작_페이드 > 0:
        조각.append(f"fade=t=in:st=0:d={시작_페이드}")
    if 끝맺음_페이드 > 0:
        조각.append(f"fade=t=out:st={max(길이 - 끝맺음_페이드, 0):.3f}:d={끝맺음_페이드}")
    return ",".join(조각)


def 곡제목뽑기(파일):
    이름 = 파일.stem
    if 이름.endswith(")") and " (" in 이름:
        이름 = 이름[:이름.rindex(" (")]
    return 이름


def 한곡만들기(노래, 배경, 정지, 문구넣기=True):
    결과물 = 노래.with_suffix(".mp4")
    길이 = 길이재기(노래)
    임시 = tempfile.mkdtemp(prefix="goldtv_") if 문구넣기 else None

    명령 = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-stats",
        "-loop", "1", "-framerate", str(초당프레임), "-i", str(배경),
        "-i", str(노래),
        "-vf", 영상필터(길이, 정지, 임시, 곡제목뽑기(노래) if 문구넣기 else ""),
        "-af", (f"afade=t=out:st={max(길이 - 끝맺음_페이드, 0):.3f}:d={끝맺음_페이드}"
                if 끝맺음_페이드 > 0 else "anull"),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(초당프레임),
        "-c:a", "aac", "-b:a", "192k",
        "-t", f"{길이:.3f}", "-movflags", "+faststart",
        str(결과물),
    ]
    결과 = subprocess.run(명령, capture_output=True, text=True,
                         encoding="utf-8", errors="replace", cwd=임시)
    if 임시:
        shutil.rmtree(임시, ignore_errors=True)
    if 결과.returncode != 0:
        print(결과.stderr[-2000:])
        sys.exit("[실패] " + 노래.name)

    크기 = 결과물.stat().st_size / (1024 * 1024)
    print(f"      -> {결과물.name}  {길이/60:.1f}분 / {크기:.0f}MB")
    return 결과물


def 곡모으기(폴더):
    return sorted(p for p in 폴더.iterdir()
                  if p.is_file() and p.suffix.lower() in 소리확장자)


def 만들기(폴더들, 배경, 정지, 다시, 문구넣기=True):
    전체 = []
    for 폴더 in 폴더들:
        for 노래 in 곡모으기(폴더):
            전체.append(노래)

    if not 전체:
        sys.exit("[실패] 노래 파일을 찾지 못했습니다.")

    print(f"\n배경 : {배경}")
    print(f"곡   : {len(전체)}개\n")

    만든것, 건너뛴것 = [], 0
    for 번호, 노래 in enumerate(전체, 1):
        결과물 = 노래.with_suffix(".mp4")
        표시 = f"[{번호}/{len(전체)}] {노래.parent.name} / {노래.name}"
        if 결과물.exists() and not 다시:
            print(표시 + "  (이미 있음, 건너뜀)")
            건너뛴것 += 1
            continue
        print(표시, flush=True)
        만든것.append(한곡만들기(노래, 배경, 정지, 문구넣기))

    print(f"\n[완료] 새로 만든 영상 {len(만든것)}개, 건너뛴 것 {건너뛴것}개")


if __name__ == "__main__":
    파서 = argparse.ArgumentParser(description="곡마다 영상 하나씩 만듭니다.")
    파서.add_argument("폴더", nargs="*", help="곡이 들어있는 폴더들")
    파서.add_argument("--배경", required=True, help="그날 재생화면 그림(png)")
    파서.add_argument("--전체", default="", help="이 폴더의 하위 폴더 전부를 훑습니다")
    파서.add_argument("--정지", action="store_true", help="그림을 움직이지 않습니다")
    파서.add_argument("--다시", action="store_true", help="이미 만든 mp4도 다시 만듭니다")
    파서.add_argument("--문구없이", action="store_true",
                     help="황주 고정 문구(채널명·안내·곡 제목)를 넣지 않습니다")
    인자 = 파서.parse_args()

    도구확인()

    배경 = Path(인자.배경).resolve()
    if not 배경.is_file():
        sys.exit("[실패] 배경 그림을 찾을 수 없습니다: " + str(배경))

    폴더들 = [Path(p).resolve() for p in 인자.폴더]
    if 인자.전체:
        뿌리 = Path(인자.전체).resolve()
        폴더들 += sorted(p for p in 뿌리.iterdir()
                       if p.is_dir() and not p.name.startswith("_"))

    폴더들 = [p for p in 폴더들 if p.is_dir()]
    if not 폴더들:
        sys.exit("[실패] 작업할 폴더가 없습니다.")

    만들기(폴더들, 배경, 인자.정지, 인자.다시, not 인자.문구없이)
