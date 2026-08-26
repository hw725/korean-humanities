<#
.SYNOPSIS
    터미널·파이썬·git의 한글 깨짐 뿌리를 사용자 수준에서 영구 차단한다.
.USAGE
    powershell -ExecutionPolicy Bypass -File scripts/setup-terminal-utf8.ps1
    powershell -ExecutionPolicy Bypass -File scripts/setup-terminal-utf8.ps1 -Check
.NOTES
    korean-humanities 슈트 CJK Text Handling Contract §4의 실행체.
    시스템 ACP(레지스트리 Beta UTF-8)는 건드리지 않는다 — HWP 등 구형 한국어
    앱을 깨뜨릴 수 있어서다. 대신 프로세스 수준 기본값 3곳을 고정한다:
      1. PYTHONUTF8=1 (사용자 환경변수) — python open()의 기본 인코딩이 cp949에서
         utf-8이 된다. 코드의 encoding= 명시 의무(계약 §1)는 그대로 유지 —
         이 변수는 이중 방어선이지 명시의 대체가 아니다.
      2. PowerShell 프로필(5.1 + 7) — 콘솔 입출력 인코딩 UTF-8 + chcp 65001.
      3. git core.quotepath=false — 한글 파일명이 \354... 이스케이프로 깨지는 것 차단.
    idempotent — 재실행해도 중복 블록을 만들지 않는다.
#>

param(
    [switch]$Check
)

$ErrorActionPreference = "Stop"
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Write-OK($msg) { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  [!] $msg" -ForegroundColor Yellow }

$MARK_BEGIN = "# >>> korean-humanities utf8 (setup-terminal-utf8.ps1) >>>"
$MARK_END = "# <<< korean-humanities utf8 <<<"
$PROFILE_BLOCK = @"
$MARK_BEGIN
# 한글 깨짐 차단 — CJK Text Handling Contract §4. 수정은 원본 스크립트에서.
`$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
try { [Console]::InputEncoding = [System.Text.Encoding]::UTF8 } catch {}
`$null = chcp 65001
$MARK_END
"@

Write-Host "=== terminal UTF-8 setup ===" -ForegroundColor White

# --- 1. PYTHONUTF8 사용자 환경변수 -------------------------------------------
$cur = [Environment]::GetEnvironmentVariable("PYTHONUTF8", "User")
if ($cur -eq "1") {
    Write-OK "PYTHONUTF8=1 (already set, user scope)"
} elseif ($Check) {
    Write-Warn "Would set user env PYTHONUTF8=1 (current: '$cur')"
} else {
    [Environment]::SetEnvironmentVariable("PYTHONUTF8", "1", "User")
    Write-OK "Set user env PYTHONUTF8=1 (새 프로세스부터 적용)"
}

# --- 2. PowerShell 프로필 (5.1 + 7, 존재하는 쪽만) ----------------------------
$profiles = @(
    (Join-Path ([Environment]::GetFolderPath("MyDocuments")) "WindowsPowerShell\Microsoft.PowerShell_profile.ps1"),
    (Join-Path ([Environment]::GetFolderPath("MyDocuments")) "PowerShell\Microsoft.PowerShell_profile.ps1")
)
foreach ($pf in $profiles) {
    $label = if ($pf -match "WindowsPowerShell") { "PS 5.1" } else { "PS 7" }
    if (-not (Test-Path -LiteralPath $pf)) {
        if ($Check) { Write-Warn "Would create $label profile with UTF-8 block: $pf"; continue }
        New-Item -ItemType File -Force -Path $pf | Out-Null
    }
    $content = Get-Content -Raw -Encoding UTF8 -LiteralPath $pf
    if ($null -eq $content) { $content = "" }
    if ($content.Contains($MARK_BEGIN)) {
        Write-OK "$label profile: UTF-8 block already present"
        continue
    }
    if ($Check) {
        Write-Warn "Would append UTF-8 block to $label profile"
        continue
    }
    # BOM 있는 UTF-8로 저장 — PS 5.1이 BOM 없는 UTF-8 프로필을 ANSI로 읽는 함정 방지
    $newContent = $content.TrimEnd() + "`r`n`r`n" + $PROFILE_BLOCK + "`r`n"
    [System.IO.File]::WriteAllText($pf, $newContent, (New-Object System.Text.UTF8Encoding($true)))
    Write-OK "$label profile: UTF-8 block appended"
}

# --- 3. git 한글 파일명 표시 --------------------------------------------------
$qp = git config --global core.quotepath 2>$null
if ($qp -eq "false") {
    Write-OK "git core.quotepath=false (already)"
} elseif ($Check) {
    Write-Warn "Would set git config --global core.quotepath false (current: '$qp')"
} else {
    git config --global core.quotepath false
    Write-OK "git core.quotepath=false"
}

Write-Host ""
Write-Host "적용 범위: 새로 여는 터미널·새 프로세스부터. 시스템 ACP(cp949)는 의도적으로 유지" -ForegroundColor Gray
Write-Host "권장 터미널 폰트(수동 설정): Sarasa Fixed K 또는 Jetendard — 계약 §5 폰트 정책 참조" -ForegroundColor Gray
