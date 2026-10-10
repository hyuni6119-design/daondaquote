# -*- coding: utf-8 -*-
"""캡컷 프로젝트에서 1회전 곡 차례를 뽑습니다."""
import io, json, os, sys
sys.stdout.reconfigure(encoding="utf-8")
뿌리 = r"C:\Users\PC\AppData\Local\CapCut\User Data\Projects\com.lveditor.draft"
여기 = os.path.dirname(os.path.abspath(__file__))
이름 = sys.argv[1]
ㅈ = json.load(io.open(os.path.join(뿌리, 이름, "draft_content.json"), encoding="utf-8"))
소리 = {m["id"]: m for m in ㅈ["materials"].get("audios", [])}
곡들 = []
for 트랙 in ㅈ["tracks"]:
    if 트랙.get("type") != "audio":
        continue
    for ㅅ in 트랙["segments"]:
        m = 소리.get(ㅅ["material_id"])
        if not m:
            continue
        제목 = os.path.splitext(os.path.basename(m.get("path", "")))[0]
        곡들.append({"시작": ㅅ["target_timerange"]["start"],
                   "제목": 제목,
                   "길이": ㅅ["target_timerange"]["duration"]})
곡들.sort(key=lambda x: x["시작"])
전체 = ㅈ.get("duration") or (곡들[-1]["시작"] + 곡들[-1]["길이"])
낼곳 = os.path.join(여기, "%s-1회전차례.json" % 이름[:4])
io.open(낼곳, "w", encoding="utf-8").write(
    json.dumps({"전체": 전체, "곡들": 곡들}, ensure_ascii=False, indent=1))
print("%s  전체 %.1f초  곡 %d개" % (이름, 전체/1e6, len(곡들)))
for ㄱ in 곡들:
    print("   %6.1f  %s" % (ㄱ["시작"]/1e6, ㄱ["제목"]))
