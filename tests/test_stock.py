from unittest.mock import Mock
import requests
from tech_shorts import stock


def test_routing_is_stable_and_uses_only_configured_providers(monkeypatch):
    monkeypatch.setenv("PEXELS_API_KEY","p");monkeypatch.delenv("PIXABAY_API_KEY",raising=False)
    assert stock.provider_order("space","narration")==["pexels"]
    monkeypatch.setenv("PIXABAY_API_KEY","b")
    counts={"pexels":0,"pixabay":0}
    for i in range(1000):
        order=stock.provider_order("space",str(i));assert order==stock.provider_order("space",str(i))
        counts[order[0]]+=1
    assert 250 < counts["pixabay"] < 350


def test_pixabay_cache_and_provenance(monkeypatch,tmp_path):
    monkeypatch.setenv("PIXABAY_API_KEY","do-not-store-key")
    response=Mock();response.json.return_value={"hits":[{"id":7,"duration":6,"pageURL":"https://pixabay.com/videos/id-7/","user":"Creator",
        "videos":{"large":{"url":"https://cdn.pixabay.com/a.mp4","width":1080,"height":1920,"thumbnail":"https://cdn.pixabay.com/a.jpg"}}}]}
    get=Mock(return_value=response);monkeypatch.setattr(stock.requests,"get",get)
    first=stock.pixabay("space",tmp_path);second=stock.pixabay("space",tmp_path)
    assert first==second and get.call_count==1
    assert first[0]["id"]==-7 and first[0]["source_id"]==7 and first[0]["provider"]=="pixabay"
    assert first[0]["image"]=="https://cdn.pixabay.com/a.jpg"
    assert all("do-not-store-key" not in p.read_text() for p in tmp_path.glob("*.json"))


def test_failed_provider_tries_other_source(monkeypatch,tmp_path):
    monkeypatch.setenv("PEXELS_API_KEY","p")
    monkeypatch.setattr(stock,"provider_order",lambda *a:["pixabay","pexels"])
    monkeypatch.setattr(stock,"pixabay",Mock(side_effect=requests.ReadTimeout("signed-secret-url")))
    response=Mock();response.json.return_value={"videos":[{"id":9,"duration":4,"video_files":[{"width":1080,"height":1920,"link":"https://example.com/v.mp4"}]}]}
    monkeypatch.setattr(stock.requests,"get",Mock(return_value=response))
    assert stock.search("space","narration",tmp_path)[0]["provider"]=="pexels"
