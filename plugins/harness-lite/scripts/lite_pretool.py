"""수강생판 PreToolUse 훅 — 막는 것 셋: 원본 쓰기, 영구 삭제, 이름 기준 프로세스 종료.

원본 = 계약의 protect 글롭 + 기본값(원본/**, primary_data/**). 계약이 없어도 기본값은 지킨다.
영구 삭제(rm·Remove-Item·del·rmdir /s·git clean -f…)는 막고 휴지통 명령(harness.py trash)을 알려 준다. git rm 은
git 이력으로 되돌릴 수 있어 막지 않는다. 이름 기준 종료는 사용자가 열어 둔 같은 프로그램까지 닫으므로 막는다.
heredoc 본문과 커밋 메시지 속 낱말은 명령이 아니다.
한계: 로컬 훅은 보안 장치가 아니다 — 실수를 막는 장치다. 문자열을 조립하면 빠져나갈 수 있다.
"""
# run-harness: allow-kill-patterns  (이 파일은 금지 명령을 «찾는» 정규식을 담는다)
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lite_common as lc  # noqa: E402

for _stream in (sys.stdout, sys.stderr):  # CJK 계약 E3
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass
# 어느 깊이의 원본/·primary_data/ 든 지킨다(계약 폴더 바로 아래만이 아니라 — 2026-10-11 교차 확인 #2)
DEFAULT_PROTECT = ["원본/**", "**/원본/**", "primary_data/**", "**/primary_data/**"]
EDIT_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
# 지우는 명령은 «명령 자리»(구간의 첫 낱말, sudo·xargs 뒤 포함)에 올 때만 — 검색어·도움말·파이썬 코드 속 낱말은 명령이 아니다
DELETE_CMDS = {"rm", "rmdir", "unlink", "shred", "del", "erase", "rd", "ri", "remove-item"}
FIND_DELETE_RX = re.compile(r"\bfind\b[^\n]*\s(?:-delete\b|-exec\s+rm\b)", re.I)
GIT_CLEAN_RX = re.compile(r"\bgit\s+(?:-C\s+\S+\s+)?clean\b[^\n]*\s-[a-zA-Z]*f", re.I)
DRIVE_RX = re.compile(r"^/([a-zA-Z])(/|$)")
# 끄기·쓰기·옮기기·복사도 «명령 자리»로 가린다 — echo 'pkill node'·Get-Help Stop-Process 는 명령이 아니다(Codex §16-21 리뷰 #11)
WRITE_CMDS = {"tee", "set-content", "add-content", "out-file", "clear-content", "truncate", "touch", "sc", "ac"}
MOVE_CMDS = {"mv", "move-item", "rename-item", "move", "ren", "mi", "rni"}
COPY_CMDS = {"cp", "copy-item", "copy", "xcopy", "robocopy", "cpi"}
SKIP_WORDS = ("sudo", "xargs", "env", "command", "exec", "time", "nohup")
PS_KILL_PIPE_RX = re.compile(r"(?:^|[;\n&(])\s*(?:Get-Process|gps|ps)\b[^\n;]*\|\s*(?:Stop-Process|spps|kill)\b", re.I)
HEREDOC_RX = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][\w-]*)\1")
INTERPRETER_RX = re.compile(r"(?:^|[\s/\\(])(?:py|python[\d.]*|sh|bash|zsh|node|deno|perl|ruby|php|pwsh|powershell|cmd)(?:\.exe)?(?=\s|$)", re.I)


def deny(reason: str) -> int:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": reason}}, ensure_ascii=False))
    return 0


def strip_data_heredocs(cmd: str) -> str:
    """해석기에 넘기지 않는 heredoc 본문(cat·git 에 넘기는 글)을 뺀다. 닫히지 않으면 그대로 둔다."""
    lines = cmd.split("\n")
    out, i = [], 0
    while i < len(lines):
        ln = lines[i]
        out.append(ln)
        heads = HEREDOC_RX.findall(ln)
        if not heads:
            i += 1
            continue
        code = bool(INTERPRETER_RX.search(ln))
        j = i + 1
        for q, tag in heads:
            k = j
            while k < len(lines) and lines[k].strip() != tag:
                k += 1
            if k >= len(lines):
                return cmd
            # 따옴표 없는 heredoc 은 본문의 $(…)·`…` 를 셸이 실행한다 — 그런 본문은 데이터가 아니다
            if code or (not q and any("$(" in s or "`" in s for s in lines[j:k])):
                out += lines[j:k]
            out.append(lines[k])
            j = k + 1
        i = j
    return "\n".join(out)


def strip_messages(seg: str) -> str:
    seg = re.sub(r"(?:^|\s)(?:-m|--message)(?:=|\s+)(?:\"[^\"]*\"|'[^']*')", " ", seg)
    return re.sub(r"(?:^|\s)-F\s+\S+", " ", seg)


def split_segments(cmd: str) -> list[str]:
    """; && || | 줄바꿈으로 구간을 나누되 따옴표 안은 나누지 않는다(«py -c "a=1; del a"»는 한 구간)."""
    out, cur, q, i = [], [], None, 0
    while i < len(cmd):
        ch = cmd[i]
        if q:
            cur.append(ch)
            if ch == q:
                q = None
        elif ch in "\"'":
            q = ch
            cur.append(ch)
        elif ch in ";|\n" or cmd.startswith("&&", i):
            out.append("".join(cur))
            cur = []
            if cmd.startswith(("&&", "||"), i):
                i += 1
        else:
            cur.append(ch)
        i += 1
    out.append("".join(cur))
    return out


def tokens(seg: str) -> list[str]:
    return [a or b or c for a, b, c in re.findall(r"\"([^\"]*)\"|'([^']*)'|(\S+)", seg.strip().lstrip("("))]


def command(seg: str) -> tuple[str, list[str]]:
    """(명령 낱말 소문자·경로 뗀 것, 인수들). sudo·xargs·env 같은 앞잡이와 그 옵션은 건너뛴다. 리다이렉트는 인수가 아니다."""
    toks = tokens(seg)
    while toks and toks[0].lower() in SKIP_WORDS:
        toks = toks[1:]
        while toks and toks[0].startswith("-"):
            toks = toks[1:]
    if not toks:
        return "", []
    word = re.split(r"[/\\]", toks[0])[-1].lower()
    word = word[:-4] if word.endswith(".exe") else word
    args, skip = [], False
    for t in toks[1:]:
        if skip:
            skip = False
            continue
        if re.match(r"^\d?>{1,2}", t):  # «> 파일»이면 다음 낱말도 리다이렉트 대상이지 인수가 아니다
            skip = bool(re.fullmatch(r"\d?>{1,2}&?", t))
            continue
        args.append(t)
    return word, args


def deletes(seg: str) -> bool:
    """구간이 영구 삭제인가 — 명령 자리가 지우는 명령이거나 find -delete·git clean -f. git rm 은 명령 자리가 git 이라 해당 없다
    (낱말 «git rm»이 인수에 있다고 면제하지 않는다 — Codex §16-21 리뷰 #10)."""
    word, _ = command(seg)
    if word in DELETE_CMDS:
        return True
    return bool(FIND_DELETE_RX.search(seg) or GIT_CLEAN_RX.search(seg)) and word in ("find", "git")


def kills_by_name(seg: str) -> bool:
    word, args = command(seg)
    low = [a.lower() for a in args]
    if word in ("pkill", "killall"):
        return True
    if word == "taskkill":
        return "/im" in low or "-im" in low
    if word in ("stop-process", "spps", "kill") and any(a.startswith(("-name", "-processname")) for a in low):
        return True
    return word == "wmic" and "process" in low and "where" in low


def _opt_value(args: list[str], names: tuple[str, ...]) -> str | None:
    for i, a in enumerate(args):
        al = a.lower()
        for n in names:
            if al == n and i + 1 < len(args):
                return args[i + 1]
            if al.startswith(n + "=") or (n.startswith("-") and al.startswith(n + ":")):
                return a.split("=", 1)[-1] if "=" in a else a.split(":", 1)[-1]
    return None


def shell_targets(seg: str) -> tuple[list[str], list[str]]:
    """(이 구간이 바꾸는 경로, 옮겨 가는 원래 경로). 리다이렉트 대상, 쓰기 명령의 경로 인수, 이동의 모든 경로,
    복사의 대상(-t·--target-directory·-Destination, robocopy 는 둘째, 아니면 마지막 경로) — Codex §16-21 리뷰 #8."""
    out = re.findall(r"(?<![<>=\-\d])>{1,2}\s*[\"']?([^\s\"'|;&]+)", seg)
    word, args = command(seg)
    pos = [a for a in args if not a.startswith("-")]
    moved: list[str] = []
    if word in WRITE_CMDS or (word == "sed" and any(a.startswith("-i") for a in args)):
        out += pos[1:] if word == "sed" else pos
        v = _opt_value(args, ("-path", "-literalpath", "-filepath"))
        out += [v] if v else []
    elif word in MOVE_CMDS:
        out += pos
        moved = pos[:-1] if len(pos) > 1 else pos
        v = _opt_value(args, ("-destination",))
        out += [v] if v else []
        moved += [x for x in (_opt_value(args, ("-path", "-literalpath")),) if x]
    elif word in COPY_CMDS:
        dest = _opt_value(args, ("-t", "--target-directory", "-destination"))
        if dest:
            out.append(dest)
        elif word == "robocopy" and len(pos) >= 2:
            out.append(pos[1])
        else:
            src = _opt_value(args, ("-path", "-literalpath"))
            rest = [p for p in pos if p != src]
            if len(rest) >= (1 if src else 2):
                out.append(rest[-1])
    return out, moved


def _abs(path: str, cwd: Path) -> Path:
    s = str(path)
    if os.name == "nt":
        s = DRIVE_RX.sub(lambda m: m.group(1).upper() + ":/", s)  # Git Bash 꼴 /c/… → C:/… (교차 확인 #1)
    p = Path(s)
    return (p if p.is_absolute() else cwd / p).resolve()


def _abs_match(p: Path, pats: list[str]) -> bool:
    """절대 경로로 적은 protect(«D:/연구/원본/**» — 계약 폴더 밖 원본)를 맞춘다(교차 확인 #2)."""
    import fnmatch
    s = p.as_posix()
    for pat in pats:
        q = pat.replace("\\", "/")
        if os.name == "nt":
            q = DRIVE_RX.sub(lambda m: m.group(1).upper() + ":/", q)
        if not (Path(q.split("*")[0] or "x").is_absolute()):
            continue
        a, b = (s.lower(), q.lower()) if os.name == "nt" else (s, q)
        if fnmatch.fnmatch(a, b) or (b.endswith("/**") and (a == b[:-3] or a.startswith(b[:-2]))):
            return True
    return False


def _protect_of(cp: Path) -> list[str]:
    try:
        return [x for x in lc.load(cp).get("protect") or [] if isinstance(x, str)]
    except (OSError, ValueError):
        return []


def is_protected(path: str, cwd: Path) -> bool:
    """경로가 원본인가 — 그 경로를 품은 계약 폴더(없으면 작업 폴더) 기준 상대 경로를 protect 글롭과 맞추고,
    절대 경로로 적은 protect 는 절대 경로로 맞춘다."""
    p = _abs(path, cwd)
    cp = lc.find_contract(p if p.is_dir() else p.parent)
    root = cp.parent if cp else cwd.resolve()
    pats = list(DEFAULT_PROTECT)
    if cp:
        pats += _protect_of(cp)
    # 절대 경로 protect 는 작업 폴더의 계약에도 적힌다 — 원본이 계약 폴더 밖에 있으면 그 파일을 품은 계약이 없다
    cwd_cp = lc.find_contract(cwd)
    if _abs_match(p, pats + (_protect_of(cwd_cp) if cwd_cp and cwd_cp != cp else [])):
        return True
    try:
        rel = p.relative_to(root).as_posix()
    except ValueError:
        return False
    return lc.matches(rel, pats)


def holds_protected(path: str, cwd: Path, depth: int = 6) -> bool:
    """폴더를 옮기면 그 안의 원본도 옮겨진다 — 폴더 안에 원본이 있는가(Codex §16-21 리뷰 #7)."""
    p = _abs(path, cwd)
    if not p.is_dir():
        return False
    for dp, dns, fns in os.walk(p):
        if len(Path(dp).relative_to(p).parts) >= depth:
            dns[:] = []
        for n in dns + fns:
            if is_protected(str(Path(dp) / n), cwd):
                return True
        dns[:] = [d for d in dns if d not in lc.SKIP_DIRS]
    return False


def main() -> int:
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}")
    except json.JSONDecodeError:
        return 0
    name, ti = data.get("tool_name"), data.get("tool_input") or {}
    cwd = Path(data.get("cwd") or os.getcwd())
    if name in EDIT_TOOLS:
        fp = ti.get("file_path") or ti.get("notebook_path")
        if fp and is_protected(fp, cwd):
            return deny(f"[harness-lite] {fp} 는 원본(읽기만 할 자료)입니다 — 고친 결과는 다른 폴더에 쓰세요. "
                        "원본을 바꿔야 하면 사용자가 직접 하거나, 계약의 protect 를 사용자와 함께 고치세요.")
        return 0
    if name not in ("Bash", "PowerShell"):
        return 0
    cmd = ti.get("command")
    if not isinstance(cmd, str) or not cmd.strip():
        return 0
    body = strip_data_heredocs(cmd)
    kill_msg = ("[harness-lite] 프로그램 이름으로 프로세스를 끄면 사용자가 열어 둔 같은 프로그램까지 닫힙니다 — "
                "직접 띄운 프로세스의 번호(PID)로만 끄세요.")
    if PS_KILL_PIPE_RX.search(re.sub(r"\"[^\"]*\"|'[^']*'", "", body)):
        return deny(kill_msg)
    for seg in split_segments(body):
        seg = strip_messages(seg)
        if kills_by_name(seg):
            return deny(kill_msg)
        if deletes(seg):
            return deny("[harness-lite] 영구 삭제는 막혀 있습니다 — 휴지통으로 보내세요: " + lc.cli_command("trash <경로>"))
        targets, moved = shell_targets(seg)
        for t in moved:
            if t and holds_protected(t, cwd):
                return deny(f"[harness-lite] {t} 안에 원본(읽기만 할 자료)이 있어 폴더째 옮기지 않습니다.")
        for t in targets:
            if t and is_protected(t, cwd):
                return deny(f"[harness-lite] {t} 는 원본(읽기만 할 자료)입니다 — 셸로도 바꾸지 않습니다. 결과는 다른 폴더에 쓰세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
