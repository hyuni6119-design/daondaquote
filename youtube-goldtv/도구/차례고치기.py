# -*- coding: utf-8 -*-
import sys, re, json, io, os
from pathlib import Path
도구 = Path(r"C:\Users\PC\daondaquote\youtube-goldtv\도구")
sys.path.insert(0, str(도구))
sys.stdout.reconfigure(encoding="utf-8")
import 업로드 as U
from 채널 import 설정읽기
진짜 = "--진짜" in sys.argv
yt = U.인증(설정읽기("황금주파수"))
짝 = {
 "_완성8":"sZor_PrFiFc","_완성9":"BB5SqTDDcxc","_완성10":"-HlCmo-h6cQ","_완성11":"9iVBqU337fs",
 "_완성12":"JBnXzmcUaAk","_완성13":"eC0JiZvfz_A","_완성14":"fBlcY84Wqps","_완성15":"O_t7QeIqNrE",
 "_완성16":"HEvtvnfz3sU","_완성17":"dVlgrenO4yY","_완성18":"LYFeub1NR7Y","_완성19":"QpeDluoc2EI",
 "_완성20":"-9CEjtgu2Qg"}
def 시각(us):
    s = int(us // 1000000)
    return "%d:%02d" % (s//60, s%60)
for 폴, 번호 in 짝.items():
    d = json.load(io.open(os.path.join("D:/골드TV", 폴, "수록곡.json"), encoding="utf-8"))
    곡 = d["곡들"]
    새 = "🕐 수록곡\n" + "\n".join("%s %s" % (시각(ㄱ["시작"]), ㄱ["제목"]) for ㄱ in 곡)
    r = yt.videos().list(part="snippet", id=번호).execute()["items"][0]["snippet"]
    설 = r["description"]
    바뀜, 수 = re.subn(r"🕐 수록곡\n(?:\d+:\d\d .*\n?)+", 새 + "\n", 설)
    if 수 != 1:
        print("!! %s %s — 수록곡 덩이 %d개 찾음, 건너뜀" % (폴, 번호, 수)); continue
    바뀜 = re.sub(r"이 영상에는 \d+곡이", "이 영상에는 %d곡이" % len(곡), 바뀜)
    옛줄 = len(re.findall(r"^\d+:\d\d ", 설, re.M))
    print("%-8s %-12s %2d줄 → %2d줄 (끝 %s)" % (폴, 번호, 옛줄, len(곡), 시각(곡[-1]["시작"])))
    if 진짜:
        몸 = {"title": r["title"], "description": 바뀜, "categoryId": r["categoryId"], "tags": r.get("tags", [])}
        if r.get("defaultLanguage"): 몸["defaultLanguage"] = r["defaultLanguage"]
        if r.get("defaultAudioLanguage"): 몸["defaultAudioLanguage"] = r["defaultAudioLanguage"]
        yt.videos().update(part="snippet", body={"id": 번호, "snippet": 몸}).execute()
        print("   고침")
print("\n%s" % ("고쳤습니다" if 진짜 else "시험만 돌렸습니다 (--진짜 를 붙이면 실제로 고칩니다)"))
