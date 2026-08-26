#!/usr/bin/env python3
"""
gugyeol-decode — 폰트 이름 mojibake 복원 유틸리티

PyMuPDF가 추출하는 폰트 이름이 종종 cp949 → latin1 mojibake로 깨져서 나온다.
예: '*ÇÑ¾ç½Å¸íÁ¶' → '*한양신명조'

이 모듈은 가능한 mojibake 패턴을 탐지하고 정상 폰트명으로 복원한다.

사용법 (CLI):
  python scripts/font_alias.py "*ÇÑ¾ç½Å¸íÁ¶"
  → *한양신명조
"""
from __future__ import annotations

import sys


def restore_korean_font_name(garbled: str) -> str:
    """latin1로 디코드된 cp949 바이트를 정상 한글로 복원."""
    if not garbled:
        return garbled
    try:
        # latin1로 인코드해서 cp949로 디코드 (역변환)
        restored = garbled.encode("latin1").decode("cp949")
        # 한글이 포함되면 복원 성공으로 본다
        if any("가" <= c <= "힣" for c in restored):
            return restored
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return garbled


COMMON_KOREAN_FONTS = {
    # 식별된 폰트 패턴 (확장 가능)
    "한양신명조": ["*한양신명조", "*ÇÑ¾ç½Å¸íÁ¶"],
    "한양중고딕": ["*한양중고딕", "*ÇÑ¾çÁß°íµñ"],
    "한컴 명조": ["*명조", "*¸íÁ¶", "Hancom 명조"],
    "신명-세명조": ["*신명-세명조", "*½Å¸í-¼¼¸íÁ¶"],
    "함초롬바탕": ["*함초롬바탕", "HamchorombatangLVT"],
    "함초롬돋움": ["*함초롬돋움", "HamchoromdotumLVT"],
}


def font_family_hint(font_name: str) -> str | None:
    """폰트 이름에서 family 추정. 옛한글/구결자 폰트면 family 반환, 아니면 None."""
    restored = restore_korean_font_name(font_name)
    for family, aliases in COMMON_KOREAN_FONTS.items():
        for alias in aliases:
            if alias in restored or alias in font_name:
                return family
    # 기타 한글 폰트 패턴
    if any(s in font_name for s in ["Hancom", "한컴", "한양", "Nanum", "함초롬"]):
        return "기타 한글"
    if font_name.startswith("TT70"):
        # 한국 학술 출판에서 자주 쓰이는 폰트군 (한양정보통신 계열)
        return "TT70 (한양정보통신 계열, 옛한글 가능성 높음)"
    return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # 데모
        examples = [
            "*ÇÑ¾ç½Å¸íÁ¶",
            "*¸íÁ¶",
            "TT7064o00",
            "Arial",
            "*ÇÑ¾çÁß°íµñ",
        ]
        for s in examples:
            print(f"{s:30s} → {restore_korean_font_name(s):20s} "
                  f"(family: {font_family_hint(s)})")
    else:
        for arg in sys.argv[1:]:
            print(f"{arg} → {restore_korean_font_name(arg)} "
                  f"(family: {font_family_hint(arg)})")
