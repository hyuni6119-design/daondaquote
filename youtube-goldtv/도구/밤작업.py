# -*- coding: utf-8 -*-
"""
🌙 밤 작업 도우미 — 매일 밤 PC의 Claude가 영상 관리 사이트와 주고받을 때 씁니다.
(사이트가 주제·썸네일 문구·제목·설명·가사까지 만들어 두면, PC가 수노·제미나이·영상·올리기를 합니다)

사용법:
    python 밤작업.py 할일                          만들 편 목록 (JSON)
    python 밤작업.py 가사저장 <편번호>              곡 폴더를 만들고 곡마다 가사·스타일을 적어 둠
    python 밤작업.py 상태 <편번호> <상태> [메모]     사이트에 진행 상황 적기 (노래중·영상중·올리는중·실패…)
    python 밤작업.py 썸네일 <편번호> <그림파일>      1280×720으로 맞추고(제미나이 표시 잘라냄) 사이트 썸네일로 넣기
    python 밤작업.py 배경 <그림파일> <저장할 png>    영상 배경 그림을 16:9 1920×1080으로 (제미나이 표시 잘라냄)
    python 밤작업.py 지금                          지금 시각(숫자) — 다운로드 버튼 누르기 전에 적어 둠
    python 밤작업.py 받기 <지금 숫자> <옮길 곳>       그 뒤에 새로 받아진 제미나이 그림만 옮김 (예전 파일은 절대 안 건드림)
    python 밤작업.py 올리기 <편번호> <완성.mp4> <수록곡.json> [썸네일.jpg]
                                                  사이트로 영상을 올리고 유튜브로 보내기 (서버가 일부 공개로 올림)

편번호는 사이트 편의 id 입니다 (할일 목록의 "id").
사이트 주소·토큰은 이 폴더의 관리사이트.json 에서 읽습니다 (저장소에 올라가지 않음).
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib import error, request

여기 = Path(__file__).resolve().parent
설정 = json.loads((여기 / "관리사이트.json").read_text(encoding="utf-8-sig"))
주소, 토큰 = 설정["주소"].rstrip("/"), 설정["토큰"]
# 채널 이름 → PC 작업 폴더 (효과합성.py 의 --채널 이름과 같음)
뿌리 = {"불심명언": Path(r"D:\불심명언"), "황금주파수": Path(r"D:\골드TV")}
조각 = 32 * 1024 * 1024
# 그림은 실사풍으로 (사장님 지시 2026-10-27 · 애니메이션·일러스트 말고)
실사 = "진짜 사진 같은 실사풍(DSLR 사진, 사실적인 빛과 질감) — 애니메이션·일러스트·디지털 아트 느낌 금지"


def 부르기(방법, 경로, 몸=None, 머리=None, 날것=False):
    머리 = dict(머리 or {})
    머리["Authorization"] = f"Bearer {토큰}"
    자료 = None
    if 몸 is not None and not 날것:
        자료 = json.dumps(몸, ensure_ascii=False).encode("utf-8")
        머리["Content-Type"] = "application/json"
    elif 날것:
        자료 = 몸
    요청 = request.Request(주소 + 경로, data=자료, method=방법, headers=머리)
    try:
        with request.urlopen(요청, timeout=600) as r:
            return json.loads(r.read().decode("utf-8") or "null")
    except error.HTTPError as e:
        raise SystemExit(f"사이트 오류 {e.code} {경로}: {e.read().decode('utf-8', 'replace')[:300]}")


def 파일보내기(경로, 파일, 이름, 형식):
    """multipart 로 파일 하나 보내기"""
    경계 = "----nightjobboundary7c1"
    몸 = (f"--{경계}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{이름}\"\r\n"
          f"Content-Type: {형식}\r\n\r\n").encode("utf-8") + Path(파일).read_bytes() + f"\r\n--{경계}--\r\n".encode()
    return 부르기("POST", 경로, 몸, {"Content-Type": f"multipart/form-data; boundary={경계}"}, 날것=True)


def 가사만(가사):
    """맨 앞 [Style: …] 줄은 빼고 (스타일은 따로 넣음)"""
    return re.sub(r"^\s*\[Style:[^\]]*\]\s*", "", 가사 or "").strip()


def 채널들():
    return {c["key"]: c["name"] for c in 부르기("GET", "/api/meta")["channels"]}


def 편(편번호):
    return 부르기("GET", f"/api/episodes/{편번호}")


def 폴더(이름, 날짜):
    md = 날짜[5:7] + 날짜[8:10]
    r = 뿌리.get(이름, Path(r"D:\영상") / 이름)
    return {"뿌리": str(r), "곡폴더": str(r / f"{md}-1회전"), "완성": str(r / md / "_완성"),
            "썸네일": str(r / "_오늘이미지" / f"{md}-썸네일.png"), "배경": str(r / "_오늘이미지" / f"{md}-영상용.png")}


def 할일():
    ch = 채널들()
    규칙 = 부르기("GET", "/api/rules")
    out = []
    for e in 부르기("GET", "/api/episodes"):
        mk = e.get("make") or {}
        곡 = mk.get("songs") or []
        if e.get("video_id") or not 곡 or not all(s.get("lyrics") for s in 곡):
            continue
        if (mk.get("pc") or {}).get("state") in ("올림",):
            continue
        rl = 규칙.get(e["channel"], {})
        out.append({
            "id": e["id"], "채널": ch.get(e["channel"], e["channel"]), "편": e["ep"], "공개날짜": e["date"],
            "제목": e.get("title", ""), "썸네일있음": bool(e.get("thumb")), "썸네일문구": mk.get("thumb_text", ""),
            "썸네일프롬프트": mk.get("thumb_prompt", "") + (" " + 실사 if mk.get("thumb_prompt") else ""), "배경프롬프트": (rl.get("image_prompt", "") or "썸네일과 같은 분위기의 장면") + " — 글자 없는 16:9 가로, " + 실사,
            "규칙": {k: rl.get(k) for k in ("songs", "loops", "min_minutes", "max_minutes")},
            "곡": [{"번호": i + 1, "제목": s["title"], "스타일": s.get("style", ""), "가사": 가사만(s["lyrics"])} for i, s in enumerate(곡)],
            "PC상태": (mk.get("pc") or {}).get("state", ""), "폴더": 폴더(ch.get(e["channel"], e["channel"]), e["date"]),
        })
    print(json.dumps(out, ensure_ascii=False, indent=2))


def 가사저장(편번호):
    e = 편(편번호)
    이름 = 채널들().get(e["channel"], e["channel"])
    f = 폴더(이름, e["date"])
    for i, s in enumerate((e.get("make") or {}).get("songs") or []):
        안전 = "".join(c for c in s["title"] if c not in '\\/:*?"<>|').strip() or f"곡{i + 1}"
        d = Path(f["곡폴더"]) / f"{i + 1:02d}-{안전}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "가사.txt").write_text(가사만(s["lyrics"]), encoding="utf-8")
        (d / "스타일.txt").write_text(s.get("style", ""), encoding="utf-8")
        (d / "제목.txt").write_text(s["title"], encoding="utf-8")
        print(d)
    Path(f["완성"]).mkdir(parents=True, exist_ok=True)
    Path(f["썸네일"]).parent.mkdir(parents=True, exist_ok=True)
    print(json.dumps(f, ensure_ascii=False))


def 상태(편번호, 무엇, 메모=""):
    부르기("POST", f"/api/episodes/{편번호}/make", {"pc": {"state": 무엇, "note": 메모}})
    print("적었습니다:", 무엇, 메모)


def 그림맞추기(그림, 낼곳, 폭, 높이):
    # 4% 키워 가운데를 잘라 16:9로
    # 제미나이 ✦ 표시(오른쪽 아래)는 그 자리만 흐리게 지움
    mx, my, mw = int(폭 * 0.900), int(높이 * 0.822), int(폭 * 0.052)
    vf = (f"scale={int(폭 * 1.04)}:{int(높이 * 1.04)}:force_original_aspect_ratio=increase,crop={폭}:{높이},"
          f"delogo=x={mx}:y={my}:w={mw}:h={mw}")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(그림), "-vf", vf, "-q:v", "3", str(낼곳)], check=True)


def 썸네일(편번호, 그림):
    jpg = Path(그림).with_name(Path(그림).stem + "-1280.jpg")
    그림맞추기(그림, jpg, 1280, 720)
    if jpg.stat().st_size > 2 * 1024 * 1024:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(jpg), "-q:v", "6", str(jpg)], check=True)
    파일보내기(f"/api/episodes/{편번호}/thumbnail", jpg, jpg.name, "image/jpeg")
    print("썸네일을 넣었습니다:", jpg)


def 배경(그림, 낼곳):
    Path(낼곳).parent.mkdir(parents=True, exist_ok=True)
    그림맞추기(그림, 낼곳, 1920, 1080)
    print("배경:", 낼곳)


def 올리기(편번호, 영상, 차례, 썸=None):
    e = 편(편번호)
    if e.get("video_id"):
        raise SystemExit("이미 유튜브에 올라간 편입니다")
    크기 = Path(영상).stat().st_size
    u = 부르기("POST", "/api/uploads", {"channel": e["channel"], "date": e["date"], "filename": Path(영상).name, "size": 크기})
    uid = u["id"]
    상태(편번호, "올리는중", f"사이트로 보내는 중 ({크기 / 1024 ** 3:.2f}GB)")
    with open(영상, "rb") as f:
        받음 = 0
        while 받음 < 크기:
            덩이 = f.read(조각)
            for 번 in range(5):
                try:
                    r = 부르기("PUT", f"/api/uploads/{uid}/video?offset={받음}", 덩이, {"Content-Type": "application/octet-stream"}, 날것=True)
                    break
                except SystemExit as x:
                    if 번 == 4:
                        raise
                    print("다시 보냄:", x)
                    받음 = 부르기("GET", f"/api/uploads/{uid}")["received"]
                    f.seek(받음)
                    덩이 = f.read(조각)
            받음 = r["received"]
            print(f"  {받음 / 크기 * 100:.0f}%", flush=True)
    if 썸 or e.get("thumb"):
        썸파일 = Path(썸) if 썸 else None
        if 썸파일 and 썸파일.exists():
            파일보내기(f"/api/uploads/{uid}/thumb", 썸파일, 썸파일.name, "image/jpeg")
    파일보내기(f"/api/uploads/{uid}/chapters", 차례, "수록곡.json", "application/json")
    부르기("PATCH", f"/api/uploads/{uid}", {"title": e.get("title", ""), "description": e.get("description", ""), "tags": e.get("tags") or []})
    부르기("POST", f"/api/uploads/{uid}/go")
    상태(편번호, "올림", "사이트로 다 보냈어요 — 서버가 유튜브에 일부 공개로 올립니다")
    print("올리기 번호:", uid)


def 받기(이후, 옮길곳, 기다림=90):
    """다운로드 폴더에서 '이후' 시각 뒤에 새로 생긴 Gemini 그림 하나만 옮김"""
    import time
    받는곳 = Path.home() / "Downloads"
    for _ in range(기다림 // 3):
        새것 = [p for p in 받는곳.glob("Gemini_Generated_Image_*.png") if p.stat().st_mtime > float(이후)]
        if 새것 and not list(받는곳.glob("*.crdownload")):
            f = max(새것, key=lambda p: p.stat().st_mtime)
            Path(옮길곳).parent.mkdir(parents=True, exist_ok=True)
            f.replace(옮길곳)
            print("받았습니다:", f.name, "→", 옮길곳)
            return
        time.sleep(3)
    raise SystemExit("새 그림이 다운로드되지 않았어요 (예전 파일은 그대로 둠)")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        print(__doc__)
    elif a[0] == "할일":
        할일()
    elif a[0] == "가사저장":
        가사저장(int(a[1]))
    elif a[0] == "상태":
        상태(int(a[1]), a[2], " ".join(a[3:]))
    elif a[0] == "썸네일":
        썸네일(int(a[1]), a[2])
    elif a[0] == "배경":
        배경(a[1], a[2])
    elif a[0] == "지금":
        import time
        print(int(time.time()))
    elif a[0] == "받기":
        받기(a[1], a[2])
    elif a[0] == "올리기":
        올리기(int(a[1]), a[2], a[3], a[4] if len(a) > 4 else None)
    else:
        print(__doc__)
