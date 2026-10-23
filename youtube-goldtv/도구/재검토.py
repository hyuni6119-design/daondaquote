# -*- coding: utf-8 -*-
"""예약된 영상을 한눈에 훑어 봅니다.

    python 재검토.py                  # 황금주파수
    python 재검토.py --채널 불심명언    # (API 인증되면)

보는 것: 예약 날짜·시각, 영상 길이, 수록곡 차례 줄 수와 마지막 시각,
「이 영상에는 N곡이」 문구, 태그, 제목 중복, 지난 영상의 공개 상태.

차례 마지막 시각이 영상 길이의 90% 근처여야 두 회전이 다 들어간 것입니다.
40%대면 1회전 분량만 들어간 것이니 차례고치기.py 로 고칩니다.
"""
import sys, re, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")
import 업로드 as U
from 채널 import 설정읽기

이름 = "황금주파수"
if "--채널" in sys.argv:
    이름 = sys.argv[sys.argv.index("--채널") + 1]

def 초(d):
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d or "")
    if not m:
        return 0
    h, mi, s = [int(x or 0) for x in m.groups()]
    return h * 3600 + mi * 60 + s

yt = U.인증(설정읽기(이름))
업 = yt.channels().list(part="contentDetails", mine=True).execute()
업 = 업["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

번호들, 쪽 = [], None
while True:
    r = yt.playlistItems().list(part="contentDetails", playlistId=업,
                                maxResults=50, pageToken=쪽).execute()
    번호들 += [i["contentDetails"]["videoId"] for i in r["items"]]
    쪽 = r.get("nextPageToken")
    if not 쪽:
        break
번호들 = list(dict.fromkeys(번호들))

모두 = []
for i in range(0, len(번호들), 50):
    모두 += yt.videos().list(part="snippet,status,contentDetails",
                            id=",".join(번호들[i:i + 50])).execute()["items"]

예약 = [v for v in 모두
        if v["status"].get("privacyStatus") == "private" and v["status"].get("publishAt")]
예약.sort(key=lambda v: v["status"]["publishAt"])

print("== %s ==  전체 %d편 / 예약 %d편\n" % (이름, len(모두), len(예약)))
제목들, 탈 = {}, 0
for v in 예약:
    설 = v["snippet"].get("description", "")
    줄 = re.findall(r"^(\d+):(\d\d) (.+)$", 설, re.M)
    끝 = int(줄[-1][0]) * 60 + int(줄[-1][1]) if 줄 else 0
    길 = 초(v["contentDetails"].get("duration"))
    곡 = re.search(r"이 영상에는 (\d+)곡", 설)
    덮 = 끝 * 100.0 / 길 if 길 else 0
    문제 = []
    if 덮 < 80:
        문제.append("차례가 %.0f%% 까지만 — 1회전만 들어갔습니다" % 덮)
    if 곡 and len(줄) != int(곡.group(1)):
        문제.append("문구는 %s곡인데 차례는 %d줄" % (곡.group(1), len(줄)))
    if not v["snippet"].get("tags"):
        문제.append("태그 없음")
    if not v["status"]["publishAt"].endswith("T12:00:00Z"):
        문제.append("예약 시각 %s (21시가 아님)" % v["status"]["publishAt"][11:19])
    제목들.setdefault(v["snippet"]["title"], []).append(v["id"])
    print("%s | %-12s | %2d:%02d | 차례 %2d줄 끝 %2d:%02d (%2.0f%%) | %s" % (
        v["status"]["publishAt"][:10], v["id"], 길 // 60, 길 % 60,
        len(줄), 끝 // 60, 끝 % 60, 덮, v["snippet"]["title"][:30]))
    for ㅁ in 문제:
        print("    ↳ %s" % ㅁ)
        탈 += 1

겹 = {t: i for t, i in 제목들.items() if len(i) > 1}
print("\n제목 중복: %s" % (겹 if 겹 else "없음"))
print("걸린 것: %d" % 탈)

지난 = [v for v in 모두 if v["snippet"]["title"].startswith("[지난 영상]")]
안숨 = [(v["id"], v["status"]["privacyStatus"]) for v in 지난
        if v["status"]["privacyStatus"] != "private"]
print("[지난 영상] %d편 중 비공개가 아닌 것: %s" % (len(지난), 안숨 if 안숨 else "없음"))
남 = [(v["id"], v["status"].get("publishAt")) for v in 지난 if v["status"].get("publishAt")]
if 남:
    print("  !! 예약이 남아 있는 지난 영상: %s" % 남)
