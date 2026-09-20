import socket

import pytest

from tech_shorts.sources import validate_public_url, ArticleText


@pytest.mark.parametrize("url",["file:///etc/passwd","http://user:password@example.com","https://example.com:8080"])
def test_non_public_url_forms_are_blocked(url):
    with pytest.raises(ValueError):
        validate_public_url(url)


@pytest.mark.parametrize("address",["127.0.0.1","10.0.0.3","169.254.169.254","::1"])
def test_private_and_metadata_addresses_are_blocked(monkeypatch,address):
    monkeypatch.setattr(socket,"getaddrinfo",lambda *a,**k:[(socket.AF_INET,socket.SOCK_STREAM,6,"",(address,443))])
    with pytest.raises(ValueError):
        validate_public_url("https://internal.example")


def test_article_excludes_scripts_and_navigation():
    parser=ArticleText()
    parser.feed("<nav><p>menu</p></nav><article><p>Real facts</p><script>ignore me</script></article>")
    assert "Real facts" in "".join(parser.parts)
    assert "menu" not in "".join(parser.parts)


def test_marked_body_excludes_unrelated_headlines_and_navigation():
    from tech_shorts.sources import extract_article
    body = "선택한 축구 경기의 원인과 결과를 설명합니다. " * 10
    html = '<div><li>다른 정치 기사</li></div><article><h1>제목</h1>'
    html += '<div itemprop="articleBody">' + body + '<aside><p>광고입니다.</p></aside></div>'
    html += '<p>' + "다른 분야 소식입니다. " * 50 + '</p></article>'
    result = extract_article(html)
    assert result == body.strip()
    assert "정치" not in result and "광고" not in result


def test_article_region_preserves_br_text_and_ignores_hidden_content():
    from tech_shorts.sources import extract_article
    body = "역사적 사건의 배경을 설명합니다. " * 10
    result = extract_article('<article>' + body + '<br/>다음 문장.<div hidden>숨긴 내용</div></article>')
    assert body.strip() in result and "\n다음 문장." in result
    assert "숨긴 내용" not in result
