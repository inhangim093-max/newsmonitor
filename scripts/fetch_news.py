#!/usr/bin/env python3
"""keywords.json 에 등록된 키워드로 뉴스를 수집해 docs/news.json 에 누적 저장한다.

- 기본 수집원: Google 뉴스 RSS (API 키 불필요)
- 선택 수집원: 네이버 뉴스 검색 API (환경변수 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 이 있을 때만)

표준 라이브러리만 사용하므로 별도 설치가 필요 없다.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEYWORDS_FILE = ROOT / "keywords.json"
OUTPUT_FILE = ROOT / "docs" / "news.json"

KST = timezone(timedelta(hours=9))
USER_AGENT = "Mozilla/5.0 (compatible; newsmonitor/1.0)"
TAG_RE = re.compile(r"<[^>]+>")


def http_get(url: str, headers: dict[str, str] | None = None) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def clean(text: str | None) -> str:
    return html.unescape(TAG_RE.sub("", text or "")).strip()


def to_iso(date_str: str | None) -> str | None:
    if not date_str:
        return None
    try:
        dt = parsedate_to_datetime(date_str)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(KST).isoformat()


def google_query(keyword: str) -> str:
    # 띄어쓰기 없는 키워드는 정확히 일치하도록 따옴표로 감싸고,
    # "울산 사업장폐기물" 처럼 여러 단어인 경우는 모든 단어가 포함된 기사를 찾는다.
    return keyword if " " in keyword else f'"{keyword}"'


def parse_google_rss(xml_bytes: bytes, keyword: str) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    items = []
    for item in root.iter("item"):
        title = clean(item.findtext("title"))
        source_el = item.find("source")
        source = clean(source_el.text) if source_el is not None else ""
        # Google 뉴스 제목은 "기사 제목 - 언론사" 형식이므로 언론사 부분을 떼어낸다.
        if source and title.endswith(f" - {source}"):
            title = title[: -len(f" - {source}")].strip()
        link = (item.findtext("link") or "").strip()
        if not title or not link:
            continue
        items.append(
            {
                "title": title,
                "link": link,
                "source": source,
                "published": to_iso(item.findtext("pubDate")),
                "summary": "",
                "keyword": keyword,
                "provider": "google",
            }
        )
    return items


def fetch_google(keyword: str) -> list[dict]:
    params = urllib.parse.urlencode(
        {"q": f"{google_query(keyword)} when:7d", "hl": "ko", "gl": "KR", "ceid": "KR:ko"}
    )
    return parse_google_rss(http_get(f"https://news.google.com/rss/search?{params}"), keyword)


def fetch_naver(keyword: str, client_id: str, client_secret: str) -> list[dict]:
    params = urllib.parse.urlencode({"query": keyword, "display": 100, "sort": "date"})
    data = json.loads(
        http_get(
            f"https://openapi.naver.com/v1/search/news.json?{params}",
            {"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret},
        )
    )
    items = []
    for it in data.get("items", []):
        link = it.get("originallink") or it.get("link") or ""
        domain = urllib.parse.urlparse(link).netloc.removeprefix("www.")
        items.append(
            {
                "title": clean(it.get("title")),
                "link": link,
                "source": domain,
                "published": to_iso(it.get("pubDate")),
                "summary": clean(it.get("description")),
                "keyword": keyword,
                "provider": "naver",
            }
        )
    return items


def normalize_title(title: str) -> str:
    return re.sub(r"[\s\W_]+", "", title).lower()


def merge(existing: list[dict], fetched: list[dict], now: datetime) -> list[dict]:
    """제목 기준으로 중복을 합치고, 같은 기사가 여러 키워드에 걸리면 keywords 에 모두 기록한다."""
    by_key: dict[str, dict] = {}
    for art in existing:
        by_key[normalize_title(art["title"])] = art

    now_iso = now.isoformat()
    for art in fetched:
        key = normalize_title(art["title"])
        if not key:
            continue
        cur = by_key.get(key)
        if cur is None:
            by_key[key] = {
                "id": hashlib.sha1(key.encode()).hexdigest()[:12],
                "title": art["title"],
                "link": art["link"],
                "source": art["source"],
                "published": art["published"],
                "summary": art["summary"],
                "keywords": [art["keyword"]],
                "collected": now_iso,
            }
            continue
        if art["keyword"] not in cur["keywords"]:
            cur["keywords"].append(art["keyword"])
        # 네이버 결과에는 요약이 있으므로 비어 있으면 채워 넣는다.
        if not cur.get("summary") and art["summary"]:
            cur["summary"] = art["summary"]
        if not cur.get("published") and art["published"]:
            cur["published"] = art["published"]
    return list(by_key.values())


def sort_key(art: dict) -> str:
    return art.get("published") or art.get("collected") or ""


def main() -> int:
    config = json.loads(KEYWORDS_FILE.read_text(encoding="utf-8"))
    keywords: list[str] = config["keywords"]
    retention_days: int = config.get("retention_days", 90)

    naver_id = os.environ.get("NAVER_CLIENT_ID", "").strip()
    naver_secret = os.environ.get("NAVER_CLIENT_SECRET", "").strip()

    now = datetime.now(KST).replace(microsecond=0)
    fetched: list[dict] = []
    errors: list[str] = []
    for kw in keywords:
        try:
            got = fetch_google(kw)
            print(f"[google] {kw}: {len(got)}건")
            fetched += got
        except Exception as e:  # noqa: BLE001 - 한 키워드 실패가 전체를 멈추지 않도록
            errors.append(f"google/{kw}: {e}")
        if naver_id and naver_secret:
            try:
                got = fetch_naver(kw, naver_id, naver_secret)
                print(f"[naver] {kw}: {len(got)}건")
                fetched += got
            except Exception as e:  # noqa: BLE001
                errors.append(f"naver/{kw}: {e}")

    for err in errors:
        print(f"오류: {err}", file=sys.stderr)
    if not fetched and errors:
        print("모든 수집이 실패하여 기존 데이터를 유지합니다.", file=sys.stderr)
        return 1

    existing: list[dict] = []
    if OUTPUT_FILE.exists():
        existing = json.loads(OUTPUT_FILE.read_text(encoding="utf-8")).get("articles", [])

    articles = merge(existing, fetched, now)
    cutoff = (now - timedelta(days=retention_days)).isoformat()
    articles = [a for a in articles if sort_key(a) >= cutoff]
    articles.sort(key=sort_key, reverse=True)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(
            {"updated": now.isoformat(), "keywords": keywords, "articles": articles},
            ensure_ascii=False,
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )
    new_count = sum(1 for a in articles if a["collected"] == now.isoformat())
    print(f"총 {len(articles)}건 저장 (신규 {new_count}건)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
