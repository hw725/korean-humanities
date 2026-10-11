"""수강생판 PreToolUse 훅 — 막는 것 셋: 원본 쓰기, 영구 삭제, 이름 기준 프로세스 종료.

원본 = 계약의 protect 글롭 + 기본값(원본/**, primary_data/**). 계약이 없어도 기본값은 지킨다.
영구 삭제(rm·Remove-Item·del·rmdir /s·git clean -f…)는 막고 휴지통 명령(harness.py trash)을 알려 준다. git rm 은
git 이력으로 되돌릴 수 있어 막지 않는다(-f 는 저장 안 된 변경을 버리므로 원본이면 막는다). 다만 git 이 작업 트리의 원본을
덮어쓰는 명령(restore·checkout -- <경로>·checkout -f·switch -f|--discard-changes·reset --hard·stash·checkout-index -f·
read-tree --reset -u)은 원본을 겨누거나, 저장소 전체를 겨누는데 그 저장소에 원본이 있으면 막는다(저장 안 된 변경이 사라진다).
git 앞 전역 옵션(--no-pager·--work-tree=…·-C …)은 건너뛰고 하위 명령을 본다.
이름 기준 종료는 사용자가 열어 둔 같은 프로그램까지 닫으므로 막는다. PowerShell 호출 연산자 «&» 뒤도 명령 자리다.
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
DRIVE_RX = re.compile(r"^/([a-zA-Z])(/|$)")
# 끄기·쓰기·옮기기·복사도 «명령 자리»로 가린다 — echo 'pkill node'·Get-Help Stop-Process 는 명령이 아니다(Codex §16-21 리뷰 #11)
WRITE_CMDS = {"tee", "set-content", "add-content", "out-file", "clear-content", "truncate", "touch", "sc", "ac"}
MOVE_CMDS = {"mv", "move-item", "rename-item", "move", "ren", "mi", "rni"}
COPY_CMDS = {"cp", "copy-item", "copy", "xcopy", "robocopy", "cpi"}
SKIP_WORDS = ("sudo", "xargs", "env", "command", "exec", "time", "nohup")
# 값을 받는 앞잡이 옵션 — 다음 낱말이 명령이 아니라 옵션 값이다
SKIP_OPT_VALUE = {"sudo": ("-u", "-g", "-h", "-p", "-C", "-D", "-r", "-t", "-U", "-T"), "env": ("-u", "-C", "-S", "--unset", "--chdir"),
                  "xargs": ("-I", "-n", "-P", "-L", "-s", "-d", "-E", "-a")}
ASSIGN_RX = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.*")
CD_WORDS = {"cd", "pushd", "set-location", "sl", "chdir"}
HOLDS_CAP = 20000  # 폴더 안 원본 탐색 상한 — 넘으면 «있을 수 있다»로 보고 막는다(깊이로 자르지 않는다)
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
    """; && || | & 줄바꿈으로 구간을 나누되 따옴표 안은 나누지 않는다(«py -c "a=1; del a"»는 한 구간).
    홑 & 도 경계다 — bash 의 백그라운드(«sleep 1 & rm x»)와 PowerShell 호출 연산자(«& Stop-Process …»)
    뒤가 다음 명령 자리다(리뷰 ③ R-9). 리다이렉트의 &(«2>&1»·«&>»)는 경계가 아니다."""
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
        elif ch in ";|\n" or cmd.startswith("&&", i) or (
                ch == "&" and not (i and cmd[i - 1] in "<>") and not cmd.startswith("&>", i)):
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
    if toks and toks[0].startswith("&"):  # PowerShell 호출 연산자(«&'C:\x.exe'»처럼 붙여 쓴 꼴 포함, 리뷰 ③ R-9)
        toks = ([toks[0][1:]] if toks[0][1:] else []) + toks[1:]
    # 앞잡이(sudo·env …)와 그 옵션·옵션 값, 환경 변수 할당(FLAG=1)을 건너뛴다 — «sudo -u root rm»·«env FLAG=1 rm»의 실제 명령을
    # 옵션 값·할당으로 읽던 것(리뷰 ⑤ p4 R-4)
    while toks:
        if ASSIGN_RX.fullmatch(toks[0]):
            toks = toks[1:]
            continue
        if toks[0].lower() not in SKIP_WORDS:
            break
        word0 = toks[0].lower()
        toks = toks[1:]
        while toks and (toks[0].startswith("-") or (word0 == "env" and ASSIGN_RX.fullmatch(toks[0]))):
            takes = toks[0] in SKIP_OPT_VALUE.get(word0, ())
            toks = toks[2:] if takes and len(toks) > 1 else toks[1:]
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
    word, args = command(seg)
    if word in DELETE_CMDS:
        return True
    if word == "git":
        # 하위 명령은 전역 옵션(--no-pager·-P·--git-dir …)을 건너뛰고 읽는다 — 종전 정규식은 -C 만 건너뛰어
        # «git --no-pager clean -fd»가 통과했다(전수 S-20261011-175508-48d241 F1)
        _, sub, opts = git_sub(args, Path("."))
        flags = [o for o in opts if o.startswith("-")]
        forced = any(f == "--force" or (not f.startswith("--") and "f" in f[1:]) for f in flags)
        return sub == "clean" and forced and not any(f in ("-n", "--dry-run") for f in flags)
    return bool(FIND_DELETE_RX.search(seg)) and word == "find"


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


def holds_protected(path: str, cwd: Path) -> bool:
    """폴더를 옮기면 그 안의 원본도 옮겨진다 — 폴더 안에 원본이 있는가(Codex §16-21 리뷰 #7). 깊이로 자르지 않는다 — 깊이 6에서
    끊고 «없음»으로 보던 것은 깊은 곳의 원본을 폴더째 옮기게 했다(리뷰 ⑤ p4 R-6). 너무 커서 다 보지 못하면 «있을 수 있다»(막는 쪽)."""
    p = _abs(path, cwd)
    if not p.is_dir():
        return False
    seen = 0
    for dp, dns, fns in os.walk(p):
        for n in dns + fns:
            seen += 1
            if seen > HOLDS_CAP:
                return True
            if is_protected(str(Path(dp) / n), cwd):
                return True
        dns[:] = [d for d in dns if d not in (".git", "node_modules", ".venv", "venv", "__pycache__")]
    return False


GIT_READ_STASH = {"list", "show", "drop", "clear", "pop", "apply", "branch", "create", "store"}
GIT_OPT_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env", "--super-prefix"}


def git_sub(args: list[str], cwd: Path) -> tuple[Path, str, list[str]]:
    """(작업 트리 기준 폴더, 하위 명령 소문자, 하위 명령 뒤 인수). 하위 명령 앞 전역 옵션(--no-pager·-P·
    --work-tree[=]…·--git-dir[=]…·-C·-c)은 건너뛴다. 하위 명령이 없으면 빈 문자열."""
    base, rest = cwd, list(args)
    while rest and rest[0].startswith("-"):
        o = rest[0]
        if o in GIT_OPT_WITH_VALUE and len(rest) > 1:
            if o in ("-C", "--work-tree"):
                base = _abs(rest[1], base)
            rest = rest[2:]
            continue
        if o.startswith("--work-tree="):
            base = _abs(o.split("=", 1)[1], base)
        rest = rest[1:]
    return (base, rest[0].lower(), rest[1:]) if rest else (base, "", [])


def _repo_root(start: Path) -> Path:
    for d in [start, *start.parents]:
        if (d / ".git").exists():
            return d
    return start


def git_overwrites(seg: str, cwd: Path) -> str | None:
    """git 이 원본을 작업 트리째 덮어쓰는가(리뷰 ③ R-10). 덮는 경로를 돌려준다(저장소 전체면 저장소 폴더).
    본다: restore(--staged 만이면 작업 트리를 건드리지 않음)·checkout -- <경로>·checkout -f·reset --hard|--merge|--keep·
    stash(인자 없음·push·save, 경로를 주면 그 경로)·clean·switch -f|--discard-changes·rm -f(--cached 아님)·
    checkout-index -f·read-tree --reset -u. 저장소 전체가 대상이면 그 저장소 안에 원본이 있을 때만 막는다.
    하위 명령 앞 전역 옵션(--no-pager·-P·--work-tree[=]…·--git-dir[=]…·-C·-c)은 건너뛴다 — 종전에는 «git --no-pager
    checkout -- 원본»이 하위 명령을 «--no-pager»로 읽어 통과했다."""
    word, args = command(seg)
    if word != "git":
        return None
    base, sub, opts = git_sub(args, cwd)
    if not sub:
        return None
    if "--" in opts:
        k = opts.index("--")
        paths, flags = opts[k + 1:], [o for o in opts[:k] if o.startswith("-")]
    else:
        paths, flags = [o for o in opts if not o.startswith("-")], [o for o in opts if o.startswith("-")]
    whole = False
    if sub == "restore":
        if ("--staged" in flags or "-S" in flags) and not ("--worktree" in flags or "-W" in flags):
            return None
        whole = not paths or any(p in (".", ":/", "*") for p in paths)
    elif sub == "checkout":
        if "--" in opts:
            whole = not paths or any(p in (".", ":/", "*") for p in paths)
        else:
            if any(f in ("-f", "--force") for f in flags):
                whole = True
            # «git checkout <경로>»도 덮어쓴다 — 있는 경로 인수만 경로로 본다(가지 이름은 아니다)
            paths = [p for p in paths if p == "." or _abs(p, base).exists()]
            whole = whole or "." in paths
            if not whole and not paths:
                return None
    elif sub == "reset":
        if not any(f in ("--hard", "--merge", "--keep") for f in flags):
            return None  # --soft·--mixed 는 작업 트리를 건드리지 않는다
        whole = True
    elif sub == "stash":
        head = opts[:opts.index("--")] if "--" in opts else opts
        words = [o for o in head if not o.startswith("-")]
        act = words[0].lower() if words else ""
        if act in GIT_READ_STASH:
            return None
        if "--" not in opts:  # «stash push <경로>…»만 경로, «stash save <메시지>»·인자 없음은 저장소 전체
            paths = words[1:] if act == "push" else []
        whole = not paths
    elif sub == "clean":
        whole = not paths
    elif sub == "switch":
        if not any(f in ("-f", "--force", "--discard-changes") for f in flags):
            return None  # 저장 안 된 변경이 있으면 git 이 거부한다
        whole = True
    elif sub == "rm":
        forced = any(f in ("-f", "--force") or (not f.startswith("--") and "f" in f[1:]) for f in flags)
        if not forced or "--cached" in flags:
            return None  # -f 없는 rm 은 저장 안 된 변경이 있으면 거부하고, 지운 것은 git 이력으로 되돌린다
    elif sub == "checkout-index":
        if not any(f in ("-f", "--force") for f in flags):
            return None
        whole = any(f in ("-a", "--all") for f in flags) or not paths
    elif sub == "read-tree":
        if not ("--reset" in flags and "-u" in flags):
            return None
        whole = True
    else:
        return None
    if whole:
        repo = _repo_root(base.resolve())
        return str(repo) if holds_protected(str(repo), cwd) or is_protected(str(repo), cwd) else None
    for p in paths:
        if is_protected(str(_abs(p, base)), cwd) or holds_protected(str(_abs(p, base)), cwd):
            return p
    return None


def main() -> int:
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}")
        data = data if isinstance(data, dict) else {}  # 객체가 아닌 JSON 에 Traceback 으로 죽지 않게
    except json.JSONDecodeError:
        return 0
    name = data.get("tool_name")
    ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}  # 객체가 아닌 입력에 죽지 않게
    cwd = Path(data.get("cwd") if isinstance(data.get("cwd"), str) and data.get("cwd") else os.getcwd())
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
    here = cwd
    for seg in split_segments(body):
        seg = strip_messages(seg)
        word, args = command(seg)
        if word in CD_WORDS:
            # 구간 사이의 작업 폴더 변경을 따라간다 — «cd ../B && git reset --hard»를 처음 폴더 기준으로 보던 것(리뷰 ⑤ p4 R-5)
            dest = next((x for x in args if not x.startswith("-")), None)
            if dest:
                here = _abs(dest, here)
            continue
        if kills_by_name(seg):
            return deny(kill_msg)
        if deletes(seg):
            return deny("[harness-lite] 영구 삭제는 막혀 있습니다 — 휴지통으로 보내세요: " + lc.cli_command("trash <경로>"))
        g = git_overwrites(seg, here)
        if g:
            return deny(f"[harness-lite] git 명령이 원본(읽기만 할 자료)을 덮어쓸 수 있습니다({g}) — 원본의 저장 안 된 변경이 "
                        "사라집니다. 원본이 아닌 경로만 지정하거나, 사용자가 직접 하세요.")
        for t in trash_targets(word, args):
            # 공식 휴지통 명령도 원본은 옮기지 않는다 — Move-Item 은 막으면서 trash 로는 원본을 옮기던 모순(리뷰 ⑤ p4 R-3)
            if is_protected(t, here) or holds_protected(t, here):
                return deny(f"[harness-lite] {t} 는 원본(읽기만 할 자료)이거나 원본을 품은 폴더입니다 — 휴지통으로도 보내지 않습니다.")
        targets, moved = shell_targets(seg)
        for t in moved:
            if t and holds_protected(t, here):
                return deny(f"[harness-lite] {t} 안에 원본(읽기만 할 자료)이 있어 폴더째 옮기지 않습니다.")
        for t in targets:
            if t and is_protected(t, here):
                return deny(f"[harness-lite] {t} 는 원본(읽기만 할 자료)입니다 — 셸로도 바꾸지 않습니다. 결과는 다른 폴더에 쓰세요.")
    return 0


def trash_targets(word: str, args: list[str]) -> list[str]:
    """`… harness.py trash <경로> …` 의 경로들(sh run.sh harness.py trash · py harness.py trash 모두)."""
    seq = [word, *args]
    for i, t in enumerate(seq):
        if re.split(r"[/\\]", t)[-1].lower() == "harness.py":
            rest = seq[i + 1:]
            while rest and rest[0].startswith("-"):  # --root 같은 전역 옵션
                rest = rest[2:] if rest[0] == "--root" and len(rest) > 1 else rest[1:]
            if rest and rest[0].lower() == "trash":
                return [x for x in rest[1:] if not x.startswith("-")]
    return []


if __name__ == "__main__":
    sys.exit(main())
