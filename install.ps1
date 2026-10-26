# Admiral 설치(처음 한 번): 윈도우 로그온 자동 실행 등록 + 바탕화면·시작 메뉴 바로가기 + 실행
# 사용: powershell -ExecutionPolicy Bypass -File install.ps1   (build.bat 으로 dist\Admiral\Admiral.exe 를 먼저 만든다)
$P = Split-Path -Parent $MyInvocation.MyCommand.Path
$exe = "$P\dist\Admiral\Admiral.exe"
if (-not (Test-Path $exe)) { throw "실행 파일 없음: $exe (build.bat 먼저)" }
schtasks /create /tn admiral /sc onlogon /ru $env:USERNAME /it /rl limited /tr "`"$exe`"" /f | Out-Null
$ws = New-Object -ComObject WScript.Shell
$desk = [Environment]::ExpandEnvironmentVariables((Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders').Desktop)
$menu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
foreach ($d in @($desk, $menu)) {
  $s = $ws.CreateShortcut((Join-Path $d 'Admiral.lnk'))
  $s.TargetPath = $exe; $s.WorkingDirectory = "$P\dist\Admiral"; $s.IconLocation = "$exe,0"
  $s.Description = "Admiral — 에이전트 함대 지휘 도구"; $s.Save()
}
schtasks /run /tn admiral | Out-Null
"설치 완료: $exe"
