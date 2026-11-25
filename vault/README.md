# 내 정보 금고 — 내 서버에 올리는 방법

메일·비밀번호·애드센스·전자책·강의·카페 계정을 한곳에 보관하는 개인 사이트입니다.

- 마스터 비밀번호로 **브라우저에서 암호화한 뒤** 서버에 저장합니다. 서버에는 열 수 없는 암호문만 남아요.
- 휴대폰과 컴퓨터에서 같은 주소로 열면 같은 내용이 보입니다.
- 저장할 때마다 서버에 이전 버전 50개가 자동으로 남습니다 (`/data/backups`).
- 비밀번호를 15분 안에 10번 틀리면 15분 동안 잠깁니다.

> 마스터 비밀번호를 잊으면 아무도 복구할 수 없습니다. 종이에 적어 안전한 곳에 보관하세요.

---

## 1단계. 서버 빌리기 (Hetzner 기준, 월 5~7천 원)

1. https://www.hetzner.com/cloud 에서 가입하고 결제 수단을 등록합니다.
2. **Add Server**를 누르고 아래처럼 고릅니다.
   - Location: 아무 곳 (한국에서 가까운 곳은 Singapore가 있으면 그것)
   - Image: **Ubuntu 24.04**
   - Type: **CX22** (가장 저렴한 것도 충분해요)
   - SSH key가 어렵다면 비워 두세요. 그러면 root 비밀번호가 메일로 옵니다.
3. 만들어지면 서버 **IP 주소**(예: `168.119.152.95`)를 적어 둡니다.

## 2단계. Coolify 설치 (명령어 한 줄)

컴퓨터에서 터미널(윈도우는 PowerShell)을 열고 서버에 접속합니다. `IP주소` 자리에 내 서버 IP를 넣으세요.

```bash
ssh root@IP주소
```

접속되면 아래 한 줄을 붙여넣습니다. 5분쯤 걸립니다.

```bash
curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash
```

끝나면 브라우저에서 `http://IP주소:8000` 을 열고 관리자 계정을 만듭니다.
**이 관리자 계정이 서버 전체의 열쇠입니다.** 길고 어려운 비밀번호를 쓰세요.

## 3단계. 금고 올리기

1. Coolify 화면에서 **Projects → Add → New Resource → Public Repository**(저장소가 비공개라면 **Private Repository (with GitHub App)**)를 고릅니다.
2. 저장소 주소: `https://github.com/hyuni6119-design/daondaquote`
3. Branch: 이 금고 코드가 들어 있는 브랜치 (main에 합쳤다면 `main`)
4. Build Pack: **Dockerfile**
5. Base Directory: **`/vault`**
6. Ports Exposes: **3000**
7. Domains 칸에 `https://vault.IP주소를-점-대신-대시로.sslip.io` 를 넣습니다.
   예: IP가 `168.119.152.95`라면 `https://vault.168-119-152-95.sslip.io`
8. **Storages(Persistent Storage)** 메뉴에서 저장 공간을 추가합니다.
   - Destination Path: **`/data`**
   - 이걸 빼먹으면 다시 배포할 때 금고 내용이 사라집니다. 꼭 넣으세요.
9. **Deploy**를 누릅니다. 1~2분 뒤 위 주소로 들어가면 금고가 열립니다.

## 4단계. 바로 할 일

- 주소에 처음 들어간 사람이 금고 주인이 됩니다. **배포하자마자 바로 들어가서 마스터 비밀번호를 정하세요.**
- 주소 앞이 반드시 `https://` 여야 합니다. `http://`로 열면 금고가 작동하지 않아요.
- 가끔 화면 아래 **암호화된 백업 파일 받기**를 눌러 내 컴퓨터에도 백업해 두세요.

## 서버 안전하게 쓰기

- Coolify 관리자 비밀번호와 서버 root 비밀번호는 금고 비밀번호와 **다르게** 하세요.
- Hetzner 계정에 2단계 인증을 켜세요.
- 서버를 지우면 금고도 사라집니다. 백업 파일을 꼭 따로 보관하세요.

---

## 개발자용 메모

- 외부 패키지 없음. `node server.js`로 실행 (`PORT`, `DATA_DIR` 환경 변수).
- 암호화: PBKDF2-SHA256(600,000회) → 512비트. 앞 256비트는 AES-GCM 열쇠(브라우저에만), 뒤 256비트는 서버 인증 토큰(서버는 SHA-256 해시만 저장).
- API: `GET /api/meta`, `POST /api/setup`(금고가 없을 때만), `GET|PUT /api/vault`, `PUT /api/password`. PUT은 `version`이 다르면 409와 최신본을 돌려주고, 브라우저가 합친 뒤 다시 저장합니다.
