#!/bin/bash
# gugyeol-decode 원클릭 설치 (macOS / Linux / WSL)
#
# 사용:
#   curl -fsSL https://raw.githubusercontent.com/hw725/gugyeol-decode/master/install.sh | bash
#
# 또는 이미 clone한 경우:
#   bash install.sh
set -e

SKILLS_DIR="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
TARGET="$SKILLS_DIR/gugyeol-decode"
REPO_URL="https://github.com/hw725/gugyeol-decode.git"

echo "==================================="
echo " gugyeol-decode 원클릭 설치"
echo "==================================="

# 1. Python 확인
if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
    echo "[ERROR] Python 미설치. https://python.org 에서 Python 3.9+ 설치 후 재시도."
    exit 1
fi
PY=$(command -v python3 || command -v python)
echo "[OK] Python: $PY"

# 2. clone (이미 있으면 스킵)
mkdir -p "$SKILLS_DIR"
if [ -d "$TARGET/.git" ]; then
    echo "[SKIP] 이미 설치되어 있음 ($TARGET). 업데이트는: cd $TARGET && git pull"
elif [ -d "$TARGET" ]; then
    echo "[ERROR] $TARGET 가 이미 존재. 수동으로 정리 후 재시도."
    exit 1
else
    echo "[>] git clone $REPO_URL → $TARGET"
    git clone --depth 1 "$REPO_URL" "$TARGET"
fi

# 3. setup
cd "$TARGET"
echo "[>] python setup.py (의존성·매핑 데이터 자동 다운로드, 5-10분)"
"$PY" setup.py

echo
echo "==================================="
echo " 설치 완료"
echo "==================================="
echo " Claude Code 사용자: 그냥 자연어로 호출"
echo "   '이 PDF에서 옛한글이 깨져 나와 — 풀어줘'"
echo
echo " CLI 사용자:"
echo "   $PY $TARGET/scripts/decode.py <파일.pdf|.hwpx|.hwp>"
