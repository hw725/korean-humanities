#!/usr/bin/env python3
"""CJK 서지 제목 정규화·동일성 판정 (korean-humanities 슈트 공용 헬퍼).

색인 DB(KCI·CrossRef·OpenAlex 등)에서 받은 제목과 우리가 가진 제목이 「같은 논문인가」를
판정할 때, 한자·한글 제목에서 실제로 어긋나는 것은 내용이 아니라 표기 잡음이다:
NFD로 들어온 한글, 서명 부호 《》「」, 꼬리 마침표 「。」, 한자 사이에 끼어든 공백,
전각/반각 구두점. 이 모듈은 그 잡음만 걷어내고 나머지는 그대로 비교한다.

설계 원칙(hanmun-research-assistant §CJK Text Handling Contract):
- 정규화는 **NFC** 한 번 — NFKC·casefold 같은 광역 정규화는 쓰지 않는다. 「Ⅱ」와 「II」,
  「㈜」와 「(주)」가 같아지는 것은 제목 동일성 판정에서 과잉이다.
- 한자·한글 판정은 `regex`의 `\\p{Han}`·`\\p{Hangul}` — 하드코딩 범위(`[一-鿿]`)는
  확장 B 이상·옛한글 첫가끝을 놓친다.
- CJK 경로는 **양쪽 모두** 한자·한글·가나 중 하나를 포함할 때만 탄다(일본 문헌 제목 대비).
  꼬리 마침표 제거 대상은 `。．.`와 가운뎃점 `·`(전각 마침표 대용으로 쓰이는 경우) 네 글자다. 한쪽만 CJK면 같은 논문의
  국문·영문 제목일 수 있으므로 이 모듈은 「다르다」가 아니라 「판정 불가(False)」를 낸다 —
  호출자가 다른 근거(DOI·연도·저자)로 판단해야 한다.

개념 출처: Imbad0202/academic-research-skills `_text_similarity.py`의 「CJK 제목은 별도
경로로, 서명 부호·꼬리 마침표·한자 인접 공백만 제거」라는 발상(CC BY-NC 4.0, 코드 미참조 —
NOTICE.md §3). 구현은 여기서 새로 썼고, 정규화 층(NFC)·문자 판정(`regex`)·판정 불가 반환
설계는 슈트 계약에 맞춘 것이라 원본과 다르다.

사용:
    py scripts/cjk_title_match.py --selftest
    py scripts/cjk_title_match.py "《朝鮮王朝實錄》 硏究。" "朝鮮王朝實錄 研究"

파이썬에서:
    from cjk_title_match import normalize_cjk_title, cjk_titles_match, title_key
"""
from __future__ import annotations

import argparse
import sys
import unicodedata

import regex  # stdlib re 금지 — 계약 §2

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

# CJK 서명 부호 — 어디에 있든 표기 잡음(같은 논문을 한 DB는 《》로 감싸고 다른 DB는 안 감싼다).
_CJK_TITLE_MARKS = "《》〈〉「」『』"
# 인용 부호 — 제목 전체를 감싸는 것만 벗긴다(영문 제목 안의 아포스트로피는 내용이다).
_WRAPPER_PAIRS = (
    ("“", "”"), ("‘", "’"), ("\"", "\""), ("'", "'"),
)
# 꼬리 마침표 — 표기 잡음. 물음표·느낌표는 제목 내용이므로 남긴다.
_TRAILING_STOPS = "。．.·"
# CJK 문자(한자·한글·가나) 인접 공백 — 한자 사이 공백은 조판 잡음이다.
_CJK_CLASS = r"[\p{Han}\p{Hangul}\p{Hiragana}\p{Katakana}]"
_SPACE_NEXT_TO_CJK = regex.compile(
    rf"(?<={_CJK_CLASS})\s+|\s+(?={_CJK_CLASS})"
)
_MULTI_SPACE = regex.compile(r"\s+")
_HAS_CJK = regex.compile(_CJK_CLASS)
# 전각 → 반각 구두점 (NFKC 없이 필요한 것만 명시)
_PUNCT_MAP = str.maketrans({
    "：": ":", "；": ";", "，": ",", "（": "(", "）": ")", "－": "-", "～": "~", "！": "!", "？": "?",
})


def has_cjk(text: str | None) -> bool:
    """한자·한글·가나 중 하나라도 있으면 True."""
    return bool(text) and _HAS_CJK.search(text) is not None


def _strip_wrappers(s: str) -> str:
    changed = True
    while changed and len(s) >= 2:
        changed = False
        for lo, hi in _WRAPPER_PAIRS:
            if s.startswith(lo) and s.endswith(hi):
                s = s[len(lo):-len(hi)].strip()
                changed = True
                break
    return s


def normalize_cjk_title(title: str | None) -> str:
    """제목 표기 잡음 제거. 내용(글자·어순·부제)은 건드리지 않는다.

    순서: NFC → 양끝 공백 → 바깥 인용 부호 → CJK 서명 부호 전역 제거 → 꼬리 마침표
          → 전각 구두점 반각화 → CJK 인접 공백 제거 → 나머지 연속 공백 1칸.
    """
    if not title:
        return ""
    s = unicodedata.normalize("NFC", title).strip()
    s = _strip_wrappers(s)
    s = s.translate({ord(c): None for c in _CJK_TITLE_MARKS}).strip()
    s = s.rstrip(_TRAILING_STOPS).rstrip()
    s = s.translate(_PUNCT_MAP)
    s = _SPACE_NEXT_TO_CJK.sub("", s)
    s = _MULTI_SPACE.sub(" ", s).strip()
    return s


def title_key(title: str | None) -> str:
    """색인·중복 제거용 키. 정규화 후 라틴 부분만 casefold(CJK는 대소문자가 없다)."""
    return normalize_cjk_title(title).casefold()


def cjk_titles_match(a: str | None, b: str | None) -> bool:
    """두 제목이 표기 잡음만 다른 같은 제목인가.

    양쪽 모두 CJK를 포함할 때만 판정한다. 한쪽만 CJK면 False — 「다르다」가 아니라
    「이 모듈로는 판정 불가」이며, 호출자가 DOI·연도·저자 등으로 별도 판단한다.
    """
    if not (has_cjk(a) and has_cjk(b)):
        return False
    return title_key(a) == title_key(b) != ""


# ---------------------------------------------------------------- selftest
_CASES: tuple[tuple[str, str, bool], ...] = (
    # (a, b, 기대) — 표기 잡음
    ("《朝鮮王朝實錄》 硏究。", "朝鮮王朝實錄 硏究", True),
    ("「退溪 의 理 氣 論」", "退溪의 理氣論", True),
    ("조선 후기 한문 소설 연구", "조선후기 한문소설 연구", True),
    ("東國李相國集：詩", "東國李相國集:詩", True),
    # NFD 한글(macOS 파일명 유입) vs NFC
    (unicodedata.normalize("NFD", "한문학 연구"), "한문학 연구", True),
    # 내용 차이는 잡아야 한다
    ("朝鮮王朝實錄 硏究", "朝鮮王朝實錄 硏究 Ⅱ", False),
    ("退溪의 理氣論", "栗谷의 理氣論", False),
    # 물음표는 내용 — 제거하지 않는다
    ("性理學은 무엇인가?", "性理學은 무엇인가", False),
    # 한쪽만 CJK → 판정 불가(False)
    ("朝鮮王朝實錄 硏究", "A Study of the Veritable Records", False),
    # 둘 다 비-CJK → 이 모듈 소관 아님(False)
    ("A Study", "A Study", False),
    # 빈 값
    ("", "", False),
)


def selftest() -> int:
    bad = 0
    for a, b, want in _CASES:
        got = cjk_titles_match(a, b)
        mark = "ok  " if got == want else "FAIL"
        if got != want:
            bad += 1
        print(f"{mark} {want!s:5} {a!r} ~ {b!r}")
        if got != want:
            print(f"       key(a)={title_key(a)!r} key(b)={title_key(b)!r}")
    # NFC 보존 확인 — NFKC였다면 「Ⅱ」가 「II」로, 「㈜」가 「(주)」로 바뀐다
    assert "Ⅱ" in normalize_cjk_title("硏究 Ⅱ"), "NFKC 오염"
    assert "㈜" in normalize_cjk_title("㈜ 조선"), "NFKC 오염"
    print(f"\n{len(_CASES) - bad}/{len(_CASES)} 통과")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="CJK 서지 제목 정규화·동일성 판정")
    p.add_argument("titles", nargs="*", help="제목 1개면 정규화 결과, 2개면 동일성 판정")
    p.add_argument("--selftest", action="store_true")
    args = p.parse_args(argv)
    if args.selftest:
        return selftest()
    if len(args.titles) == 1:
        print(normalize_cjk_title(args.titles[0]))
        return 0
    if len(args.titles) == 2:
        a, b = args.titles
        print(f"key(a) = {title_key(a)}\nkey(b) = {title_key(b)}\nmatch  = {cjk_titles_match(a, b)}")
        return 0
    p.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
