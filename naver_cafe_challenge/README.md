# 네이버카페 챌린지 자동업로드

매일 정해진 시간에 네이버카페 게시판에 **챌린지 인증글**을 자동으로 올리는 프로그램입니다.

- 제목·본문 템플릿에 **날짜 / N일차**가 자동으로 들어갑니다
- **AI(Claude)** 가 매일 다른 응원 문구를 써 줍니다 (선택)
- `photos/` 폴더의 **인증 사진**을 자동 첨부합니다 (선택)
- 기본은 **임시등록만** — 발행은 내가 확인하고 직접 누름 (`post.mode: publish` 로 바꾸면 바로 발행)
- 하루에 한 번만 올라가도록 **중복 방지**, 실패하면 **화면 캡처 + 로그** 저장

> ⚠️ **주의**: 브라우저 자동화 방식이라 네이버 화면이 바뀌면 동작이 멈출 수 있고,
> 네이버가 자동화를 감지하면 캡차·이용 제한이 걸릴 수 있습니다.
> 카페 운영 규칙(도배 금지 등)을 꼭 확인하고, 본인 계정으로 하루 1회 정도만 사용하세요.

---

## 1. 설치 (처음 1번)

[Python 3.10 이상](https://www.python.org/downloads/)과 크롬 브라우저가 필요합니다.
(윈도우에서 Python 설치 시 **"Add python.exe to PATH"** 체크)

이 폴더에서 터미널(명령 프롬프트)을 열고:

```bash
python -m venv .venv
```

윈도우:

```bash
.venv\Scripts\activate
```

맥:

```bash
source .venv/bin/activate
```

```bash
pip install -r requirements.txt
```

크롬이 없으면 내장 브라우저를 설치하세요 (그리고 config.yaml 의 `channel` 을 `""` 로):

```bash
playwright install chromium
```

## 2. 설정

`config.example.yaml` 을 복사해서 `config.yaml` 로 이름을 바꾸고 수정합니다.

| 항목 | 설명 |
|---|---|
| `cafe.url_name` | 카페 주소 `cafe.naver.com/여기` 부분 |
| `cafe.menu_id` | 올릴 게시판 번호. 게시판 클릭 시 주소의 `menuid=숫자` 또는 `/menus/숫자` |
| `challenge.start_date` | 1일차 날짜 |
| `challenge.total_days` | 총 일수 (지나면 자동으로 멈춤) |
| `post.mode` | `draft` = 임시등록만 (기본) / `publish` = 바로 발행 |
| `post.title_template` / `body_template` | 글 틀. `{day}`, `{date_kr}`, `{ai_text}` 등 치환 |
| `ai.enabled` | AI 문구 사용 여부 |
| `photos.enabled` | 사진 첨부 여부 |

### AI 문구 사용 시

[Anthropic Console](https://console.anthropic.com/)에서 API 키를 발급받아 환경변수로 등록하세요.

윈도우 (한 번 실행 후 터미널 재시작):

```bash
setx ANTHROPIC_API_KEY "sk-ant-..."
```

맥 (`~/.zshrc` 에 추가):

```bash
echo 'export ANTHROPIC_API_KEY="sk-ant-..."' >> ~/.zshrc
```

키가 없거나 오류가 나면 `ai.fallback_text` 문구로 대신 올라갑니다.

### 사진

`photos/` 폴더에 사진을 넣어 두세요.
파일명이 회차 번호로 시작하면 그 날에 사용됩니다 (예: `5.jpg` → 5일차). 없으면 가장 오래된 사진부터.
올린 사진은 `photos/used/` 로 옮겨집니다.

## 3. 로그인 (처음 1번)

```bash
python main.py login
```

브라우저 창이 뜨면 **직접** 네이버에 로그인하세요 (**로그인 상태 유지** 체크).
아이디/비밀번호는 프로그램에 저장하지 않고, 로그인 상태만 `browser_profile/` 폴더에 남습니다.
이 폴더는 다른 사람에게 절대 공유하지 마세요.

## 4. 테스트

오늘 올라갈 글 미리보기 (브라우저 안 열림):

```bash
python main.py preview
```

글쓰기 화면에 입력까지만 하고 **등록은 안 누르는** 연습 모드:

```bash
python main.py post --dry-run
```

실제로 한 번 임시등록 해 보기:

```bash
python main.py post --no-delay
```

카페 글쓰기 화면 상단의 **임시등록 (숫자)** 를 눌러 저장된 글을 불러온 뒤, 확인하고 **등록** 을 누르면 발행됩니다.

임시등록 없이 바로 발행하려면:

```bash
python main.py post --publish
```

## 5. 매일 자동 실행

### 윈도우 (작업 스케줄러)

매일 오전 7시에 실행 — 이 폴더에서 아래를 실행 (경로는 실제 위치로):

```bash
schtasks /create /tn "NaverCafeChallenge" /tr "\"C:\경로\naver_cafe_challenge\run_daily.bat\"" /sc daily /st 07:00
```

- PC가 켜져 있고 **로그인된 상태**여야 실행됩니다.
- 작업 스케줄러 앱 → 작업 속성 → 조건 → "작업을 실행하기 위해 절전 모드 종료" 를 체크하면 절전 중에도 깨어나 실행합니다.
- 삭제: `schtasks /delete /tn "NaverCafeChallenge" /f`

### 맥 (cron)

```bash
crontab -e
```

아래 줄 추가 (매일 오전 7시):

```
0 7 * * * /경로/naver_cafe_challenge/run_daily.sh
```

`schedule.random_delay_minutes` 만큼 랜덤하게 기다렸다가 올리므로 매일 정확히 같은 시각에 올라가지 않습니다.

## 6. 기타 명령

특정 날짜로 올리기 / 이미 올렸어도 다시 올리기:

```bash
python main.py post --date 2026-12-05 --force
```

## 문제 해결

| 증상 | 해결 |
|---|---|
| `로그인되어 있지 않습니다` | `python main.py login` 다시 실행 |
| `'title' 요소를 찾지 못했습니다` 등 | 네이버 화면이 바뀐 것. `logs/` 의 캡처를 보고 `uploader.py` 맨 위 `SELECTORS` 수정 |
| 카페 ID를 못 찾음 | 카페 아무 글 주소의 `/cafes/숫자/` 숫자를 `cafe.club_id` 에 직접 입력 |
| 캡차가 뜸 | `headless: false` 로 두고, 업로드 빈도를 줄이세요 |
| 임시등록 버튼을 못 찾음 | `uploader.py` 의 `SELECTORS["draft"]` 에 실제 버튼 글자 추가 |
| 올린 기록 | `state.json`, 로그는 `logs/challenge.log` |

## 파일 구성

```
main.py          명령 실행 (login / preview / post)
content.py       회차 계산, 제목·본문 생성, AI 문구, 사진 고르기
uploader.py      브라우저로 카페 글쓰기
config.yaml      내 설정 (직접 만들기)
run_daily.bat    윈도우 예약 실행용
run_daily.sh     맥/리눅스 예약 실행용
```
