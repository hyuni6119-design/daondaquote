"""Playwright 로 네이버카페에 글을 올리는 부분.

네이버 화면 구조가 바뀌면 아래 SELECTORS 의 후보만 고치면 됩니다.
각 항목은 위에서부터 순서대로 시도합니다.
"""
from __future__ import annotations

import logging
import random
import re
import time
from pathlib import Path

from playwright.sync_api import BrowserContext, Page, TimeoutError as PWTimeout, sync_playwright

from content import Post

log = logging.getLogger("challenge")

SELECTORS = {
    "title": [
        "textarea.textarea_input",
        "textarea[placeholder*='제목']",
        "input[placeholder*='제목']",
    ],
    "body": [
        ".se-content [contenteditable='true']",
        ".se-component-content .se-text-paragraph",
        ".se-placeholder",
        "[contenteditable='true']",
    ],
    "image_button": [
        "button.se-image-toolbar-button",
        "button[data-name='image']",
        "button[data-log='dot.img']",
        "button:has-text('사진')",
    ],
    "submit": [
        "a.BaseButton:has-text('등록')",
        "button.BaseButton:has-text('등록')",
        "button:has-text('등록')",
        "a:has-text('등록')",
    ],
}

LOGIN_URL = "https://nid.naver.com/nidlogin.login?url=https%3A%2F%2Fcafe.naver.com"


def _human_pause(a: float = 0.6, b: float = 1.6) -> None:
    time.sleep(random.uniform(a, b))


class CafeUploader:
    def __init__(self, cfg: dict, base_dir: Path, headless: bool | None = None):
        self.cfg = cfg
        self.base_dir = base_dir
        b = cfg.get("browser") or {}
        self.headless = b.get("headless", False) if headless is None else headless
        self.profile_dir = (base_dir / b.get("profile_dir", "browser_profile")).resolve()
        self.typing_delay = int(b.get("typing_delay_ms", 40))
        self.log_dir = base_dir / "logs"
        self.log_dir.mkdir(exist_ok=True)
        self._pw = None
        self.ctx: BrowserContext | None = None
        self.page: Page | None = None

    # ── 브라우저 열고 닫기 ────────────────────────────
    def __enter__(self):
        self._pw = sync_playwright().start()
        b = self.cfg.get("browser") or {}
        extra = {}
        if b.get("channel"):
            extra["channel"] = b["channel"]  # 예: "chrome" → PC에 설치된 크롬 사용
        if b.get("executable_path"):
            extra["executable_path"] = b["executable_path"]
        self.ctx = self._pw.chromium.launch_persistent_context(
            str(self.profile_dir),
            **extra,
            headless=self.headless,
            locale="ko-KR",
            viewport={"width": 1280, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
        self.page.set_default_timeout(20_000)
        return self

    def __exit__(self, *exc):
        try:
            if self.ctx:
                self.ctx.close()
        finally:
            if self._pw:
                self._pw.stop()

    # ── 로그인 ──────────────────────────────────────
    def is_logged_in(self) -> bool:
        cookies = self.ctx.cookies("https://naver.com")
        return any(c["name"] == "NID_AUT" for c in cookies)

    def interactive_login(self) -> bool:
        """브라우저 창에서 사용자가 직접 로그인 (캡차·2단계 인증 대응)."""
        self.page.goto(LOGIN_URL)
        print("\n열린 브라우저 창에서 네이버에 직접 로그인하세요.")
        print("  · '로그인 상태 유지'를 체크하면 다음부터 자동으로 로그인됩니다.")
        print("  · 로그인이 끝나면 자동으로 감지합니다. (최대 5분 대기)\n")
        for _ in range(300):
            if self.is_logged_in():
                print("✅ 로그인 확인! 이제 창을 닫아도 됩니다.")
                time.sleep(2)
                return True
            time.sleep(1)
        print("❌ 5분 안에 로그인이 확인되지 않았습니다.")
        return False

    # ── 카페 정보 ───────────────────────────────────
    def resolve_club_id(self) -> str:
        cafe = self.cfg["cafe"]
        if str(cafe.get("club_id") or "").strip():
            return str(cafe["club_id"]).strip()
        url_name = cafe["url_name"]
        self.page.goto(f"https://cafe.naver.com/{url_name}")
        self.page.wait_for_load_state("domcontentloaded")
        _human_pause()
        html = self.page.content()
        for f in self.page.frames:
            try:
                html += f.content()
            except Exception:
                pass
        for pat in (r"g_sClubId\s*=\s*\"?(\d+)", r"clubid=(\d+)", r"/cafes/(\d+)", r"\"cafeId\"\s*:\s*(\d+)"):
            m = re.search(pat, html, re.IGNORECASE)
            if m:
                log.info("카페 ID 자동 확인: %s", m.group(1))
                return m.group(1)
        raise RuntimeError("카페 숫자 ID(club_id)를 찾지 못했습니다. config.yaml 에 직접 적어 주세요.")

    # ── 요소 찾기 (iframe 포함) ──────────────────────
    def _find(self, key: str, timeout_s: float = 20):
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            for frame in self.page.frames:  # 메인 화면 + 모든 iframe
                for sel in SELECTORS[key]:
                    try:
                        loc = frame.locator(sel).first
                        if loc.count() and loc.is_visible():
                            return loc
                    except Exception:
                        continue
            time.sleep(0.5)
        raise RuntimeError(f"화면에서 '{key}' 요소를 찾지 못했습니다. (uploader.py SELECTORS 확인)")

    def _screenshot(self, name: str) -> Path:
        path = self.log_dir / f"{time.strftime('%Y%m%d_%H%M%S')}_{name}.png"
        try:
            self.page.screenshot(path=str(path), full_page=True)
        except Exception:
            pass
        return path

    # ── 글쓰기 ──────────────────────────────────────
    def _type_multiline(self, text: str) -> None:
        kb = self.page.keyboard
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if line:
                # 한글은 insert_text 가 안정적. 짧게 나눠 사람처럼 입력.
                for chunk in re.findall(r".{1,8}", line):
                    kb.insert_text(chunk)
                    time.sleep(self.typing_delay / 1000 * len(chunk))
            if i < len(lines) - 1:
                kb.press("Enter")
                time.sleep(0.05)

    def _attach_photos(self, photos: list[Path]) -> None:
        for p in photos:
            log.info("사진 첨부: %s", p.name)
            btn = self._find("image_button")
            with self.page.expect_file_chooser(timeout=15_000) as fc:
                btn.click()
            fc.value.set_files(str(p))
            # 업로드 완료 대기 (이미지 컴포넌트 등장)
            try:
                self.page.locator(".se-image, .se-module-image, img.se-image-resource").last.wait_for(timeout=30_000)
            except PWTimeout:
                log.warning("사진 업로드 완료를 확인하지 못했습니다: %s", p.name)
            _human_pause(1.0, 2.0)

    def publish(self, post: Post, dry_run: bool = False) -> str | None:
        if not self.is_logged_in():
            raise RuntimeError("로그인되어 있지 않습니다. 먼저 `python main.py login` 을 실행하세요.")

        club_id = self.resolve_club_id()
        menu_id = self.cfg["cafe"]["menu_id"]
        write_url = f"https://cafe.naver.com/ca-fe/cafes/{club_id}/articles/write?boardType=L&menuId={menu_id}"
        log.info("글쓰기 화면 열기: %s", write_url)
        self.page.goto(write_url)
        self.page.wait_for_load_state("domcontentloaded")
        _human_pause(1.5, 3.0)

        try:
            title = self._find("title", 30)
            title.click()
            _human_pause(0.3, 0.8)
            title.fill("")
            self._type_multiline(post.title)
            _human_pause()

            body = self._find("body")
            body.click()
            _human_pause(0.3, 0.8)
            self._type_multiline(post.body)
            _human_pause()

            if post.photos:
                # 사진은 본문 맨 끝에 붙임
                self.page.keyboard.press("Control+End")
                self.page.keyboard.press("Enter")
                self._attach_photos(post.photos)

            shot = self._screenshot("before_submit")
            if dry_run:
                log.info("[연습 모드] 등록 버튼은 누르지 않았습니다. 화면 캡처: %s", shot)
                if not self.headless:
                    input("브라우저에서 내용을 확인한 뒤 Enter 를 누르면 종료합니다 (글은 저장되지 않음)...")
                return None

            before = self.page.url
            self._find("submit").click()
            log.info("등록 버튼 클릭, 완료 대기 중...")
            try:
                self.page.wait_for_url(lambda u: u != before and "/write" not in u, timeout=30_000)
            except PWTimeout:
                path = self._screenshot("submit_timeout")
                raise RuntimeError(f"등록 후 글 페이지로 이동하지 않았습니다. 화면 캡처: {path}")
            _human_pause()
            log.info("✅ 업로드 완료: %s", self.page.url)
            return self.page.url
        except Exception:
            path = self._screenshot("error")
            log.error("업로드 중 오류. 화면 캡처: %s", path)
            raise
