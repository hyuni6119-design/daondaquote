# -*- coding: utf-8 -*-
r"""캡컷 없이 모음집 1바퀴를 만듭니다 (캡컷 효과 그대로).

    배경 그림 + 고정 효과판(오프닝·윗줄·채널명·음파, 캡컷에서 한 번 구운 것) + 곡 제목 효과 + 곡

고정 효과판은 캡컷에서 검정 바탕·흰 바탕으로 한 번씩 내보낸 것입니다.
두 판을 견주면  결과 = 검정판 + (흰판 − 검정판) × 배경  으로 캡컷과 똑같이 얹힙니다.
앞부분(오프닝·등장)은 그대로, 그 뒤는 반복판을 끝까지 돌립니다.
황금주파수의 음파 스티커는 주기(4.5초)가 달라서 제자리만 따로 돌립니다.

    python 효과합성.py --채널 불심명언 --배경 그림.png --곡폴더 D:\불심명언\1103-1회전 --저장 D:\...\1바퀴.mp4

`수록곡.json` 을 같은 폴더에 남깁니다 (두번붙이기.py 가 그대로 읽습니다).
"""
import argparse, io, json, os, subprocess, sys
from pathlib import Path

여기 = Path(__file__).resolve().parent
sys.path.insert(0, r"C:\Users\PC\daondaquote\youtube-goldtv\도구")

# 판: 고정_검정_앞.mkv · 고정_검정_반복.mkv (· 고정_검정_스티커.mkv) 와 흰판이 있는 곳
# 첫제목: 첫 곡 제목이 나오는 시각 (황금주파수는 오프닝 문구가 끝난 뒤)
채널들 = {
    "불심명언": dict(판="D:/불심명언/_효과판", 첫제목=0.0, 스티커=None),
    "황금주파수": dict(판="D:/골드TV/_효과판", 첫제목=13.933, 스티커=dict(x=48, y=104, 시작=20.0)),
}


def 길이(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--채널", default="불심명언", choices=list(채널들))
    p.add_argument("--배경", required=True)
    p.add_argument("--곡폴더", required=True)
    p.add_argument("--저장", required=True)
    p.add_argument("--최대초", type=float, default=0, help="시험용: 앞부분만")
    a = p.parse_args()
    설정 = 채널들[a.채널]

    from 캡컷모음집만들기 import 곡모으기, 곡제목
    곡들 = 곡모으기(a.곡폴더)
    길이들 = [길이(f) for f in 곡들]
    저장 = Path(a.저장); 저장.parent.mkdir(parents=True, exist_ok=True)
    일 = 저장.parent / "_제목효과"; 일.mkdir(exist_ok=True)

    # 곡 제목 효과판 만들기
    제목들 = []
    for i, f in enumerate(곡들):
        d = 일 / ("%02d" % i)
        if not (d / "반복.mov").exists():
            subprocess.run([sys.executable, str(여기 / "제목효과.py"), "만들기", 곡제목(f), str(d),
                            "--채널", a.채널], check=True)
        제목들.append(d)

    전체 = sum(길이들)
    if a.최대초:
        전체 = min(전체, a.최대초)
    판 = Path(설정["판"])
    입력, 필터 = ["-loop", "1", "-framerate", "30", "-i", a.배경], []
    필터.append("[0]scale=1920:-1,crop=1920:1080:0:0,format=gbrp,setsar=1,trim=duration=%.3f[bg]" % 전체)
    k = 1
    for 색, 이름 in (("검정", "b"), ("흰", "w")):
        입력 += ["-i", str(판 / ("고정_%s_앞.mkv" % 색)), "-stream_loop", "-1", "-i", str(판 / ("고정_%s_반복.mkv" % 색))]
        필터.append("[%d][%d]concat=n=2:v=1,trim=duration=%.3f,format=gbrp[%s0]" % (k, k + 1, 전체, 이름))
        k += 2
        st = 설정["스티커"]
        if st:
            입력 += ["-stream_loop", "-1", "-i", str(판 / ("고정_%s_스티커.mkv" % 색))]
            필터.append("[%d]format=gbrp,setpts=PTS+%.3f/TB[%ss]" % (k, st["시작"], 이름))
            # format=gbrp 를 꼭 줌: 기본(yuv420)으로 바뀌면 아래 빼기·곱하기가 색 채널에서 깨져 흑백이 됨
            필터.append("[%s0][%ss]overlay=%d:%d:format=gbrp:enable='gte(t,%.3f)':eof_action=pass,format=gbrp[%s1]"
                        % (이름, 이름, st["x"], st["y"], st["시작"], 이름))
            k += 1
        else:
            필터.append("[%s0]null[%s1]" % (이름, 이름))
    필터 += ["[b1]split[b1a][b1b]", "[w1][b1a]blend=all_mode=subtract[d]", "[d][bg]blend=all_mode=multiply[m]",
            "[b1b][m]blend=all_mode=addition,format=yuva444p[v0]"]
    차례 = []
    시작 = 0.0
    앞 = "v0"
    for i, (f, L, d) in enumerate(zip(곡들, 길이들, 제목들)):
        if 시작 >= 전체:
            break
        자리 = json.load(io.open(d / "자리.json", encoding="utf-8"))
        치우침 = 설정["첫제목"] if i == 0 else 0.0
        t0 = 시작 + 치우침
        보일 = min(L - 치우침, 전체 - t0)
        if 자리["등장초"] > 0:
            입력 += ["-i", str(d / "등장.mov"), "-stream_loop", "-1", "-i", str(d / "반복.mov")]
            필터.append("[%d][%d]concat=n=2:v=1,trim=duration=%.3f,setpts=PTS+%.3f/TB[t%d]" % (k, k + 1, 보일, t0, i))
            k += 2
        else:
            입력 += ["-stream_loop", "-1", "-i", str(d / "반복.mov")]
            필터.append("[%d]trim=duration=%.3f,setpts=PTS+%.3f/TB[t%d]" % (k, 보일, t0, i))
            k += 1
        필터.append("[%s][t%d]overlay=%d:%d:eof_action=pass:enable='between(t,%.3f,%.3f)'[v%d]"
                    % (앞, i, 자리["x"], 자리["y"], t0, t0 + 보일 - 0.001, i + 1))
        앞 = "v%d" % (i + 1)
        차례.append({"시작": int(round(시작 * 1e6)), "제목": 곡제목(f), "파일": f.name})
        시작 += L
    필터.append("[%s]format=yuv420p[v]" % 앞)
    # 소리: 곡을 차례대로 이어 붙임
    목록 = 일 / "소리.txt"
    io.open(목록, "w", encoding="utf-8").write(
        "".join("file '%s'\n" % str(f).replace("\\", "/").replace("'", r"'\''") for f in 곡들))
    입력 += ["-f", "concat", "-safe", "0", "-i", str(목록)]
    명령 = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-stats"] + 입력 + [
        "-filter_complex", ";".join(필터), "-map", "[v]", "-map", "%d:a" % k,
        "-t", "%.3f" % 전체, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-tune", "stillimage",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(저장)]
    subprocess.run(명령, check=True)
    json.dump({"전체": int(round(전체 * 1e6)), "곡들": 차례},
              io.open(저장.parent / "수록곡.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("[완료]", 저장, "%.1f분 · 곡 %d개" % (전체 / 60, len(차례)))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
