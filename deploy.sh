#!/usr/bin/env bash
# 개발 서버 → 작업PC 배포: 소스 복사 → (형이 녹음 중이 아니면) 끄고 → 빌드 → 다시 실행
# 사용: ./deploy.sh            (작업PC user@pc-address, 프로젝트 C:\path\to\admiral)
set -euo pipefail
HOST=user@pc-address
DST='C:/path/to/admiral'
WIN='C:\path\to\admiral'
cd "$(dirname "$0")"

scp -q admiral.py pyproject.toml uv.lock build.bat setup.bat restart.ps1 install.ps1 version.txt admiral.ico "$HOST:$DST/"
ssh "$HOST" "$WIN\\setup.bat" | tail -1

# 녹음·변환 중이면 끝날 때까지 기다린다(쓰는 도중에 끄지 않기)
for _ in $(seq 1 60); do
  last=$(ssh "$HOST" "powershell -NoProfile -Command \"Get-ChildItem $WIN\\logs\\admiral-*.log | Sort-Object LastWriteTime | Select-Object -Last 1 | Get-Content -Encoding utf8 -Tail 1\"" | iconv -f cp949 -t utf-8 -c || true)
  case "$last" in *"녹음 시작"*|*"음량"*|*"변환"*) echo "사용 중, 대기: $last"; sleep 8;; *) break;; esac
done

ssh "$HOST" "taskkill /F /IM Admiral.exe >nul 2>&1 & $WIN\\build.bat" | tail -1
ssh "$HOST" "schtasks /run /tn admiral >nul"
echo "배포 완료 — 로그: $WIN\\logs"
