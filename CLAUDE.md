# 저장소 안내

두 가지 작업이 한 저장소에 들어 있습니다. 서로 무관하니 섞지 마세요.

| 경로 | 내용 |
|---|---|
| `index.html` | 다온다자동차유리 보험사 견적서 자동생성기 (단일 HTML 파일) |
| `youtube-goldtv/` | 골드TV 유튜브 채널 작업 공간 |

## 골드TV 작업을 할 때

먼저 `youtube-goldtv/README.md` 를 읽으세요. 폴더 구성과 작업 방식이 거기 있습니다.

중요한 문서:
- `youtube-goldtv/00-채널정보.md` — 채널 컨셉, 타깃, 톤앤매너. 모든 가사의 기준
- `youtube-goldtv/수노-프롬프트-가이드.md` — 곡 만드는 형식
- `youtube-goldtv/유명-경전구절-모음.md` — 가사에 쓸 수 있는 구절 (1군에서만 고를 것)
- `youtube-goldtv/도구/사용법.md` — 자동화 스크립트 사용법

## 두 세션이 함께 일하는 방식

- **클라우드 세션**(웹·휴대폰)이 `youtube-goldtv/지시사항.md` 에 할 일을 씁니다
- **로컬 세션**(파워셸·VS Code)이 `/작업` 으로 그것을 실행하고
  `youtube-goldtv/작업기록.md` 에 결과를 씁니다
- 양쪽 다 `claude/fervent-mendel-124aee` 브랜치를 씁니다

## 절대 커밋하지 않는 것

```
youtube-goldtv/도구/api키.json
youtube-goldtv/도구/client_secret.json
youtube-goldtv/도구/인증토큰.json
```

음원(mp3), 영상(mp4), 이미지 원본도 커밋하지 않습니다.
