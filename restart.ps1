Get-Process Admiral -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep 1
schtasks /run /tn admiral | Out-Null
