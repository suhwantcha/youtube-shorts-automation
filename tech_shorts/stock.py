"""Optional stock providers with stable routing and Pixabay's 24-hour search cache."""
import hashlib
import json
import logging
import os
from pathlib import Path
import tempfile
import time
import requests


def provider_order(query, narration):
    providers=[p for p in ("pexels","pixabay") if os.getenv(f"{p.upper()}_API_KEY")]
    if len(providers)==2:
        bucket=int(hashlib.sha256(f"{query}\n{narration}".encode()).hexdigest()[:8],16)%100
        if bucket < 30:
            providers.reverse()
    return providers


def pixabay(query, cache_dir):
    key=os.environ["PIXABAY_API_KEY"]
    cache_dir=Path(cache_dir);cache_dir.mkdir(parents=True,exist_ok=True)
    cache=cache_dir/(hashlib.sha256(f"pixabay-v1:{key}:{query}".encode()).hexdigest()+".json")
    try:
        if time.time()-cache.stat().st_mtime < 86400:
            return json.loads(cache.read_text(encoding="utf-8"))
    except (FileNotFoundError,ValueError):
        pass
    response=requests.get("https://pixabay.com/api/videos/",params={"key":key,"q":query[:100],
        "lang":"en","safesearch":"true","per_page":20,"min_width":1080,"min_height":1920},timeout=(10,20))
    response.raise_for_status()
    videos=[]
    for hit in response.json().get("hits",[]):
        files=[{"file_type":"video/mp4","width":v.get("width",0),"height":v.get("height",0),
                "link":v.get("url"),"thumbnail":v.get("thumbnail","")}
               for v in hit.get("videos",{}).values() if isinstance(v,dict) and v.get("url")]
        image=next((f["thumbnail"] for f in files if f["thumbnail"]),"")
        videos.append({"id":-int(hit["id"]),"source_id":hit["id"],"provider":"pixabay",
            "duration":hit.get("duration",0),"image":image,"video_files":files,
            "url":hit.get("pageURL",""),"user":{"name":hit.get("user","")},
            "license_url":"https://pixabay.com/service/license-summary/"})
    with tempfile.NamedTemporaryFile(mode="w",encoding="utf-8",dir=cache_dir,suffix=".tmp",delete=False) as stream:
        json.dump(videos,stream,ensure_ascii=False)
        temporary=Path(stream.name)
    try:
        temporary.replace(cache)
    finally:
        temporary.unlink(missing_ok=True)
    return videos


def search(query, narration, cache_dir):
    for provider in provider_order(query,narration):
        try:
            if provider=="pixabay":
                videos=pixabay(query,cache_dir)
            else:
                response=requests.get("https://api.pexels.com/videos/search",headers={"Authorization":os.environ["PEXELS_API_KEY"]},
                    params={"query":query,"per_page":12,"size":"large","orientation":"portrait"},timeout=30)
                response.raise_for_status()
                videos=[{**v,"provider":"pexels","source_id":v["id"],"license_url":"https://www.pexels.com/license/"}
                        for v in response.json().get("videos",[])]
            # Empty or unusable results should try the other configured provider.
            videos=[v for v in videos if v.get("duration",0)>=3 and any(
                (f.get("width") or 0)>=1080 and (f.get("height") or 0)>=1920 and f.get("link") for f in v.get("video_files",[]))]
            if videos:
                return videos
        except (requests.RequestException,ValueError,KeyError):
            logging.getLogger(__name__).warning("%s 영상 검색 실패: 다른 소스를 확인합니다.",provider)
    return []
