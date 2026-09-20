from datetime import datetime, timezone
from unittest.mock import Mock
from email.utils import format_datetime

import pytest

from tech_shorts import content, discovery
from tech_shorts.topics import CATEGORIES, category_choices
from tech_shorts.pipeline import validate_inputs


def test_catalog_and_input_validation():
    assert len(category_choices()) == 17
    for category in CATEGORIES:
        assert validate_inputs({"script": "테스트", "category": category})["category"] == category
    with pytest.raises(ValueError, match="분야"):
        validate_inputs({"script": "테스트", "category": "unknown"})


@pytest.mark.parametrize("category", ["football", "boxing", "mma", "baseball", "basketball", "motorsport", "gaming"])
def test_removed_categories_are_rejected(category):
    assert category not in CATEGORIES
    with pytest.raises(ValueError, match="분야"):
        validate_inputs({"script": "테스트", "category": category})


def test_news_keeps_original_links_dates_and_honest_ranking():
    xml = '''<rss xmlns:News="urn:news"><channel>
    <item><title>축구 뉴스</title><link>https://www.bing.com/news/apiclick.aspx?url=https%3A%2F%2Fexample.com%2Fstory%3Futm_source%3Dbing</link><pubDate>Fri, 18 Sep 2026 04:00:00 GMT</pubDate><News:Source>스포츠신문</News:Source></item>
    <item><title>오래된 기사</title><link>https://example.com/old</link><pubDate>Fri, 18 Sep 2020 04:00:00 GMT</pubDate></item>
    <item><title>미래 기사</title><link>https://example.com/future</link><pubDate>Fri, 18 Sep 2030 04:00:00 GMT</pubDate></item>
    <item><title>잘못된 링크</title><link>file:///private</link><pubDate>Fri, 18 Sep 2026 04:00:00 GMT</pubDate></item>
    </channel></rss>'''
    result = discovery.parse_news(xml, now=datetime(2026, 9, 19, tzinfo=timezone.utc))
    assert len(result) == 1
    assert result[0]["url"] == "https://example.com/story"
    assert result[0]["source"] == "스포츠신문" and "score" not in result[0]


@pytest.mark.parametrize("category", [c for c in CATEGORIES if c != "it"])
def test_non_it_categories_never_use_hacker_news(monkeypatch, category):
    monkeypatch.delenv("REDDIT_CLIENT_ID", raising=False)
    monkeypatch.setattr(content, "collect_trends", Mock(side_effect=AssertionError("IT feed")))
    news = Mock(return_value=[dict(title=f"소재 {i}", url=f"https://example.com/{i}", source="뉴스") for i in range(10)])
    monkeypatch.setattr(content, "collect_news", news)
    result = content.all_trends(category=category)
    news.assert_called_once_with(category, 10)
    assert len(result) == 10 and all(t["category"] == category for t in result)


def test_deduplication_removes_tracking_links_and_title_duplicates():
    rows = [dict(title="같은 기사!", url="https://example.com/a?utm_source=x"),
            dict(title="다른 제목", url="https://example.com/a?utm_source=y"),
            dict(title="같은 기사", url="https://other.com/b")]
    assert len(discovery.deduplicate(rows)) == 1


def test_daily_automatic_jobs_are_separate_for_each_category(service, monkeypatch):
    trends = Mock(return_value=[dict(title="추천 소재", url="https://example.com/news")])
    monkeypatch.setattr(content, "all_trends", trends)
    monkeypatch.setattr("tech_shorts.sources.article_notes", lambda url: "기사 원문")
    science = service.create_auto({"category": "science"})
    music = service.create_auto({"category": "music"})
    assert science["id"] != music["id"]
    assert service.create_auto({"category": "science"})["id"] == science["id"]
    assert trends.call_count == 2
    assert music["inputs"]["category"] == "music"


def test_news_fills_sparse_relevance_results_with_recent_results(monkeypatch):
    date = format_datetime(datetime.now(timezone.utc))
    xml = "<rss><channel>" + "".join(
        f"<item><title>소재 {i}</title><link>https://example.com/{i}</link><pubDate>{date}</pubDate></item>"
        for i in range(10)) + "</channel></rss>"
    def response(payload):
        result = Mock()
        result.__enter__ = Mock(return_value=result)
        result.__exit__ = Mock(return_value=False)
        result.iter_content.return_value = [payload.encode("utf-8")]
        return result
    get = Mock(side_effect=[response("<rss><channel/></rss>"), response(xml)])
    monkeypatch.setattr(discovery.requests, "get", get)
    result = discovery.collect_news("science")
    assert len(result) == 10
    assert get.call_args.kwargs["params"]["qft"] == 'sortbydate="1"'
    assert get.call_count == 2
    for call in get.call_args_list:
        assert call.kwargs["params"]["mkt"] == "en-US"
        assert call.kwargs["params"]["q"] == "science"
    assert all(info["english_query"].isascii() and "query" not in info for info in CATEGORIES.values())
    assert all(t["ranking_basis"] == "최근 뉴스 · 최신순 보완" for t in result)
