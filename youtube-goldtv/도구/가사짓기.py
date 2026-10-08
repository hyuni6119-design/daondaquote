# -*- coding: utf-8 -*-
"""26줄짜리 노랫말에 수노용 구간 표시를 붙여 48줄로 만듭니다.

전에는 scratchpad 에 두었다가 세션이 바뀔 때마다 사라졌습니다. 두 번
잃어버렸으므로 이제 저장소 안에 둡니다. 짝인 `가사찍기.py` 가 여기서
나온 json 을 02-가사 폴더의 md 로 찍어 냅니다.

쓰는 법 — 곡마다 `줄` 에 **딱 26줄**을 넣습니다.

    4줄  Verse 1
    4줄  Chorus 1
    4줄  Verse 2
    4줄  Chorus 2
    4줄  Verse 3
    4줄  Chorus 3
    2줄  Outro

    from 가사짓기 import 만들기
    만들기(곡들, 둘곳=r"...\02-가사", 낼곳=r"...\황금21.json")
"""
import io
import json

구간 = [
    ("[Verse 1 - Soft, reflective tone]", 4),
    ("[Chorus - Warm trot ballad, hopeful male vocal]", 4),
    ("[Verse 2 - Emotional rise with haegeum line]", 4),
    ("[Chorus - Enriched with strings and harmonies]", 4),
    ("__다리__", 0),
    ("[Verse 3 - Quiet, almost spoken]", 4),
    ("[Chorus - Final, climactic delivery with full arrangement]", 4),
    ("[Outro - Whisper-like male vocal, fading instrumental]", 2),
]
머리 = ("[Intro: Gentle gayageum plucking with soft piano chords, daegeum long "
      "breath, temple wind chime, light trot brush rhythm]")
다리 = ("[Bridge - Instrumental meditation]\n"
      "[Haegeum solo interwoven with daegeum echo, gayageum tremolo layered "
      "with soft piano]")
끝 = ("[Outro Instrumental: Gayageum last pluck, daegeum fading breath, "
     "temple bell echo dissolve]")


def 엮기(줄글):
    """26줄 노랫말 → 48줄 수노 가사."""
    줄들 = [ㄱ.strip() for ㄱ in 줄글.strip().splitlines() if ㄱ.strip()]
    if len(줄들) != 26:
        raise ValueError("노랫말은 26줄이어야 합니다 (지금 %d줄)" % len(줄들))
    덩이, 남은 = ["[start]", "", 머리, ""], list(줄들)
    for 이름, 수 in 구간:
        if 이름 == "__다리__":
            덩이 += [다리, ""]
            continue
        덩이.append(이름)
        덩이 += 남은[:수]
        남은 = 남은[수:]
        덩이.append("")
    덩이.append(끝)
    return "\n".join(덩이)


def 만들기(곡들, 둘곳, 낼곳, 가이드="../수노-프롬프트-가이드.md",
        등급="1군(유명 구절, 각도 바꿈)"):
    """곡 목록을 받아 가사찍기.py 가 읽는 json 으로 떨굽니다."""
    나옴 = []
    for 곡 in 곡들:
        한 = {ㅋ: ㄱ for ㅋ, ㄱ in 곡.items() if ㅋ != "줄"}
        한["가사"] = 엮기(곡["줄"])
        줄수 = len(한["가사"].splitlines())
        if 줄수 != 48:
            raise ValueError("%s: 48줄이 아니라 %d줄입니다" % (곡["번호"], 줄수))
        나옴.append(한)
    자료 = {"둘곳": 둘곳, "가이드": 가이드, "등급": 등급, "곡들": 나옴}
    io.open(낼곳, "w", encoding="utf-8").write(
        json.dumps(자료, ensure_ascii=False, indent=1))
    print("%d곡을 %s 에 적었습니다" % (len(나옴), 낼곳))
    return 낼곳
