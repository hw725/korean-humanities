#!/bin/sh
# 수강생판 하네스 실행기 — 파이썬 3.8 이상을 찾아 scripts/ 의 스크립트를 돌린다. 표준 입력은 그대로 넘긴다(훅 입력).
# 파이썬이 없으면 알리기만 하고 막지 않는다(exit 0): 설치 전에 Claude Code 사용이 막히면 안 된다.
# Windows 의 python3 는 Microsoft Store 안내 껍데기일 수 있어(실행하면 조용히 실패) 실제로 돌려 보고 고른다.
here=$(cd "$(dirname "$0")" && pwd)
script="$1"
shift
for py in "py -3" python3 python; do
  if $py -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >/dev/null 2>&1; then
    exec $py "$here/$script" "$@"
  fi
done
msg="[harness-lite] Python 3.8 이상을 찾지 못해 확인 장치가 꺼져 있습니다. 설치 안내는 플러그인 README 를 보세요."
echo "$msg" >&2
# 훅으로 불렸으면 화면에 보이는 알림(systemMessage)도 낸다 — 종료 코드 0 인 훅의 stderr 는 보이지 않는다(교차 확인 #3).
# 훅마다 매번 내면 시끄러우므로 하루 한 번만.
if [ "$script" != "harness.py" ]; then
  mark="${TMPDIR:-/tmp}/harness-lite-nopython-$(date +%Y%m%d)"
  if [ ! -e "$mark" ]; then
    : > "$mark" 2>/dev/null
    printf '{"systemMessage": "%s"}\n' "$msg"
  fi
fi
exit 0
