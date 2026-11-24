# 화면 캡처 프로그램

## 실행
```
pip install pillow
python capture.py
```
Windows에서는 `run.bat`을 더블클릭해도 됩니다.

## 기능
- **전체 화면** (F1): 모든 모니터를 한 번에 캡처
- **영역 선택** (F2): 화면이 어두워지면 마우스로 드래그, ESC로 취소
- **지연(초)**: 0~10초 뒤에 캡처 (메뉴 등을 열어둔 상태로 찍을 때)
- **미리보기 창**: 저장(Ctrl+S, PNG/JPG/BMP), 빠른 저장(`사진\Captures` 폴더에 자동 이름), 클립보드 복사(Ctrl+C, Windows)

## exe로 만들기 (선택)
```
pip install pyinstaller
pyinstaller --onefile --noconsole capture.py
```
`dist\capture.exe`가 생성됩니다.
