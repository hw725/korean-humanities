#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kci_ingest.py - KCI 서지정보·초록 수집기 (corpus JSONL / 선택적 vault 노트 적재).

[korean-humanities trends 벤더링본] 개인 경로 기본값을 전부 환경변수+cwd 폴백으로
교체했다. 동향(trends) 용도는 --dry-run --corpus-out 경로만 쓰며 vault 적재는
--inbox를 명시한 사용자만 켠다. 원본: 개인 corpus pipeline.

용법:
  python scripts/kci_ingest.py --url "https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART003019392"
  python scripts/kci_ingest.py --query "蒙求" --max 20 --since 2020
  python scripts/kci_ingest.py --journal "민족문화" --since 2010 --per-journal-max 50
  python scripts/kci_ingest.py --journal-profile config/kci_korean_studies_journals.json --since 2010
  python scripts/kci_ingest.py --html saved_kci_article.html
  python scripts/kci_ingest.py --html saved_kci_article.html --download-pdf
  python scripts/kci_ingest.py --query "蒙求" --dry-run

원칙:
  - 기본값은 본문 PDF를 확보하지 않고 서지와 초록만 Layer 2 abstract-only로 기록한다.
  - classify_and_route.py를 거치지 않는 독립 ingest 경로다.
  - .queue/kci-seen.jsonl로 dedupe, .queue/kci-pending.jsonl로 처리 로그를 남긴다.
  - User-Agent, robots.txt 확인, 요청 간 sleep을 적용한다.
  - robots.txt가 live fetch를 막으면 --html로 수동 저장한 상세 페이지를 처리한다.
  - --download-pdf 사용 시 PDF 후보를 PAPERS_ROOT/_global_inbox에 넣어 classify_and_route.py부터 태운다.
  - 원문 확보는 KCI/KOAJ의 KCI_FI 다운로드 후보만 사용한다.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import logging
import os
import re
import sys

# CJK Text Contract 1-b: Windows cp949 콘솔에서 한글 출력이 UnicodeEncodeError로 죽는 것 차단
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

import time
import unicodedata
import urllib.parse
import urllib.request
import urllib.robotparser
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional


# 작업 루트: KCI_TRENDS_DIR 환경변수, 없으면 cwd의 kci-trends/
DEFAULT_PIPELINE = Path(os.environ.get("KCI_TRENDS_DIR", "kci-trends"))
DEFAULT_QUEUE = DEFAULT_PIPELINE / ".queue"
DEFAULT_LOGS = DEFAULT_PIPELINE / "logs"
# 저널 프로파일: 스킬 동봉 기본값 — 사용자는 사본을 만들어 자기 분야로 편집한다
DEFAULT_JOURNAL_PROFILE = Path(__file__).resolve().parent.parent / "assets" / "kci_korean_studies_journals.json"
# vault 적재는 선택 기능 — KCI_INGEST_INBOX 환경변수 또는 --inbox 인자로만 켠다
DEFAULT_INBOX = Path(os.environ["KCI_INGEST_INBOX"]) if os.environ.get("KCI_INGEST_INBOX") else (DEFAULT_PIPELINE / "inbox")
DEFAULT_PAPERS_ROOT = Path(os.environ.get("PAPERS_ROOT", str(DEFAULT_PIPELINE / "papers")))
DEFAULT_GLOBAL_INBOX = DEFAULT_PAPERS_ROOT / "_global_inbox"

KCI_BASE = "https://www.kci.go.kr"
KCI_SEARCH_URL = f"{KCI_BASE}/kciportal/po/search/poArtiSearList.kci"
KCI_ARTICLE_URL = f"{KCI_BASE}/kciportal/ci/sereArticleSearch/ciSereArtiView.kci"
KCI_LANDING_URL = f"{KCI_BASE}/kciportal/landing/article.kci"
KCI_PDF_DOWNLOAD_URL = f"{KCI_BASE}/kciportal/ci/sereArticleSearch/ciSereArtiOrteServHistIFrame.kci"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "kci_ingest/0.1; personal research KCI/KOAJ ingest"
)

_ARTI_ID_RE = re.compile(r"\bART\d{9}\b")
def _contains_hanja(text: str) -> bool:
    """한자 포함 여부 — upstream 문자클래스 [㐀-鿿]는 확장 B(U+20000+)를 놓쳐 교체."""
    return any(0x3400 <= ord(c) <= 0x9FFF or 0xF900 <= ord(c) <= 0xFAFF
               or 0x20000 <= ord(c) <= 0x2FA1F for c in text)
_TAG_RE = re.compile(r"<[^>]+>")
_ASCII_TAG_RE = re.compile(r"</?[A-Za-z][^>]*>")


@dataclass
class KCIArticle:
    kci_id: str
    url: str
    title: str = ""
    title_en: str = ""
    authors: list[str] = field(default_factory=list)
    year: str = ""
    journal: str = ""
    volume: str = ""
    issue: str = ""
    pages: str = ""
    doi: str = ""
    issn: str = ""
    publisher: str = ""
    abstract: str = ""
    abstract_en: str = ""
    keywords: list[str] = field(default_factory=list)
    subject: str = ""
    citation_count: Optional[int] = None
    sere_id: str = ""
    publisher_id: str = ""
    pdf_url: str = ""
    pdf_file_id: str = ""
    pdf_source: str = ""
    nfc_applied: bool = False
    local_html: Optional[str] = None
    journal_profile: dict[str, object] = field(default_factory=dict)


@dataclass
class IngestResult:
    timestamp: str
    kci_id: str
    title: str
    url: str
    action: str
    query: Optional[str] = None
    year: str = ""
    out_path: Optional[str] = None
    pdf_action: Optional[str] = None
    pdf_path: Optional[str] = None
    pdf_url: Optional[str] = None
    pdf_source: Optional[str] = None
    nfc_applied: bool = False
    error: Optional[str] = None


class HTTPClient:
    def __init__(self, sleep_seconds: float, respect_robots: bool = True) -> None:
        self.sleep_seconds = sleep_seconds
        self.respect_robots = respect_robots
        self._last_request = 0.0
        self._robots_cache: dict[str, urllib.robotparser.RobotFileParser] = {}

    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.sleep_seconds:
            time.sleep(self.sleep_seconds - elapsed)

    def _headers(self, referer: Optional[str] = None) -> dict[str, str]:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.7,en;q=0.5",
        }
        if referer:
            headers["Referer"] = referer
        return headers

    def _robots_for(self, url: str) -> urllib.robotparser.RobotFileParser:
        parsed = urllib.parse.urlparse(url)
        root = f"{parsed.scheme}://{parsed.netloc}"
        if root in self._robots_cache:
            return self._robots_cache[root]

        rp = urllib.robotparser.RobotFileParser()
        robots_url = urllib.parse.urljoin(root, "/robots.txt")
        try:
            req = urllib.request.Request(robots_url, headers=self._headers())
            with urllib.request.urlopen(req, timeout=10) as resp:
                lines = resp.read().decode("utf-8", errors="ignore").splitlines()
            rp.parse(lines)
            logging.info("robots.txt 확인: %s", robots_url)
        except Exception as e:
            logging.warning("robots.txt 확인 실패. 보수적 rate limit만 적용: %s", e)
            rp.parse([])
        self._robots_cache[root] = rp
        return rp

    def _check_robots(self, url: str) -> None:
        if not self.respect_robots:
            return
        rp = self._robots_for(url)
        if not rp.can_fetch(USER_AGENT, url):
            raise PermissionError(f"robots.txt disallow: {url}")

    def get(self, url: str, referer: Optional[str] = None) -> str:
        self._check_robots(url)
        self._wait()
        req = urllib.request.Request(url, headers=self._headers(referer))
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
        self._last_request = time.monotonic()
        return raw.decode(charset, errors="replace")

    def post(self, url: str, data: dict[str, str], referer: Optional[str] = None) -> str:
        self._check_robots(url)
        self._wait()
        encoded = urllib.parse.urlencode(data).encode("utf-8")
        headers = self._headers(referer)
        headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        headers["X-Requested-With"] = "XMLHttpRequest"
        req = urllib.request.Request(url, data=encoded, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
        self._last_request = time.monotonic()
        return raw.decode(charset, errors="replace")

    def get_bytes(self, url: str, referer: Optional[str] = None) -> tuple[bytes, str]:
        self._check_robots(url)
        self._wait()
        req = urllib.request.Request(url, headers=self._headers(referer))
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            content_type = resp.headers.get("Content-Type", "")
        self._last_request = time.monotonic()
        return raw, content_type


def canonical_article_url(kci_id: str) -> str:
    return f"{KCI_ARTICLE_URL}?sereArticleSearchBean.artiId={kci_id}"


def kci_pdf_download_url(kci_id: str, file_id: str) -> str:
    return KCI_PDF_DOWNLOAD_URL + "?" + urllib.parse.urlencode({
        "sereArticleSearchBean.artiId": kci_id,
        "sereArticleSearchBean.orteFileId": file_id,
    })


def canonical_landing_url(kci_id: str) -> str:
    return f"{KCI_LANDING_URL}?arti_id={kci_id}"


def extract_kci_id(value: str) -> Optional[str]:
    parsed = urllib.parse.urlparse(value)
    qs = urllib.parse.parse_qs(parsed.query)
    for key in ("sereArticleSearchBean.artiId", "artiId", "arti_id"):
        if key in qs and qs[key]:
            found = _ARTI_ID_RE.search(qs[key][0])
            if found:
                return found.group(0)
    found = _ARTI_ID_RE.search(value)
    return found.group(0) if found else None


def clean_text(value: str) -> str:
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = _TAG_RE.sub(" ", value)
    value = html.unescape(value)
    value = html.unescape(value)
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = _ASCII_TAG_RE.sub(" ", value)
    value = value.replace("\xa0", " ")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n[ \t]+", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def extract_element_by_id(page: str, element_id: str) -> str:
    pattern = re.compile(
        rf"<(?P<tag>[a-zA-Z0-9]+)\b[^>]*\bid=[\"']{re.escape(element_id)}[\"'][^>]*>"
        rf"(?P<body>.*?)</(?P=tag)>",
        re.S | re.I,
    )
    match = pattern.search(page)
    if not match:
        return ""
    return clean_text(match.group("body"))


def parse_hidden_inputs(row_html: str) -> dict[str, str]:
    out: dict[str, str] = {}
    pattern = re.compile(
        r"<input\b[^>]*\bname=[\"']([^\"']+)[\"'][^>]*\bvalue=[\"'](.*?)[\"'][^>]*>",
        re.S | re.I,
    )
    for name, value in pattern.findall(row_html):
        out[name] = clean_text(value)
    return out


def parse_int(value: str) -> Optional[int]:
    value = clean_text(value)
    if not value:
        return None
    match = re.search(r"\d+", value)
    return int(match.group(0)) if match else None


def parse_search_results(
    page: str,
    since: Optional[int],
    until: Optional[int],
    limit: int,
) -> list[KCIArticle]:
    articles: list[KCIArticle] = []
    seen: set[str] = set()

    for row_match in re.finditer(r"<tr\b[^>]*>(.*?)</tr>", page, flags=re.S | re.I):
        row = row_match.group(1)
        fields = parse_hidden_inputs(row)
        kci_id = fields.get("R_SYST_LOCA_ID1") or extract_kci_id(row) or ""
        if not kci_id or kci_id in seen:
            continue

        year = fields.get("R_PUBI_DT", "")[:4]
        if since and year.isdigit() and int(year) < since:
            continue
        if until and year.isdigit() and int(year) > until:
            continue

        st_pg = fields.get("R_ST_PG", "")
        end_pg = fields.get("R_END_PG", "")
        pages = f"{st_pg}-{end_pg}" if st_pg and end_pg else st_pg or end_pg
        authors = split_authors(fields.get("R_CRET_NM", ""))
        article = KCIArticle(
            kci_id=kci_id,
            url=canonical_article_url(kci_id),
            title=fields.get("R_INDE_TITL", ""),
            authors=authors,
            year=year,
            journal=fields.get("R_SERE_NM", ""),
            volume=fields.get("R_VOL", ""),
            issue=fields.get("R_ISSE", ""),
            pages=pages,
            publisher=fields.get("R_PUBI_INSI_NM", ""),
            subject=fields.get("R_MAJOR", ""),
            citation_count=parse_int(fields.get("R_CITATED_IDX", "")),
            sere_id=fields.get("R_SERE_ID", ""),
            publisher_id=fields.get("R_PUBI_INSI_ID", ""),
        )
        articles.append(normalize_article(article))
        seen.add(kci_id)
        if len(articles) >= limit:
            return articles

    if articles:
        return articles

    for kci_id in _ARTI_ID_RE.findall(page):
        if kci_id in seen:
            continue
        articles.append(KCIArticle(kci_id=kci_id, url=canonical_article_url(kci_id)))
        seen.add(kci_id)
        if len(articles) >= limit:
            break
    return articles


def extract_pdf_info(page: str, kci_id: str) -> tuple[str, str]:
    direct_patterns = [
        r"href=[\"']([^\"']*(?:articlePdf|\.pdf)(?:\?[^\"']*)?)[\"']",
        r"(https?://[^\"'\s<>]+(?:articlePdf|\.pdf)[^\"'\s<>]*)",
    ]
    for pattern in direct_patterns:
        for match in re.finditer(pattern, page, flags=re.I):
            url = html.unescape(match.group(1))
            if "kci_data_filed.pdf" in url:
                continue
            return urllib.parse.urljoin(KCI_BASE, url), ""

    for match in re.finditer(r"fncDown\(\s*[\"'](KCI_FI[^\"']+)[\"']\s*\)", page):
        file_id = match.group(1)
        return kci_pdf_download_url(kci_id, file_id), file_id

    pattern = r"fncDown\(\s*[\"'](ART\d{9})[\"']\s*,\s*[\"'](KCI_FI[^\"']+)[\"']\s*\)"
    for match in re.finditer(pattern, page):
        arti_id, file_id = match.groups()
        if arti_id == kci_id:
            return kci_pdf_download_url(kci_id, file_id), file_id
    return "", ""


def split_authors(value: str) -> list[str]:
    value = clean_text(value)
    if not value:
        return []
    parts = re.split(r"\s+and\s+|[,;]\s*|ㆍ|·", value)
    return [p.strip() for p in parts if p.strip()]


def split_keywords(value: str) -> list[str]:
    value = clean_text(value)
    if not value:
        return []
    return [p.strip() for p in re.split(r",|;|ㆍ|·", value) if p.strip()]


def parse_ris(text: str) -> dict[str, list[str]]:
    fields: dict[str, list[str]] = {}
    current: Optional[str] = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        match = re.match(r"^([A-Z0-9]{2})\s+-\s*(.*)$", line)
        if match:
            current = match.group(1)
            fields.setdefault(current, []).append(match.group(2).strip())
        elif current and fields.get(current):
            fields[current][-1] = (fields[current][-1] + "\n" + line).strip()
    return fields


def first_field(fields: dict[str, list[str]], *keys: str) -> str:
    for key in keys:
        values = fields.get(key) or []
        for value in values:
            if value.strip():
                return clean_text(value)
    return ""


def article_from_ris(kci_id: str, url: str, ris_text: str) -> KCIArticle:
    fields = parse_ris(ris_text)
    start_page = first_field(fields, "SP")
    end_page = first_field(fields, "EP")
    pages = f"{start_page}-{end_page}" if start_page and end_page else start_page or end_page
    return KCIArticle(
        kci_id=kci_id,
        url=url,
        title=first_field(fields, "TI"),
        authors=[clean_text(v) for v in fields.get("AU", []) if clean_text(v)],
        year=first_field(fields, "PY"),
        journal=first_field(fields, "T2", "JO"),
        volume=first_field(fields, "VL"),
        issue=first_field(fields, "IS"),
        pages=pages,
        doi=first_field(fields, "DO"),
        issn=first_field(fields, "SN"),
        publisher=first_field(fields, "PB"),
        abstract=first_field(fields, "AB"),
        keywords=split_keywords(first_field(fields, "KW")),
    )


def merge_article(primary: KCIArticle, fallback: Optional[KCIArticle]) -> KCIArticle:
    if fallback is None:
        return primary
    for field_name in (
        "title",
        "title_en",
        "year",
        "journal",
        "volume",
        "issue",
        "pages",
        "doi",
        "issn",
        "publisher",
        "abstract",
        "abstract_en",
        "subject",
        "sere_id",
        "publisher_id",
        "pdf_url",
        "pdf_file_id",
        "pdf_source",
    ):
        if not getattr(primary, field_name) and getattr(fallback, field_name):
            setattr(primary, field_name, getattr(fallback, field_name))
    if not primary.authors and fallback.authors:
        primary.authors = fallback.authors
    if not primary.keywords and fallback.keywords:
        primary.keywords = fallback.keywords
    if primary.citation_count is None and fallback.citation_count is not None:
        primary.citation_count = fallback.citation_count
    if not primary.journal_profile and fallback.journal_profile:
        primary.journal_profile = fallback.journal_profile
    primary.nfc_applied = primary.nfc_applied or fallback.nfc_applied
    return primary


def normalize_article(article: KCIArticle) -> KCIArticle:
    before = json.dumps(asdict(article), ensure_ascii=False, sort_keys=True)
    for field_name in (
        "kci_id",
        "url",
        "title",
        "title_en",
        "year",
        "journal",
        "volume",
        "issue",
        "pages",
        "doi",
        "issn",
        "publisher",
        "abstract",
        "abstract_en",
        "subject",
        "sere_id",
        "publisher_id",
        "pdf_url",
        "pdf_file_id",
        "pdf_source",
    ):
        setattr(article, field_name, unicodedata.normalize("NFC", getattr(article, field_name)))
    article.authors = [unicodedata.normalize("NFC", a) for a in article.authors]
    article.keywords = [unicodedata.normalize("NFC", k) for k in article.keywords]
    after = json.dumps(asdict(article), ensure_ascii=False, sort_keys=True)
    combined = after
    article.nfc_applied = article.nfc_applied or before != after or bool(_contains_hanja(combined))
    return article


def article_from_page(page: str, kci_id: str, url: str, stub: Optional[KCIArticle] = None) -> KCIArticle:
    ris_text = extract_element_by_id(page, "RIS")
    article = article_from_ris(kci_id, url, ris_text) if ris_text else KCIArticle(kci_id=kci_id, url=url)

    kor_abst = extract_element_by_id(page, "korAbst")
    eng_abst = extract_element_by_id(page, "engAbst")
    if kor_abst:
        article.abstract = kor_abst
    if eng_abst:
        article.abstract_en = eng_abst
    pdf_url, pdf_file_id = extract_pdf_info(page, kci_id)
    article.pdf_url = pdf_url
    article.pdf_file_id = pdf_file_id
    if pdf_url:
        article.pdf_source = "KCI/KOAJ" if "landing/article.kci" in page else "KCI"

    article = merge_article(article, stub)
    return normalize_article(article)


def fetch_article(client: HTTPClient, kci_id: str, stub: Optional[KCIArticle] = None) -> KCIArticle:
    url = canonical_article_url(kci_id)
    page = client.get(url, referer=KCI_SEARCH_URL)
    return article_from_page(page, kci_id, url, stub)


def read_article_html(path: Path) -> KCIArticle:
    page = path.read_text(encoding="utf-8", errors="replace")
    kci_id = extract_kci_id(page) or extract_kci_id(path.name)
    if not kci_id:
        raise ValueError(f"KCI 논문 ID를 찾을 수 없음: {path}")
    stub = KCIArticle(kci_id=kci_id, url=canonical_article_url(kci_id), local_html=str(path))
    article = article_from_page(page, kci_id, canonical_article_url(kci_id), stub)
    article.local_html = str(path)
    return article


def search_kci(
    client: HTTPClient,
    query: str,
    max_results: int,
    since: Optional[int],
    condition: str,
    until: Optional[int] = None,
) -> list[KCIArticle]:
    docs_count = str(min(max(max_results, 1), 300))
    data = {
        "poSearchBean.searType": "thesis",
        "poSearchBean.conditionList": condition,
        "poSearchBean.keywordList": query,
        "poSearchBean.startPg": "1",
        "poSearchBean.docsCount": docs_count,
        "poSearchBean.sortName": "PUBI_DT",
        "poSearchBean.sortDir": "desc",
        "poSearchBean.isAdvanceSearch": "false",
        "poSearchBean.resultForm": "Y",
    }
    if since:
        data["poSearchBean.pubiStYr"] = str(since)
    if since or until:
        data["poSearchBean.pubiEndYr"] = str(until or dt.date.today().year)
    page = client.post(KCI_SEARCH_URL, data)
    return parse_search_results(page, since, until, max_results)


def load_journal_profile(
    path: Path,
    priorities: Optional[set[int]] = None,
    fields: Optional[set[str]] = None,
) -> list[dict[str, object]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    journals = data.get("journals")
    if not isinstance(journals, list):
        raise ValueError(f"journal profile에 journals 배열이 없음: {path}")

    out: list[dict[str, object]] = []
    seen: set[str] = set()
    for item in journals:
        if not isinstance(item, dict):
            continue
        name = clean_text(str(item.get("name") or ""))
        if not name or name in seen:
            continue
        priority_raw = item.get("priority", 999)
        try:
            priority = int(priority_raw)
        except (TypeError, ValueError):
            priority = 999
        field_name = clean_text(str(item.get("field") or ""))
        if priorities and priority not in priorities:
            continue
        if fields and field_name not in fields:
            continue
        out.append({**item, "name": name, "priority": priority, "field": field_name})
        seen.add(name)
    return out


def journal_match_key(value: str) -> str:
    value = unicodedata.normalize("NFC", clean_text(value))
    return re.sub(r"[\s\W_]+", "", value, flags=re.UNICODE).lower()


def journal_accepted_keys(name: str, aliases: Optional[list[str]] = None) -> set[str]:
    values = [name, *(aliases or [])]
    return {journal_match_key(value) for value in values if journal_match_key(value)}


def journal_candidate_keys(value: str) -> set[str]:
    stripped = re.sub(r"\s*[\(\（][^\)\）]+[\)\）]\s*", "", value or "")
    return {journal_match_key(value), journal_match_key(stripped)} - {""}


def sere_id_key(value: object) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def profile_allows_article(profile_item: Optional[dict[str, object]], article: KCIArticle) -> bool:
    if not profile_item:
        return True

    expected_sere_id = sere_id_key(profile_item.get("kci_sere_id"))
    if expected_sere_id:
        article_sere_id = sere_id_key(article.sere_id)
        return bool(article_sere_id and article_sere_id == expected_sere_id)

    publisher_aliases_raw = profile_item.get("publisher_aliases") or []
    if isinstance(publisher_aliases_raw, str):
        publisher_aliases_raw = [publisher_aliases_raw]
    publisher_aliases = [profile_item.get("publisher"), *publisher_aliases_raw]
    accepted_publishers = {journal_match_key(str(value)) for value in publisher_aliases if value}
    if accepted_publishers and article.publisher:
        article_publisher = journal_match_key(article.publisher)
        return any(key in article_publisher or article_publisher in key for key in accepted_publishers)
    return True


def filter_journal_hits(
    articles: list[KCIArticle],
    name: str,
    aliases: Optional[list[str]] = None,
    limit: Optional[int] = None,
    profile_item: Optional[dict[str, object]] = None,
) -> list[KCIArticle]:
    accepted = journal_accepted_keys(name, aliases)
    out: list[KCIArticle] = []
    seen: set[str] = set()
    for article in articles:
        if not (journal_candidate_keys(article.journal) & accepted):
            continue
        if not profile_allows_article(profile_item, article):
            continue
        if article.kci_id in seen:
            continue
        if profile_item:
            article.journal_profile = profile_item
        out.append(article)
        seen.add(article.kci_id)
        if limit and len(out) >= limit:
            break
    return out


def search_kci_journal(
    client: HTTPClient,
    name: str,
    aliases: Optional[list[str]],
    per_journal_max: int,
    scan_max: int,
    since: Optional[int],
    until: Optional[int] = None,
    profile_item: Optional[dict[str, object]] = None,
) -> list[KCIArticle]:
    queries = [name, *(aliases or [])]
    collected: list[KCIArticle] = []
    seen: set[str] = set()
    for query in queries:
        hits = search_kci(client, query, scan_max, since, "SERE_NM", until=until)
        for article in filter_journal_hits(hits, name, aliases, profile_item=profile_item):
            if article.kci_id in seen:
                continue
            if profile_item:
                article.journal_profile = profile_item
            collected.append(article)
            seen.add(article.kci_id)
            if len(collected) >= per_journal_max:
                return collected
    return collected


def parse_priority_filter(values: Optional[list[str]]) -> Optional[set[int]]:
    if not values:
        return None
    out: set[int] = set()
    for value in values:
        for part in re.split(r"[, ]+", value.strip()):
            if part:
                out.add(int(part))
    return out


def load_seen(queue_dir: Path) -> set[str]:
    seen_path = queue_dir / "kci-seen.jsonl"
    if not seen_path.exists():
        return set()
    out: set[str] = set()
    with seen_path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if data.get("kci_id"):
                out.add(data["kci_id"])
            if data.get("url"):
                out.add(data["url"])
    return out


def mark_seen(queue_dir: Path, article: KCIArticle) -> None:
    queue_dir.mkdir(parents=True, exist_ok=True)
    with (queue_dir / "kci-seen.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "kci_id": article.kci_id,
            "url": article.url,
            "title": article.title,
            "seen_at": dt.datetime.now().isoformat(timespec="seconds"),
        }, ensure_ascii=False) + "\n")


def append_log(queue_dir: Path, result: IngestResult) -> None:
    queue_dir.mkdir(parents=True, exist_ok=True)
    with (queue_dir / "kci-pending.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(result), ensure_ascii=False) + "\n")


def append_corpus(corpus_out: Optional[Path], article: KCIArticle, result: IngestResult, query: Optional[str]) -> None:
    if not corpus_out:
        return
    corpus_out.parent.mkdir(parents=True, exist_ok=True)
    record = asdict(article)
    record.update({
        "collected_at": result.timestamp,
        "ingest_action": result.action,
        "query": query,
        "out_path": result.out_path,
        "pdf_action": result.pdf_action,
        "pdf_path": result.pdf_path,
        "error": result.error,
    })
    with corpus_out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def unique_pdf_path(target_dir: Path, article: KCIArticle) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    author = article.authors[0] if article.authors else "unknown-author"
    title = article.title or article.kci_id
    year = article.year or "unknown-year"
    stem = slugify_filename(f"{author}_{title}_{year}", maxlen=140)
    base = target_dir / f"{stem}.pdf"
    if not base.exists():
        return base
    for idx in range(2, 1000):
        candidate = target_dir / f"{stem}_{idx}.pdf"
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"PDF 파일명 충돌이 너무 많음: {base}")


def slugify_filename(text: str, maxlen: int = 140) -> str:
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace(" ", "-")
    text = re.sub(r"_+", "_", text)
    return text[:maxlen].strip(" ._-") or "untitled"


def download_pdf(
    article: KCIArticle,
    client: HTTPClient,
    target_dir: Path,
    dry_run: bool,
) -> tuple[str, Optional[Path], str]:
    if not article.pdf_url:
        return "no-pdf-link", None, ""
    target = unique_pdf_path(target_dir, article)
    if dry_run:
        return "dry-run", target, article.pdf_url

    payload, content_type = client.get_bytes(article.pdf_url, referer=article.url)
    if not payload.startswith(b"%PDF") and "pdf" not in content_type.lower():
        raise ValueError(f"PDF 응답이 아님: content-type={content_type or 'unknown'} url={article.pdf_url}")
    target.write_bytes(payload)
    return "downloaded", target, article.pdf_url


def slugify(text: str, maxlen: int = 60) -> str:
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", "", text)
    # [local divergence] 문자클래스 범위 대신 코드포인트 판별 — 옛한글·한자 확장 B 커버
    def _keep(c):
        o = ord(c)
        return (c.isalnum() or c in "_ \t" or c.isspace()
                or 0xAC00 <= o <= 0xD7A3 or 0x1100 <= o <= 0x11FF or 0x3130 <= o <= 0x318F
                or 0xA960 <= o <= 0xA97F or 0xD7B0 <= o <= 0xD7FF
                or 0x3400 <= o <= 0x9FFF or 0xF900 <= o <= 0xFAFF or 0x20000 <= o <= 0x2FA1F
                or 0x3040 <= o <= 0x30FF or c in "ー々〆〤")
    text = "".join(c for c in text if _keep(c))
    text = re.sub(r"\s+", "-", text).strip("-_ ")
    return text[:maxlen] or "untitled"


def unique_note_path(inbox: Path, article: KCIArticle) -> Path:
    slug = slugify(article.title or article.kci_id)
    base = inbox / f"{dt.date.today().isoformat()}_kci_{slug}.md"
    if not base.exists():
        return base
    with_id = inbox / f"{dt.date.today().isoformat()}_kci_{slug}_{article.kci_id}.md"
    if not with_id.exists():
        return with_id
    stem = with_id.stem
    for idx in range(2, 1000):
        candidate = inbox / f"{stem}_{idx}.md"
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"노트 파일명 충돌이 너무 많음: {with_id}")


def yaml_scalar(value: str) -> str:
    return json.dumps(value or "", ensure_ascii=False)


def yaml_list(items: list[str]) -> list[str]:
    return [f"  - {yaml_scalar(item)}" for item in items]


def curly_quotes(text: str) -> str:
    out: list[str] = []
    double_open = True
    single_open = True
    for idx, ch in enumerate(text):
        if ch == '"':
            out.append("“" if double_open else "”")
            double_open = not double_open
        elif ch == "'":
            prev_ch = text[idx - 1] if idx > 0 else ""
            next_ch = text[idx + 1] if idx + 1 < len(text) else ""
            if prev_ch.isalnum() and next_ch.isalnum():
                out.append("’")
            else:
                out.append("‘" if single_open else "’")
                single_open = not single_open
        else:
            out.append(ch)
    return "".join(out)


def display_value(value: str) -> str:
    value = clean_text(value)
    return curly_quotes(value) if value else "-"


def write_note(article: KCIArticle, inbox: Path) -> Path:
    inbox.mkdir(parents=True, exist_ok=True)
    note_path = unique_note_path(inbox, article)

    front = [
        "---",
        "type: source",
        f"title: {yaml_scalar(article.title or article.kci_id)}",
        f"primary_vault: {os.environ.get('KCI_VAULT_NAME', 'vault')}",
        "source_db: KCI",
        f"source_url: {yaml_scalar(article.url)}",
        f"source_path: {yaml_scalar(article.url)}",
        f"kci_id: {yaml_scalar(article.kci_id)}",
        f"doi: {yaml_scalar(article.doi)}",
        f"year: {yaml_scalar(article.year)}",
        f"journal: {yaml_scalar(article.journal)}",
        f"volume: {yaml_scalar(article.volume)}",
        f"issue: {yaml_scalar(article.issue)}",
        f"pages: {yaml_scalar(article.pages)}",
        f"issn: {yaml_scalar(article.issn)}",
        f"publisher: {yaml_scalar(article.publisher)}",
        f"pdf_source_url: {yaml_scalar(article.pdf_url)}",
        f"pdf_source: {yaml_scalar(article.pdf_source)}",
        "verification_layer: Layer 2",
        "verification_scope: abstract-only",
        "pdf_status: not-acquired",
        f"nfc_applied: {str(article.nfc_applied).lower()}",
        f"arrived: {dt.date.today().isoformat()}",
        "status: pending-review",
        "tags:",
        "  - inbox-auto",
        "  - kci",
        "  - 학술서지",
        "---",
        "",
    ]
    if article.authors:
        front[9:9] = ["authors:", *yaml_list(article.authors)]
    else:
        front[9:9] = ["authors: []"]

    title = display_value(article.title or article.kci_id)
    authors = ", ".join(display_value(a) for a in article.authors) if article.authors else "-"
    keywords = ", ".join(display_value(k) for k in article.keywords) if article.keywords else "-"
    doi = display_value(article.doi)
    abstract = display_value(article.abstract) if article.abstract else "_KCI 상세 페이지에 초록 없음._"
    abstract_en = display_value(article.abstract_en) if article.abstract_en else ""

    body = "\n".join(front)
    body += f"# {title}\n\n"
    body += (
        "> KCI 서지와 초록만 적재한 Layer 2 보조 자료입니다. "
        "본문 PDF 확보 전에는 본문 인용이나 논증 근거로 승격하지 않습니다.\n"
    )
    body += f"> KCI: <{article.url}>\n"
    if article.doi:
        body += f"> DOI: {doi}\n"
    body += "\n## 서지\n\n"
    body += "| 항목 | 값 |\n|---|---|\n"
    body += f"| 저자 | {authors} |\n"
    body += f"| 연도 | {display_value(article.year)} |\n"
    body += f"| 학술지 | {display_value(article.journal)} |\n"
    volume_issue = display_value(article.volume)
    if article.issue:
        volume_issue = f"{volume_issue}({display_value(article.issue)})"
    body += f"| 권호 | {volume_issue} |\n"
    body += f"| 페이지 | {display_value(article.pages)} |\n"
    body += f"| 발행기관 | {display_value(article.publisher)} |\n"
    body += f"| KCI ID | {display_value(article.kci_id)} |\n"
    body += f"| DOI | {doi} |\n"
    body += f"| 키워드 | {keywords} |\n\n"
    body += "## 초록\n\n"
    body += abstract + "\n"
    if abstract_en:
        body += "\n## 영문 초록\n\n"
        body += abstract_en + "\n"
    body += "\n## 검토 후 액션\n\n"
    body += "- [ ] PDF 원문 확보\n"
    body += "- [ ] 원문 확인 후 `verification_layer`를 Layer 1로 승격할지 판단\n"
    body += "- [ ] 필요한 경우 `_논문index/`로 이동\n"

    note_path.write_text(body, encoding="utf-8")
    return note_path


def process_article(
    article_stub: KCIArticle,
    client: HTTPClient,
    inbox: Path,
    queue_dir: Path,
    pdf_output_dir: Path,
    corpus_out: Optional[Path],
    dry_run: bool,
    download_pdf_enabled: bool,
    seen: set[str],
    query: Optional[str],
) -> IngestResult:
    ts = dt.datetime.now().isoformat(timespec="seconds")
    if article_stub.kci_id in seen or article_stub.url in seen:
        result = IngestResult(
            timestamp=ts,
            kci_id=article_stub.kci_id,
            title=article_stub.title,
            url=article_stub.url,
            action="skipped-dup",
            query=query,
            year=article_stub.year,
            pdf_url=article_stub.pdf_url or None,
        )
        append_log(queue_dir, result)
        return result

    try:
        if article_stub.local_html:
            article = read_article_html(Path(article_stub.local_html))
            article = merge_article(article, article_stub)
        else:
            article = fetch_article(client, article_stub.kci_id, article_stub)
        pdf_action: Optional[str] = None
        pdf_path: Optional[Path] = None
        pdf_url: Optional[str] = article.pdf_url or None
        if download_pdf_enabled:
            pdf_action, pdf_path, pdf_url_value = download_pdf(article, client, pdf_output_dir, dry_run=True)
            pdf_url = pdf_url_value or pdf_url
        if dry_run:
            result = IngestResult(
                timestamp=ts,
                kci_id=article.kci_id,
                title=article.title,
                url=article.url,
                action="dry-run",
                query=query,
                year=article.year,
                pdf_action=pdf_action,
                pdf_path=str(pdf_path) if pdf_path else None,
                pdf_url=pdf_url,
                pdf_source=article.pdf_source or None,
                nfc_applied=article.nfc_applied,
            )
            append_log(queue_dir, result)
            append_corpus(corpus_out, article, result, query)
            return result

        out_path = write_note(article, inbox)
        if download_pdf_enabled:
            pdf_action, pdf_path, pdf_url_value = download_pdf(article, client, pdf_output_dir, dry_run=False)
            pdf_url = pdf_url_value or pdf_url
        mark_seen(queue_dir, article)
        seen.add(article.kci_id)
        seen.add(article.url)
        result = IngestResult(
            timestamp=ts,
            kci_id=article.kci_id,
            title=article.title,
            url=article.url,
            action="ingested",
            query=query,
            year=article.year,
            out_path=str(out_path),
            pdf_action=pdf_action,
            pdf_path=str(pdf_path) if pdf_path else None,
            pdf_url=pdf_url,
            pdf_source=article.pdf_source or None,
            nfc_applied=article.nfc_applied,
        )
        append_log(queue_dir, result)
        append_corpus(corpus_out, article, result, query)
        return result
    except Exception as e:
        logging.exception("KCI 처리 실패: %s", article_stub.kci_id)
        result = IngestResult(
            timestamp=ts,
            kci_id=article_stub.kci_id,
            title=article_stub.title,
            url=article_stub.url,
            action="failed",
            query=query,
            year=article_stub.year,
            pdf_url=article_stub.pdf_url or None,
            error=str(e),
        )
        append_log(queue_dir, result)
        return result


def build_targets(
    args: argparse.Namespace,
    client: HTTPClient,
) -> tuple[list[KCIArticle], Optional[str]]:
    targets: list[KCIArticle] = []
    query_labels: list[str] = []

    for url in args.url or []:
        kci_id = extract_kci_id(url)
        if not kci_id:
            raise ValueError(f"KCI 논문 ID를 찾을 수 없음: {url}")
        targets.append(KCIArticle(kci_id=kci_id, url=canonical_article_url(kci_id)))

    for html_path in args.html or []:
        article = read_article_html(html_path)
        targets.append(article)

    if args.query:
        query_labels.append(f"query:{args.query}")
        targets.extend(search_kci(client, args.query, args.max, args.since, args.condition, until=args.until))

    for journal in args.journal or []:
        journal = clean_text(journal)
        if not journal:
            continue
        query_labels.append(f"journal:{journal}")
        targets.extend(search_kci_journal(
            client,
            name=journal,
            aliases=None,
            per_journal_max=args.per_journal_max,
            scan_max=args.journal_scan_max,
            since=args.since,
            until=args.until,
        ))

    if args.journal_profile:
        priorities = parse_priority_filter(args.journal_priority)
        fields = set(args.journal_field or []) or None
        journals = load_journal_profile(args.journal_profile, priorities=priorities, fields=fields)
        query_labels.append(f"journal-profile:{args.journal_profile.name}")
        for item in journals:
            journal = str(item["name"])
            aliases = [str(alias) for alias in item.get("aliases", []) if str(alias).strip()]
            targets.extend(search_kci_journal(
                client,
                name=journal,
                aliases=aliases,
                per_journal_max=args.per_journal_max,
                scan_max=args.journal_scan_max,
                since=args.since,
                until=args.until,
                profile_item=item,
            ))

    deduped: list[KCIArticle] = []
    ids: set[str] = set()
    for target in targets:
        if target.kci_id in ids:
            continue
        deduped.append(target)
        ids.add(target.kci_id)
    if args.query and not (args.journal or args.journal_profile):
        deduped = deduped[:args.max]
    return deduped, ";".join(query_labels) or None


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="KCI 서지정보·초록 수집 (corpus JSONL; --inbox 지정 시 vault 노트 적재)")
    parser.add_argument("--url", action="append", help="KCI 논문 상세 URL. 여러 번 지정 가능")
    parser.add_argument("--html", action="append", type=Path, help="수동 저장한 KCI 논문 상세 HTML. 여러 번 지정 가능")
    parser.add_argument("--query", help="KCI 논문 검색어")
    parser.add_argument("--condition", default="KEYALL",
                        choices=["KEYALL", "INDE_TITL", "CRET_NM", "AFFI_NM", "PUBI_INSI_NM",
                                 "SERE_NM", "KEYWORD", "INDE_CONE", "ORCID"],
                        help="KCI 검색 조건. 기본 KEYALL")
    parser.add_argument("--journal", action="append", help="학술지명 검색. KCI SERE_NM 조건 사용, 여러 번 지정 가능")
    parser.add_argument("--journal-profile", nargs="?", const=DEFAULT_JOURNAL_PROFILE, type=Path,
                        help="학술지 프로필 JSON. 값 없이 쓰면 기본 한국학 프로필 사용")
    parser.add_argument("--journal-priority", action="append",
                        help="프로필 priority 필터. 예: --journal-priority 1 또는 1,2")
    parser.add_argument("--journal-field", action="append",
                        help="프로필 field 필터. 예: hanmun, hanmun_education, korean_literature, korean_history, history_education")
    parser.add_argument("--per-journal-max", type=int, default=20, help="학술지별 검색 적재 최대 건수")
    parser.add_argument("--journal-scan-max", type=int, default=300,
                        help="학술지명 부분일치 결과에서 정확일치 후보를 찾기 위해 스캔할 최대 건수")
    parser.add_argument("--max", type=int, default=20, help="검색 적재 최대 건수")
    parser.add_argument("--year", type=int, help="발행연도 정확 필터. 예: --year 2025")
    parser.add_argument("--since", type=int, help="발행연도 하한")
    parser.add_argument("--until", type=int, help="발행연도 상한")
    parser.add_argument("--dry-run", action="store_true", help="노트 생성과 seen 기록 없이 로그만 기록")
    parser.add_argument("--corpus-out", type=Path,
                        help="수집한 상세 서지·초록을 JSONL 코퍼스로 저장. --dry-run과 함께 써도 기록됨")
    parser.add_argument("--download-pdf", action="store_true",
                        help="상세 페이지의 PDF 후보를 PAPERS_ROOT/_global_inbox에 저장해 llm-pipeline 분류부터 태움")
    parser.add_argument("--inbox", type=Path, default=DEFAULT_INBOX, help="vault inbox 경로 (vault 적재를 쓸 때만)")
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE, help="작업 큐 경로 (기본: 작업 루트/.queue)")
    parser.add_argument("--pdf-output-dir", type=Path, default=DEFAULT_GLOBAL_INBOX,
                        help="PDF 저장 위치. 기본: PAPERS_ROOT/_global_inbox")
    parser.add_argument("--sleep", type=float, default=1.5, help="요청 간 sleep 초")
    parser.add_argument("--no-robots-check", action="store_true", help="명시적 허가가 있을 때만 robots.txt 확인 생략")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)

    if not args.url and not args.query and not args.html and not args.journal and not args.journal_profile:
        parser.error("--url, --query, --html, --journal, --journal-profile 중 하나는 필요합니다")
    if args.max < 1:
        parser.error("--max는 1 이상이어야 합니다")
    if args.per_journal_max < 1:
        parser.error("--per-journal-max는 1 이상이어야 합니다")
    if args.journal_scan_max < args.per_journal_max:
        parser.error("--journal-scan-max는 --per-journal-max 이상이어야 합니다")
    if args.year and (args.since or args.until):
        parser.error("--year는 --since 또는 --until과 함께 쓸 수 없습니다")
    if args.year:
        args.since = args.year
        args.until = args.year
    if args.since and args.until and args.until < args.since:
        parser.error("--until은 --since 이상이어야 합니다")

    DEFAULT_LOGS.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(DEFAULT_LOGS / "kci_ingest.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

    if args.max >= 100 or args.per_journal_max >= 100:
        logging.info("100건 이상 처리: kci-seen.jsonl dedupe와 kci-pending.jsonl checkpoint로 재실행 resume")

    client = HTTPClient(sleep_seconds=args.sleep, respect_robots=not args.no_robots_check)
    targets, query_label = build_targets(args, client)
    seen = load_seen(args.queue)
    results: list[IngestResult] = []

    print("=" * 60)
    print(f"KCI ingest - targets={len(targets)}, dry-run={args.dry_run}, since={args.since}, until={args.until}")
    print(f"inbox: {args.inbox}")
    print(f"queue: {args.queue}")
    if args.journal_profile:
        print(f"journal profile: {args.journal_profile}")
    if args.journal:
        print(f"journal queries: {len(args.journal)}")
    if args.download_pdf:
        print(f"pdf output: {args.pdf_output_dir}")
    if args.corpus_out:
        print(f"corpus out: {args.corpus_out}")
    print("=" * 60)

    for idx, target in enumerate(targets, start=1):
        print(f"[{idx}/{len(targets)}] {target.kci_id} {target.title or ''}".rstrip())
        result = process_article(
            article_stub=target,
            client=client,
            inbox=args.inbox,
            queue_dir=args.queue,
            pdf_output_dir=args.pdf_output_dir,
            corpus_out=args.corpus_out,
            dry_run=args.dry_run,
            download_pdf_enabled=args.download_pdf,
            seen=seen,
            query=query_label,
        )
        results.append(result)
        if result.action == "ingested":
            print(f"  -> {result.out_path}")
            if result.pdf_action:
                print(f"  pdf {result.pdf_action}: {result.pdf_path or result.pdf_url or ''}")
        elif result.action == "dry-run":
            print(f"  dry-run: {result.title}")
            if result.pdf_action:
                print(f"  pdf {result.pdf_action}: {result.pdf_path or result.pdf_url or ''}")
        elif result.action == "skipped-dup":
            print("  skipped duplicate")
        else:
            print(f"  {result.action}: {result.error or ''}")

    by_action: dict[str, int] = {}
    for result in results:
        by_action[result.action] = by_action.get(result.action, 0) + 1

    print("\nsummary")
    for action, count in sorted(by_action.items()):
        print(f"  {action:<12} {count}")
    print(f"log: {args.queue / 'kci-pending.jsonl'}")
    return 0 if not any(r.action == "failed" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
