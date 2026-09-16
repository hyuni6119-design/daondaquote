# -*- coding: utf-8 -*-
"""
노래(mp3)와 영상/이미지 클립을 합쳐 유튜브용 mp4 한 개를 만듭니다.

사용법:
    python 영상만들기.py "C:\\골드TV\\001-비우니-채워지더라"

폴더 구조:
    001-비우니-채워지더라/
    ├── 노래.mp3          (필수)
    ├── 영상/             (필수) 01.mp4, 02.png ... 이름순으로 배치됩니다
    ├── 자막.srt          (선택) 있으면 화면에 구워 넣습니다
    ├── 설정.json         (선택) 없으면 기본값으로 동작합니다
    └── 완성.mp4          ← 결과물이 여기 생깁니다
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

기본설정 = {
    "가로": 1920,
    "세로": 1080,
    "초당프레임": 30,
    "클립길이": 8,          # 클립 하나가 화면에 머무는 초
    "이미지_천천히확대": True,
    "장면전환_페이드": 0.8,   # 초. 0으로 두면 전환 효과 없음
    "끝맺음_페이드": 3,       # 마지막 몇 초 동안 어두워질지
    "자막_글자크기": 54,
    "자막_글꼴": "Malgun Gothic",
    "자막_아래여백": 110,
}


def 실행(명령, **kw):
    """ffmpeg를 조용히 실행하고, 실패하면 에러를 그대로 보여줍니다."""
    결과 = subprocess.run(명령, capture_output=True, text=True,
                         encoding="utf-8", errors="replace", **kw)
    if 결과.returncode != 0:
        print("\n[실패] 명령 실행 중 오류가 났습니다:\n  " + " ".join(str(c) for c in 명령))
        print(결과.stderr[-3000:])
        sys.exit(1)
    return 결과


def 도구확인():
    for 이름 in ("ffmpeg", "ffprobe"):
        if shutil.which(이름) is None:
            print(f"[실패] {이름} 을(를) 찾을 수 없습니다.")
            print("       명령 프롬프트에서 아래를 실행해 설치하세요.")
            print("       winget install Gyan.FFmpeg")
            print("       설치 후 명령 프롬프트를 새로 열어야 인식됩니다.")
            sys.exit(1)


def 길이재기(파일):
    결과 = 실행(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(파일)])
    return float(결과.stdout.strip())


def 설정읽기(작업폴더):
    설정 = dict(기본설정)
    설정파일 = 작업폴더 / "설정.json"
    if 설정파일.exists():
        with open(설정파일, encoding="utf-8") as f:
            설정.update(json.load(f))
        print(f"  설정.json 을 읽었습니다.")
    return 설정


def 클립목록(영상폴더):
    파일들 = sorted(p for p in 영상폴더.iterdir()
                   if p.suffix.lower() in VIDEO_EXT | IMAGE_EXT)
    if not 파일들:
        print(f"[실패] {영상폴더} 안에 영상이나 이미지가 없습니다.")
        sys.exit(1)
    return 파일들


def 화면맞추기(설정):
    """어떤 비율로 들어와도 잘라내서 화면을 꽉 채웁니다."""
    가로, 세로 = 설정["가로"], 설정["세로"]
    return (f"scale={가로}:{세로}:force_original_aspect_ratio=increase,"
            f"crop={가로}:{세로},fps={설정['초당프레임']},format=yuv420p")


def 조각만들기(원본, 길이, 저장할곳, 설정):
    """클립 하나를 정해진 길이와 규격으로 잘라 별도 파일로 만듭니다."""
    이미지인가 = 원본.suffix.lower() in IMAGE_EXT
    필터 = []

    if 이미지인가 and 설정["이미지_천천히확대"]:
        # 정지 이미지는 아주 느리게 확대해야 영상처럼 보입니다.
        총프레임 = int(길이 * 설정["초당프레임"])
        필터.append(
            f"scale={설정['가로']*2}:{설정['세로']*2}:force_original_aspect_ratio=increase,"
            f"crop={설정['가로']*2}:{설정['세로']*2},"
            f"zoompan=z='min(zoom+0.00035,1.12)':d={총프레임}:"
            f"s={설정['가로']}x{설정['세로']}:fps={설정['초당프레임']},format=yuv420p"
        )
    else:
        필터.append(화면맞추기(설정))

    페이드 = float(설정["장면전환_페이드"])
    if 페이드 > 0 and 길이 > 페이드 * 2:
        필터.append(f"fade=t=in:st=0:d={페이드}")
        필터.append(f"fade=t=out:st={길이 - 페이드:.3f}:d={페이드}")

    명령 = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    if 이미지인가:
        명령 += ["-loop", "1", "-t", f"{길이:.3f}", "-i", str(원본)]
    else:
        명령 += ["-stream_loop", "-1", "-t", f"{길이:.3f}", "-i", str(원본)]
    명령 += ["-vf", ",".join(필터), "-an",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-r", str(설정["초당프레임"]),
            str(저장할곳)]
    실행(명령)


def 자막필터(설정):
    스타일 = (f"FontName={설정['자막_글꼴']},FontSize={설정['자막_글자크기']},"
             "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
             "BorderStyle=1,Outline=3,Shadow=1,Alignment=2,"
             f"MarginV={설정['자막_아래여백']}")
    # 윈도우 경로에 콜론이 들어가면 필터가 깨지므로 임시폴더로 옮겨 파일명만 씁니다.
    return f"subtitles=자막.srt:force_style='{스타일}'"


def 만들기(작업폴더):
    작업폴더 = Path(작업폴더).resolve()
    if not 작업폴더.is_dir():
        print(f"[실패] 폴더를 찾을 수 없습니다: {작업폴더}")
        sys.exit(1)

    노래 = next((p for p in 작업폴더.iterdir()
                if p.suffix.lower() in {".mp3", ".wav", ".m4a", ".aac", ".flac"}), None)
    if 노래 is None:
        print(f"[실패] {작업폴더} 안에 노래 파일(mp3 등)이 없습니다.")
        sys.exit(1)

    영상폴더 = 작업폴더 / "영상"
    if not 영상폴더.is_dir():
        print(f"[실패] '영상' 폴더가 없습니다: {영상폴더}")
        sys.exit(1)

    설정 = 설정읽기(작업폴더)
    노래길이 = 길이재기(노래)
    클립들 = 클립목록(영상폴더)
    클립길이 = float(설정["클립길이"])
    필요한조각수 = int(노래길이 // 클립길이) + 1

    print(f"  노래   : {노래.name} ({노래길이/60:.1f}분)")
    print(f"  클립   : {len(클립들)}개")
    print(f"  조각   : {필요한조각수}개 (하나당 {클립길이:.0f}초, 모자라면 순서대로 반복)")

    임시 = Path(tempfile.mkdtemp(prefix="goldtv_"))
    try:
        조각파일들 = []
        for 번호 in range(필요한조각수):
            원본 = 클립들[번호 % len(클립들)]
            저장할곳 = 임시 / f"조각{번호:04d}.mp4"
            print(f"  [{번호+1}/{필요한조각수}] {원본.name}", flush=True)
            조각만들기(원본, 클립길이, 저장할곳, 설정)
            조각파일들.append(저장할곳)

        목록파일 = 임시 / "목록.txt"
        목록파일.write_text(
            "\n".join(f"file '{p.as_posix()}'" for p in 조각파일들),
            encoding="utf-8")

        이어붙인것 = 임시 / "이어붙임.mp4"
        print("  조각들을 이어붙이는 중...")
        실행(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
             "-f", "concat", "-safe", "0", "-i", str(목록파일),
             "-c", "copy", str(이어붙인것)])

        자막 = 작업폴더 / "자막.srt"
        결과물 = 작업폴더 / "완성.mp4"

        영상필터 = []
        끝페이드 = float(설정["끝맺음_페이드"])
        if 끝페이드 > 0:
            영상필터.append(f"fade=t=out:st={max(노래길이-끝페이드,0):.3f}:d={끝페이드}")

        명령 = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
               "-i", str(이어붙인것), "-i", str(노래)]

        작업디렉터리 = None
        if 자막.exists():
            shutil.copy(자막, 임시 / "자막.srt")
            영상필터.insert(0, 자막필터(설정))
            작업디렉터리 = str(임시)
            print("  자막을 화면에 구워 넣습니다.")

        if 영상필터:
            명령 += ["-vf", ",".join(영상필터),
                    "-c:v", "libx264", "-preset", "medium", "-crf", "20"]
        else:
            명령 += ["-c:v", "copy"]

        명령 += ["-map", "0:v:0", "-map", "1:a:0",
                "-af", f"afade=t=out:st={max(노래길이-끝페이드,0):.3f}:d={끝페이드}"
                if 끝페이드 > 0 else "anull",
                "-c:a", "aac", "-b:a", "192k",
                "-t", f"{노래길이:.3f}",
                "-movflags", "+faststart",
                str(결과물)]

        print("  마지막으로 합치는 중... (몇 분 걸립니다)")
        실행(명령, cwd=작업디렉터리)

        크기 = 결과물.stat().st_size / (1024 * 1024)
        print(f"\n[완료] {결과물}")
        print(f"       {노래길이/60:.1f}분 / {크기:.0f}MB")
    finally:
        shutil.rmtree(임시, ignore_errors=True)


if __name__ == "__main__":
    파서 = argparse.ArgumentParser(description="노래와 영상을 합쳐 유튜브용 mp4를 만듭니다.")
    파서.add_argument("폴더", help="노래.mp3 와 영상/ 폴더가 들어있는 작업 폴더")
    인자 = 파서.parse_args()

    도구확인()
    print(f"\n영상 만들기: {인자.폴더}\n")
    만들기(인자.폴더)
