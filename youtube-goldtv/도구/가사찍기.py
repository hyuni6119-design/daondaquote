# -*- coding: utf-8 -*-
"""가사짓기.py 가 내놓은 json 을 02-가사 폴더의 md 파일로 찍어 냅니다.

세션이 바뀌며 사라져서 다시 만들었습니다. 기존 파일(071 등)과 같은
모양이 나오도록 맞췄습니다.
"""
import io, json, os, re, sys
sys.stdout.reconfigure(encoding="utf-8")

스타일 = ("A heartfelt trot ballad blending Korean traditional instruments with modern "
       "warmth, Gayageum arpeggios and haegeum lines weave through tender piano and "
       "subtle acoustic guitar, supported by a steady trot rhythm with brushed "
       "percussion, Warm male vocals carry Buddhist-inspired lyrics with sincerity, "
       "Strings and bamboo flute (daegeum) enrich the chorus, creating a hopeful, "
       "meditative atmosphere that gently expands while maintaining emotional intimacy")

판 = """# [{번호}] {제목} — 수노(Suno) 프롬프트

- **출처 경전**: {경전}
- **인용 원문**: {원문}
- **형식**: 트로트 발라드 + 국악
- **곡 성격**: {성격}
- **구절 등급**: {등급}

> 작성 규칙은 `{가이드}` 참고

---

## Song Title

```
{제목}
```

## Styles

```
{스타일}
```

## Lyrics — 수노 입력용 (이 아래 전체 복사)

```
{가사}
```

---

## 후렴 설계 메모

| 고정 | 1회차 | 2회차 | 3회차 |
|---|---|---|---|
| {후렴고정} | {후렴1} | {후렴2} | {후렴3} |

## 가사와 경전 연결

| 구간 | 근거 |
|---|---|
| Verse 1 | {연결1} |
| Verse 3 | {연결3} |

## 화면 하단 고정 표기

```
출처: {경전} — {원문}
가사는 경전의 뜻을 바탕으로 새로 쓴 창작물입니다.
```

## 확인 사항

- [x] 경전의 뜻을 왜곡하지 않았는가
- [x] 기존 번역본 문장을 전재한 곳이 없는가
- [x] 종파 중립인가
- [x] 기복 표현이 과하지 않은가
- [ ] 출처를 영상에 표기했는가
"""


def 파일이름(번호, 제목):
    """071-하루를그말로닫더라.md 처럼 띄어쓰기를 뺀 이름을 만듭니다."""
    맨 = re.sub(r"[^0-9A-Za-z가-힣]", "", 제목)
    return "%s-%s.md" % (번호, 맨)


def 찍기(길):
    자료 = json.load(io.open(길, encoding="utf-8"))
    둘곳, 가이드, 등급 = 자료["둘곳"], 자료["가이드"], 자료["등급"]
    os.makedirs(둘곳, exist_ok=True)
    for 곡 in 자료["곡들"]:
        이름 = 파일이름(곡["번호"], 곡["제목"])
        몸 = 판.format(스타일=스타일, 가이드=가이드, 등급=등급, **곡)
        io.open(os.path.join(둘곳, 이름), "w", encoding="utf-8").write(몸)
        print("찍음:", 이름)


if __name__ == "__main__":
    for 길 in sys.argv[1:]:
        찍기(길)
