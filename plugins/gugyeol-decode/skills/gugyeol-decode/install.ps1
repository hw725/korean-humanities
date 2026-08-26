<#
.SYNOPSIS
    gugyeol-decode 원클릭 설치 (Windows)

.USAGE
    iwr -useb https://raw.githubusercontent.com/hw725/gugyeol-decode/master/install.ps1 | iex

    또는 이미 clone한 경우:
    .\install.ps1
#>
$ErrorActionPreference = "Stop"
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$SkillsDir = $env:CLAUDE_SKILLS_DIR
if (-not $SkillsDir) { $SkillsDir = Join-Path $env:USERPROFILE ".claude\skills" }
$Target = Join-Path $SkillsDir "gugyeol-decode"
$RepoUrl = "https://github.com/hw725/gugyeol-decode.git"

Write-Host "===================================" -ForegroundColor Cyan
Write-Host " gugyeol-decode 원클릭 설치" -ForegroundColor Cyan
Write-Host "===================================" -ForegroundColor Cyan

# 1. Python 확인
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
if (-not $py) {
    Write-Host "[ERROR] Python 미설치. https://python.org 에서 Python 3.9+ 설치 후 재시도." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Python: $($py.Source)" -ForegroundColor Green

# 2. clone
if (-not (Test-Path $SkillsDir)) { New-Item -ItemType Directory -Force -Path $SkillsDir | Out-Null }

if (Test-Path (Join-Path $Target ".git")) {
    Write-Host "[SKIP] 이미 설치되어 있음 ($Target). 업데이트: cd $Target; git pull" -ForegroundColor Yellow
} elseif (Test-Path $Target) {
    Write-Host "[ERROR] $Target 가 이미 존재. 수동으로 정리 후 재시도." -ForegroundColor Red
    exit 1
} else {
    Write-Host "[>] git clone $RepoUrl 으로 $Target" -ForegroundColor Cyan
    git clone --depth 1 $RepoUrl $Target
}

# 3. setup
Set-Location $Target
Write-Host "[>] python setup.py (의존성·매핑 데이터 자동 다운로드, 5-10분)" -ForegroundColor Cyan
& $py.Source setup.py

Write-Host ""
Write-Host "===================================" -ForegroundColor Green
Write-Host " 설치 완료" -ForegroundColor Green
Write-Host "===================================" -ForegroundColor Green
Write-Host " Claude Code 사용자: 그냥 자연어로 호출"
Write-Host "   '이 PDF에서 옛한글이 깨져 나와 — 풀어줘'"
Write-Host ""
Write-Host " CLI 사용자:"
Write-Host "   python $Target\scripts\decode.py <파일.pdf|.hwpx|.hwp>"
