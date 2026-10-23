# 윈도우 「열기」 파일 창에 경로를 밀어 넣고 엽니다.
#
#   powershell -File 파일창넣기.ps1 -경로 D:\bs1014.mp4
#
# 왜 이렇게 하나: 브라우저가 띄우는 네이티브 파일 창에는 클립보드도
# SendKeys 도 안 먹습니다. 창의 Edit 칸에 WM_SETTEXT 로 글자를 직접
# 넣고 WM_COMMAND/IDOK 을 보내 「열기」를 누른 것과 같게 만듭니다.
#
# 주의 1 — 경로는 **아스키**여야 합니다. 한글 경로는 하드링크로
#          D:\bs1014.mp4 처럼 영문 이름을 만들어 쓰세요.
# 주의 2 — 파일 창이 뜨려면 그 탭이 **앞에 나와 있어야** 합니다.
#          뒤에 있으면 창 자체가 안 열립니다.
param(
  [Parameter(Mandatory = $true)][string]$경로,
  [int]$기다릴초 = 15
)

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class FD {
  [DllImport("user32.dll", CharSet=CharSet.Auto)]
  public static extern IntPtr FindWindow(string cls, string name);
  [DllImport("user32.dll", CharSet=CharSet.Auto)]
  public static extern IntPtr FindWindowEx(IntPtr parent, IntPtr after, string cls, string name);
  [DllImport("user32.dll", CharSet=CharSet.Auto)]
  public static extern IntPtr SendMessage(IntPtr h, uint msg, IntPtr wp, string lp);
  [DllImport("user32.dll")]
  public static extern bool PostMessage(IntPtr h, uint msg, IntPtr wp, IntPtr lp);
  [DllImport("user32.dll")]
  public static extern bool SetForegroundWindow(IntPtr h);
}
"@

if (-not (Test-Path -LiteralPath $경로)) {
  Write-Output "그런 파일이 없습니다: $경로"; exit 1
}
if ($경로 -match '[^\x20-\x7E]') {
  Write-Output "경로에 한글이 있습니다. 아스키 이름으로 하드링크를 만들어 쓰세요: $경로"; exit 1
}

# 파일 창이 뜰 때까지 기다립니다 (클래스 이름은 #32770).
$창 = [IntPtr]::Zero
for ($i = 0; $i -lt ($기다릴초 * 4); $i++) {
  foreach ($이름 in @("열기", "Open", "업로드할 파일 선택", "파일 업로드")) {
    $ㅎ = [FD]::FindWindow("#32770", $이름)
    if ($ㅎ -ne [IntPtr]::Zero) { $창 = $ㅎ; break }
  }
  if ($창 -ne [IntPtr]::Zero) { break }
  Start-Sleep -Milliseconds 250
}
if ($창 -eq [IntPtr]::Zero) { Write-Output "파일 창을 못 찾았습니다 (no dialog)"; exit 2 }

[void][FD]::SetForegroundWindow($창)

# 파일 이름 칸: ComboBoxEx32 > ComboBox > Edit
$cbex = [FD]::FindWindowEx($창, [IntPtr]::Zero, "ComboBoxEx32", $null)
$cb   = [FD]::FindWindowEx($cbex, [IntPtr]::Zero, "ComboBox", $null)
$ed   = [FD]::FindWindowEx($cb,   [IntPtr]::Zero, "Edit", $null)
if ($ed -eq [IntPtr]::Zero) {
  $ed = [FD]::FindWindowEx($창, [IntPtr]::Zero, "Edit", $null)   # 옛 모양 창
}
if ($ed -eq [IntPtr]::Zero) { Write-Output "파일 이름 칸을 못 찾았습니다"; exit 3 }

[void][FD]::SendMessage($ed, 0x000C, [IntPtr]::Zero, $경로)      # WM_SETTEXT
Start-Sleep -Milliseconds 400
[void][FD]::PostMessage($창, 0x0111, [IntPtr]1, [IntPtr]::Zero)  # WM_COMMAND, IDOK
Start-Sleep -Milliseconds 800

$남았나 = [FD]::FindWindow("#32770", "열기")
if ($남았나 -eq [IntPtr]::Zero) { Write-Output "넣었습니다: $경로" }
else { Write-Output "창이 아직 열려 있습니다 — 경로를 다시 확인하세요" }
