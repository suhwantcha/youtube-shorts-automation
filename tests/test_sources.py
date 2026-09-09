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
