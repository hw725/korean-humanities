#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kci_search.py — KCI 웹 검색으로 논문 씨앗(artiId·제목·연도·저널)을 얻는 최소 모듈.

kci_citation_collect.py의 --query 씨앗 검색이 쓴다. 표준 라이브러리만 사용하고
Obsidian·LLM·개인 경로 결합이 없다 — API 키도 불필요(공개 검색 페이지 파싱).

[korean-humanities suite] 원문 발췌: <corpus-pipeline>/scripts/kci_ingest.py의
검색 계층(HTTPClient·search_kci·파서·KCIArticle)만 그대로 옮긴 것. 수집기의
vault 적재·PDF 다운로드 기능은 포함하지 않는다(그건 개인 파이프라인 영역).
"""
from __future__ import annotations

import re
import json
import logging
import unicodedata
import urllib.robotparser
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
import html
from typing import Optional

KCI_BASE = "https://www.kci.go.kr"
KCI_SEARCH_URL = f"{KCI_BASE}/kciportal/po/search/poArtiSearList.kci"
KCI_ARTICLE_URL = f"{KCI_BASE}/kciportal/ci/sereArticleSearch/ciSereArtiView.kci"
KCI_LANDING_URL = f"{KCI_BASE}/kciportal/landing/article.kci"
_ARTI_ID_RE = re.compile(r"\bART\d{9}\b")


def _contains_hanja(text: str) -> bool:
    """한자 포함 여부 — CJK 계약 준수 판별.

    [local divergence] upstream은 re.compile(r"[㐀-鿿]") 문자클래스였는데, 그 범위는
    한자 확장 B 이상(U+20000+)을 놓친다 — 전근대 문헌 제목에 실제로 나온다.
    코드포인트 비교로 바꿔 확장 평면까지 덮는다 (기본·확장A·호환·확장B~F).
    """
    for ch in text:
        o = ord(ch)
        if 0x3400 <= o <= 0x9FFF or 0xF900 <= o <= 0xFAFF or 0x20000 <= o <= 0x2FA1F:
            return True
    return False
_TAG_RE = re.compile(r"<[^>]+>")
_ASCII_TAG_RE = re.compile(r"</?[A-Za-z][^>]*>")
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "kci_search/0.1; personal research citation-network seed search"
)


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
    article.nfc_applied = article.nfc_applied or before != after or _contains_hanja(combined)
    return article


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
