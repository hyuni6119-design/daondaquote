' 다온다 견적서 - 공유폴더를 윈도우 탐색기로 여는 도우미
' 브라우저가 daonda:... 주소를 넘겨주면 그 폴더를 탐색기로 엽니다.
Option Explicit

Dim args, raw, payload, target, sh

Set args = WScript.Arguments
If args.Count = 0 Then
  MsgBox "열 폴더 정보가 전달되지 않았습니다.", 48, "다온다 폴더 열기"
  WScript.Quit
End If

raw = args(0)
payload = StripScheme(raw)

If Len(payload) = 0 Then
  MsgBox "열 폴더 정보가 비어 있습니다.", 48, "다온다 폴더 열기"
  WScript.Quit
End If

On Error Resume Next
target = Base64ToUtf8(FromBase64Url(payload))
If Err.Number <> 0 Then
  MsgBox "폴더 정보를 해석하지 못했습니다." & vbCrLf & vbCrLf & raw, 48, "다온다 폴더 열기"
  WScript.Quit
End If
On Error GoTo 0

If Len(target) = 0 Then
  MsgBox "폴더 경로가 비어 있습니다.", 48, "다온다 폴더 열기"
  WScript.Quit
End If

Set sh = CreateObject("WScript.Shell")
sh.Run "explorer.exe """ & target & """", 1, False

' ---------- 보조 함수 ----------

Function StripScheme(s)
  Dim p
  p = s
  If InStr(1, p, "daonda:", 1) = 1 Then p = Mid(p, 8)
  Do While Len(p) > 0 And Left(p, 1) = "/"
    p = Mid(p, 2)
  Loop
  Do While Len(p) > 0 And Right(p, 1) = "/"
    p = Left(p, Len(p) - 1)
  Loop
  StripScheme = p
End Function

Function FromBase64Url(s)
  Dim p
  p = Replace(Replace(s, "-", "+"), "_", "/")
  Do While (Len(p) Mod 4) <> 0
    p = p & "="
  Loop
  FromBase64Url = p
End Function

Function Base64ToUtf8(b64)
  Dim xml, node, stream
  Set xml = CreateObject("MSXML2.DOMDocument.6.0")
  Set node = xml.createElement("b64")
  node.dataType = "bin.base64"
  node.text = b64
  Set stream = CreateObject("ADODB.Stream")
  stream.Type = 1
  stream.Open
  stream.Write node.nodeTypedValue
  stream.Position = 0
  stream.Type = 2
  stream.Charset = "utf-8"
  Base64ToUtf8 = stream.ReadText
  stream.Close
End Function
