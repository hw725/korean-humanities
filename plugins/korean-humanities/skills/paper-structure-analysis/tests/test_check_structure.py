"""check_structure.py 시험 — 트리·노트 검사가 잡아야 할 것과 잡으면 안 되는 것(2026-10-22 vault 145편 실측 오탐 포함)."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):  # 시험 이름·실패 메시지에 한글 — cp949 콘솔 대비
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import check_structure as cs  # noqa: E402

TEXT = """<!-- page 1 -->
제목 Ⅰ. 서론
이 글은 김윤식의 문장론을 다룬다.
<!-- page 2 -->
Ⅱ. 본론
文者 貫道之器也 라고 그는 말했다. 줄끝에서 낱-
말이 끊긴다. ![image1](<a_images/x.png>)그림 뒤 문장.
<!-- page 3 -->
Ⅲ. 결론
운양집의 편찬은 늦었다.
"""


def node(nid, title, s, e, kids=()):
    return {"title": title, "node_id": nid, "start_index": s, "end_index": e, "summary": "요약", "nodes": list(kids)}


GOOD_TREE = {"doc_name": "a.pdf", "structure": [
    node("0000", "Ⅰ. 서론", 1, 1),
    node("0001", "Ⅱ. 본론", 2, 2),
    node("0002", "Ⅲ. 결론", 3, 3)]}

MAP = """| 절 | 쪽(PDF / 지면) | 논증상 기능 | 핵심 주장 | 근거 |
|---|---|---|---|---|
| Ⅰ | 1 | 문제 제기 | 가 | 나 |
| Ⅱ | 2 | 사례 분석 | 가 | 나 |
| Ⅲ | 3 | 종합 | 가 | 나 |"""

QUOTES = """> 文者 貫道之器也 (PDF p.2)

> 줄끝에서 낱말이 끊긴다. 그림 뒤 문장. (PDF p.2)

> 운양집의 편찬은 늦었다. (PDF p.3)"""


def page(map_=MAP, quotes=QUOTES, extra="", mermaid='flowchart TD\n  Q["1 물음"] -->|전제| A["2 주장"]'):
    return f"""---
title: "갑, 「을」(2000)"
description: "한 줄"
source_path: "raw/a.pdf"
structure_tree: "t.json"
structure_generator: "Claude (본문 직접)"
sources: ["raw/a.pdf"]
created: 2026-10-22
---
# 갑, 「을」(2000)

## 서지 정보
갑, 『병』 1, 2000.
{extra}
## 한눈에 보는 논증
물음.

## 논증 지도
{map_}

## 논증 흐름도
```mermaid
{mermaid}
```

## 근거의 구성
가.

## 결론의 지탱 구조와 빈틈
나.

## 학술 대화
다.

## 기존 위키와의 연결
라.

## 원문 인용
{quotes}

## 검증 메타데이터
- **검증 범위**: 전문 (PDF p.1～p.3)
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def write(self, name, content):
        p = self.dir / name
        p.write_text(content if isinstance(content, str) else json.dumps(content, ensure_ascii=False), encoding="utf-8")
        return p


class TreeTest(Base):
    def errs(self, tree):
        return cs.check_tree(self.write("t.json", tree), TEXT)[0]

    def test_good_tree_passes(self):
        self.assertEqual(self.errs(GOOD_TREE), [])

    def test_node_id_gap(self):
        t = json.loads(json.dumps(GOOD_TREE))
        t["structure"][1]["node_id"] = "0005"
        self.assertTrue(any("node_id" in e for e in self.errs(t)))

    def test_start_after_end(self):
        t = json.loads(json.dumps(GOOD_TREE))
        t["structure"][1].update(start_index=3, end_index=2)
        self.assertTrue(any("시작 쪽 3 > 끝 쪽 2" in e for e in self.errs(t)))

    def test_beyond_last_page(self):
        t = json.loads(json.dumps(GOOD_TREE))
        t["structure"][2]["end_index"] = 9
        self.assertTrue(any("밖" in e for e in self.errs(t)))

    def test_siblings_reversed(self):
        t = {"structure": [node("0000", "Ⅱ", 2, 2), node("0001", "Ⅰ", 1, 1)]}
        self.assertTrue(any("거꾸로" in e for e in self.errs(t)))

    def test_child_before_parent(self):
        t = {"structure": [node("0000", "Ⅱ", 2, 3, [node("0001", "1", 1, 2)])]}
        self.assertTrue(any("상위 노드 시작" in e for e in self.errs(t)))

    def test_parent_span_not_covering_children_is_allowed(self):
        # 상위 노드 범위를 「첫 하위 노드 앞 도입부」로 적는 관례(실측) — 오류가 아니다.
        t = {"structure": [node("0000", "Ⅱ", 2, 2, [node("0001", "1", 2, 3), node("0002", "2", 3, 3)])]}
        self.assertEqual(self.errs(t), [])

    def test_summary_must_be_korean(self):
        # 2026-10-27: 일본어·중국어 논문 5편의 요약이 원문 언어로 남아 RefManager 에 그대로 보였다.
        # 제목은 원문 그대로(지면 대조 열쇠), 요약은 한국어. 한자·원어 인용이 섞인 한국어 문장은 통과.
        for bad in ("金允植の生涯を四期に分けて略述する。", "文章介绍朝鲜领选使金允植的生平。",
                    "合本の装丁を記述し、序跋の順序を述べ 한다."):
            t = json.loads(json.dumps(GOOD_TREE))
            t["structure"][0]["summary"] = bad
            self.assertTrue(any("요약" in e and "한국어" in e for e in self.errs(t)), bad)
        for ok in ("「東槎謾吟序」를 인용해 1908년의 여정을 재구성한다.", "영문 초록. 영문 제목 “Exchanging Poems”, Key words.",
                   "[1]～[196].", ""):
            t = json.loads(json.dumps(GOOD_TREE))
            t["structure"][0]["summary"] = ok
            self.assertEqual(self.errs(t), [], ok)

    def test_unreadable_and_empty(self):
        self.assertTrue(cs.check_tree(self.write("t.json", "{깨짐"), TEXT)[0])
        self.assertTrue(self.errs({"structure": []}))


class PageTest(Base):
    def errs(self, content, tree=GOOD_TREE):
        p = self.write("n.md", content)
        t = self.write("t.json", tree) if tree is not None else None
        return cs.check_page(p, TEXT, t)

    def test_good_page_passes(self):
        # 이미지 링크·줄끝 하이픈·PUA 서명 괄호가 끼인 추출본에서도 지면 그대로 옮긴 인용은 통과한다.
        self.assertEqual(self.errs(page()), [])

    def test_missing_section_and_key(self):
        e = self.errs(page().replace("## 학술 대화\n", "").replace('sources: ["raw/a.pdf"]\n', ""))
        self.assertTrue(any("## 학술 대화" in x for x in e))
        self.assertTrue(any("sources" in x for x in e))

    def test_map_rows_must_equal_nodes_when_tree_given(self):
        e = self.errs(page(map_=MAP.rsplit("\n", 1)[0]))
        self.assertTrue(any("논증 지도 행 2개" in x for x in e))
        self.assertEqual(self.errs(page(map_=MAP.rsplit("\n", 1)[0]), tree=None), [])

    def test_quote_not_in_text(self):
        e = self.errs(page(quotes="> 없는 문장이다. (PDF p.2)"))
        self.assertTrue(any("글자 그대로 없음" in x for x in e))

    def test_quote_on_wrong_page(self):
        e = self.errs(page(quotes="> 文者 貫道之器也 (PDF p.3)"))
        self.assertTrue(any("p.3" in x for x in e))

    def test_quote_without_page(self):
        e = self.errs(page(quotes="> 文者 貫道之器也"))
        self.assertTrue(any("(PDF p.N)" in x for x in e))

    def test_straight_quote_and_ascii_tilde_in_body(self):
        e = self.errs(page(extra='저자는 "근대"라 했다. 1～3이 아니라 1~3.\n'))
        self.assertTrue(any("직선 따옴표" in x for x in e))
        self.assertTrue(any("ASCII 물결표" in x for x in e))

    def test_inline_code_and_quote_lines_exempt(self):
        self.assertEqual(self.errs(page(extra='표기 `"x"~y`는 코드다.\n')), [])

    def test_mermaid_rules(self):
        e = self.errs(page(mermaid="flowchart TD\n  Q[물음] -- 전제 --> A[\"주장\"]"))
        self.assertTrue(any("감싸이지" in x for x in e))
        self.assertTrue(any("-->|라벨|" in x for x in e))
        self.assertTrue(any("flowchart TD" in x for x in self.errs(page(mermaid='graph LR\n  A["가"]'))))


class CliTest(Base):
    def run_cli(self, *args):
        r = subprocess.run([sys.executable, str(SCRIPTS / "check_structure.py"), *args],
                           capture_output=True, text=True, encoding="utf-8")
        return r.returncode, r.stdout

    def test_exit_codes(self):
        text = self.write("x.md", TEXT)
        good = self.write("t.json", GOOD_TREE)
        self.assertEqual(self.run_cli("tree", str(good), "--text", str(text))[0], 0)
        bad = self.write("b.json", {"structure": [node("0001", "Ⅰ", 1, 1)]})
        code, out = self.run_cli("tree", str(bad), "--text", str(text))
        self.assertEqual(code, 1)
        self.assertIn("오류 1", out)
        note = self.write("n.md", page())
        self.assertEqual(self.run_cli("page", str(note), "--text", str(text), "--tree", str(good))[0], 0)


if __name__ == "__main__":
    unittest.main()
