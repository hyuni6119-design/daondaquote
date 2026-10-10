# -*- coding: utf-8 -*-
r"""캡컷이 내보낸 1회전 영상을 두 번 이어 붙여 모음집을 만듭니다.

사장님 지시(2026-10-10):
  「캡컷으로 1번용을 만들고 나서, 시간 늘리기용으로 1회전했던 걸 2번
   넣는 거야. 그거는 ff 로 만드는 거 어때」

캡컷 내보내기 한 번(약 25분 분량)만 하고, 길이는 ff 로 채웁니다.
다시 인코딩하지 않으므로(`-c copy`) 몇 초면 끝나고 화질도 그대로입니다.
"""
import io, json, os, subprocess, sys, tempfile
sys.stdout.reconfigure(encoding="utf-8")

원본, 낼곳, 차례파일 = sys.argv[1], sys.argv[2], sys.argv[3]
차례 = json.load(io.open(차례파일, encoding="utf-8"))
한바퀴 = 차례["전체"]

임시 = tempfile.mkdtemp(prefix="goldtv_x2_")
목록 = os.path.join(임시, "list.txt")
io.open(목록, "w", encoding="utf-8").write(
    "file '%s'\n" % 원본.replace("\\", "/").replace("'", r"'\''") * 1 +
    "file '%s'\n" % 원본.replace("\\", "/").replace("'", r"'\''"))
os.makedirs(os.path.dirname(낼곳), exist_ok=True)
ㄱ = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                   "-f", "concat", "-safe", "0", "-i", 목록,
                   "-c", "copy", "-movflags", "+faststart", 낼곳],
                  capture_output=True, text=True, encoding="utf-8", errors="replace")
if ㄱ.returncode != 0:
    print(ㄱ.stderr[-1500:]); sys.exit("[실패] 이어붙이기")

곡들 = []
for 바퀴 in (0, 1):
    for 곡 in 차례["곡들"]:
        곡들.append({"시작": 곡["시작"] + 바퀴 * 한바퀴,
                   "제목": 곡["제목"], "파일": 곡["제목"] + ".mp4"})
수록 = os.path.join(os.path.dirname(낼곳), "수록곡.json")
io.open(수록, "w", encoding="utf-8").write(json.dumps(
    {"전체길이": 한바퀴 * 2, "곡들": 곡들}, ensure_ascii=False, indent=2))

크기 = os.path.getsize(낼곳) / (1024 * 1024)
print("[완료] %s" % 낼곳)
print("       %.0fMB · %.0f분 · 곡 %d개 (1회전 %d곡 × 2바퀴)"
      % (크기, 한바퀴 * 2 / 60_000_000, len(곡들), len(차례["곡들"])))
for 곡 in 곡들:
    ㅊ = 곡["시작"] // 1_000_000
    print("  %d:%02d:%02d %s" % (ㅊ // 3600, ㅊ % 3600 // 60, ㅊ % 60, 곡["제목"]))
