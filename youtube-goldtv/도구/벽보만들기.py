# -*- coding: utf-8 -*-
"""채널에 걸린 썸네일을 한 장에 붙여 봅니다 (시청자가 보는 그대로).

    python 벽보만들기.py            # 황금주파수, 최근 24편
    python 벽보만들기.py --채널 불심명언 --개수 24
"""
import sys, os, io, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image
import 업로드 as U
from 채널 import 설정읽기

이름 = "황금주파수"
개수 = 24
if "--채널" in sys.argv: 이름 = sys.argv[sys.argv.index("--채널")+1]
if "--개수" in sys.argv: 개수 = int(sys.argv[sys.argv.index("--개수")+1])

yt = U.인증(설정읽기(이름))
업 = yt.channels().list(part="contentDetails", mine=True).execute()
업 = 업["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
번호들, 쪽 = [], None
while len(번호들) < 개수*3:
    r = yt.playlistItems().list(part="contentDetails", playlistId=업, maxResults=50, pageToken=쪽).execute()
    번호들 += [i["contentDetails"]["videoId"] for i in r["items"]]
    쪽 = r.get("nextPageToken")
    if not 쪽: break
번호들 = list(dict.fromkeys(번호들))

공개 = []
for i in range(0, len(번호들), 50):
    for v in yt.videos().list(part="snippet,status", id=",".join(번호들[i:i+50])).execute()["items"]:
        if v["status"]["privacyStatus"] == "public":
            공개.append((v["snippet"]["publishedAt"], v["id"], v["snippet"]["title"]))
공개.sort(reverse=True)
공개 = 공개[:개수]

칸w, 칸h, 열 = 320, 180, 6
행 = (len(공개) + 열 - 1) // 열
벽 = Image.new("RGB", (칸w*열, 칸h*행), (24, 24, 24))
for i, (날, 번호, 제) in enumerate(공개):
    조각 = None
    for 종 in ("maxresdefault", "hqdefault", "mqdefault"):
        try:
            d = urllib.request.urlopen("https://i.ytimg.com/vi/%s/%s.jpg" % (번호, 종), timeout=20).read()
            조각 = Image.open(io.BytesIO(d)).convert("RGB"); break
        except Exception: continue
    if 조각 is None: continue
    조각 = 조각.resize((칸w, 칸h), Image.LANCZOS)
    벽.paste(조각, ((i % 열)*칸w, (i // 열)*칸h))
낼 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "썸네일벽보-%s.jpg" % 이름)
낼 = os.path.abspath(낼)
벽.save(낼, quality=88)
print("%s  (%d편, %s)" % (낼, len(공개), 공개[-1][0][:10] + " ~ " + 공개[0][0][:10]))
