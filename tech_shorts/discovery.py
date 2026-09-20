"""Recent news discovery with original publisher links and explicit ranking basis."""
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from urllib.parse import parse_qs, urlparse, urlunparse, parse_qsl, urlencode
import re
import xml.etree.ElementTree as ET

import requests

from .topics import category_info


def canonical_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return ""
    params = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
              if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}]
    return urlunparse((parsed.scheme, parsed.netloc.lower(), parsed.path.rstrip("/"), "", urlencode(params), ""))


def parse_news(xml, *, now=None):
    """Feed order is relevance, not an invented view/engagement count."""
    now = now or datetime.now(timezone.utc)
    root = ET.fromstring(xml)
    items = []
    for item in root.findall("./channel/item"):
        title = unescape(item.findtext("title", "")).strip()
        url = item.findtext("link", "").strip()
        parsed = urlparse(url)
        if parsed.hostname in {"bing.com", "www.bing.com"} and parsed.path == "/news/apiclick.aspx":
            url = parse_qs(parsed.query).get("url", [""])[0]
        url = canonical_url(url)
        try:
            published = parsedate_to_datetime(item.findtext("pubDate", ""))
            published = published.replace(tzinfo=timezone.utc) if published.tzinfo is None else published
        except (ValueError, TypeError, OverflowError):
            continue
        if not title or not url or not now-timedelta(days=30) <= published <= now+timedelta(hours=24):
            continue
        publisher = next((n.text for n in item if n.tag.rsplit("}", 1)[-1].lower() == "source" and n.text), "뉴스")
        items.append(dict(title=title, url=url, source=publisher, provider="Bing News",
                          published_at=published.isoformat(), ranking_basis="최근 뉴스 · 검색 관련도"))
    return items


def collect_news(category, limit=10):
    info = category_info(category)
    items = []
    searches = [(info["english_query"], "en-US", False),
                (info["english_query"], "en-US", True)]
    for query, market, recent in searches:
        try:
            params = {"q": query, "format": "rss", "mkt": market, "count": 40}
            if recent:
                params["qft"] = 'sortbydate="1"'
            with requests.get("https://www.bing.com/news/search",
                    params=params,
                    timeout=(10, 20), stream=True) as response:
                response.raise_for_status()
                data = bytearray()
                for chunk in response.iter_content(16384):
                    data.extend(chunk)
                    if len(data) > 1_000_000:
                        raise ValueError("뉴스 응답이 너무 큽니다.")
                found = parse_news(bytes(data))
                if recent:
                    found = [{**item, "ranking_basis": "최근 뉴스 · 최신순 보완"} for item in found]
                items.extend(found)
        except (requests.RequestException, ValueError, ET.ParseError):
            continue
        items = deduplicate(items)
        if len(items) >= limit:
            break
    return items[:limit]


def deduplicate(items):
    urls, titles, result = set(), set(), []
    for item in items:
        url = canonical_url(item.get("url", ""))
        title = re.sub(r"\W+", "", item.get("title", "").casefold())
        if url and title and url not in urls and title not in titles:
            urls.add(url)
            titles.add(title)
            result.append({**item, "url": url})
    return result
