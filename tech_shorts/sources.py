"""Bounded extraction of public article text for the automatic production mode."""
from html.parser import HTMLParser
import ipaddress
import re
import socket
from urllib.parse import urljoin, urlparse

import requests


def validate_public_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("공개된 HTTP 또는 HTTPS 기사 주소가 필요합니다.")
    if parsed.port not in {None, 80, 443}:
        raise ValueError("기사 주소에는 표준 HTTP 포트만 사용할 수 있습니다.")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("기사 서버의 주소를 찾을 수 없습니다.") from exc
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError("로컬·내부 네트워크 주소는 기사 자료로 사용할 수 없습니다.")
    return url


class ArticleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.paragraph = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "nav", "header", "footer"}:
            self.skip += 1
        if tag in {"p", "h1", "h2", "li"}:
            self.paragraph += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "nav", "header", "footer"}:
            self.skip = max(0, self.skip - 1)
        if tag in {"p", "h1", "h2", "li"}:
            self.paragraph = max(0, self.paragraph - 1)
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip and self.paragraph:
            self.parts.append(data)


class ArticleRegions(HTMLParser):
    """Prefer publisher-marked article bodies over menus and related stories."""
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
    SKIP = {"script", "style", "nav", "header", "footer", "aside", "button", "form"}

    def __init__(self):
        super().__init__()
        self.stack, self.regions = [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "br":
            self.handle_data("\n")
        if tag in self.VOID:
            return
        marker = re.sub(r"[-_]", "", attrs.get("id", "").lower())
        classes = {re.sub(r"[-_]", "", c.lower()) for c in attrs.get("class", "").split()}
        priority = (3 if "articleBody" in attrs.get("itemprop", "").split() else
                    2 if marker in {"articlebody", "textbody", "newsctarticle", "dicarea", "articlecontent"}
                    or classes & {"articlebody", "articlecontent", "storybody", "entrycontent"} else
                    1 if tag == "article" else 0)
        skip = (tag in self.SKIP or "hidden" in attrs or attrs.get("aria-hidden") == "true"
                or bool(re.search(r"display\s*:\s*none", attrs.get("style", ""), re.I)))
        region = {"priority": priority, "parts": []} if priority and not skip and not any(f[1] for f in self.stack) else None
        if region is not None:
            self.regions.append(region)
        self.stack.append((tag, skip, region))
        if tag in {"p", "div", "section", "article", "li", "h1", "h2"}:
            self.handle_data("\n")

    def handle_endtag(self, tag):
        if tag in {"p", "div", "section", "article", "li", "h1", "h2"}:
            self.handle_data("\n")
        for index in range(len(self.stack)-1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_data(self, data):
        if any(frame[1] for frame in self.stack):
            return
        for _, _, region in self.stack:
            if region is not None:
                region["parts"].append(data)


def extract_article(html):
    def cleaned(parts):
        return "\n".join(" ".join(line.split()) for line in "".join(parts).splitlines() if line.strip())
    regions = ArticleRegions()
    regions.feed(html)
    candidates = [(r["priority"], cleaned(r["parts"])) for r in regions.regions]
    candidates = [(priority, text) for priority, text in candidates if len(text) >= 150]
    if candidates:
        return max(candidates, key=lambda item: (item[0], len(item[1])))[1][:24000]
    parser = ArticleText()
    parser.feed(html)
    return cleaned(parser.parts)[:24000]


def article_notes(url):
    current = url
    for _ in range(4):
        validate_public_url(current)
        with requests.get(current, timeout=(10, 20), stream=True, allow_redirects=False,
                          headers={"User-Agent": "TechShortsStudio/3.0 (article preview)"}) as response:
            if response.is_redirect:
                current = urljoin(current, response.headers["Location"])
                continue
            response.raise_for_status()
            if "text/html" not in response.headers.get("Content-Type", "").lower():
                raise ValueError("HTML 기사만 자동으로 읽을 수 있습니다. 핵심 사실을 직접 입력해주세요.")
            data = bytearray()
            for chunk in response.iter_content(16384):
                data.extend(chunk)
                if len(data) > 1_000_000:
                    break
            raw = bytes(data[:1_000_000])
            encoding = response.encoding
            if not encoding or encoding.lower() == "iso-8859-1":
                charset = re.search(br'charset=["\x27\s]*([\w-]+)', raw[:8192], re.I)
                encoding = charset.group(1).decode("ascii") if charset else "utf-8"
            try:
                html = raw.decode(encoding, errors="replace")
            except LookupError:
                html = raw.decode("utf-8", errors="replace")
            text = extract_article(html)
            if len(text) < 150:
                raise ValueError("기사 본문이 충분하지 않습니다. 핵심 사실을 직접 입력해주세요.")
            return f"출처: {current}\n기사 본문 (검토 전 자동 추출):\n{text}"
    raise ValueError("기사 주소의 리디렉션이 너무 많습니다.")
