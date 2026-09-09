"""Bounded extraction of public article text for the automatic production mode."""
from html.parser import HTMLParser
import ipaddress
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
            parser = ArticleText()
            parser.feed(bytes(data[:1_000_000]).decode(response.encoding or "utf-8", errors="replace"))
            lines = [line.strip() for line in "".join(parser.parts).splitlines() if line.strip()]
            text = "\n".join(lines)[:10000]
            if len(text) < 150:
                raise ValueError("기사 본문이 충분하지 않습니다. 핵심 사실을 직접 입력해주세요.")
            return f"출처: {current}\n기사 본문 (검토 전 자동 추출):\n{text}"
    raise ValueError("기사 주소의 리디렉션이 너무 많습니다.")
