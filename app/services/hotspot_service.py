"""首页热点数据聚合"""
import time
from typing import Any, Optional

import httpx
from pydantic import BaseModel

_cache: dict[str, tuple[float, Any]] = {}
CACHE_TTL = 600


class HotItem(BaseModel):
    title: str
    url: str
    description: str = ""
    source: str
    extra: dict[str, Any] = {}


class HotspotResponse(BaseModel):
    github: list[HotItem]
    bilibili: list[HotItem]
    community: list[HotItem]


def _get_cached(key: str) -> Optional[Any]:
    if key in _cache:
        ts, data = _cache[key]
        if time.time() - ts < CACHE_TTL:
            return data
    return None


def _set_cache(key: str, data: Any) -> None:
    _cache[key] = (time.time(), data)


async def fetch_github_trending() -> list[HotItem]:
    """获取 GitHub Trending（通过 search API 近似）"""
    cached = _get_cached("github")
    if cached:
        return cached

    items: list[HotItem] = []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.github.com/search/repositories",
                params={"q": "stars:>1000", "sort": "stars", "order": "desc", "per_page": 10},
                headers={"Accept": "application/vnd.github+json"},
            )
            if resp.status_code == 200:
                for repo in resp.json().get("items", []):
                    items.append(
                        HotItem(
                            title=repo.get("full_name", ""),
                            url=repo.get("html_url", ""),
                            description=repo.get("description") or "",
                            source="github",
                            extra={"stars": repo.get("stargazers_count", 0), "language": repo.get("language")},
                        )
                    )
    except httpx.HTTPError:
        pass

    _set_cache("github", items)
    return items


async def fetch_bilibili_hot() -> list[HotItem]:
    """获取 B 站热门编程视频（搜索 API）"""
    cached = _get_cached("bilibili")
    if cached:
        return cached

    items: list[HotItem] = []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.bilibili.com/x/web-interface/search/type",
                params={"search_type": "video", "keyword": "编程教程", "page": 1, "pagesize": 10},
            )
            if resp.status_code == 200:
                data = resp.json()
                for v in data.get("data", {}).get("result", [])[:10]:
                    bvid = v.get("bvid", "")
                    items.append(
                        HotItem(
                            title=v.get("title", "").replace("<em class=\"keyword\">", "").replace("</em>", ""),
                            url=f"https://www.bilibili.com/video/{bvid}",
                            description=v.get("description", "")[:100],
                            source="bilibili",
                            extra={"author": v.get("author", ""), "play": v.get("play", 0)},
                        )
                    )
    except httpx.HTTPError:
        pass

    _set_cache("bilibili", items)
    return items


async def fetch_community_posts() -> list[HotItem]:
    """获取编程社区最新帖子（Hacker News + V2EX）"""
    cached = _get_cached("community")
    if cached:
        return cached

    items: list[HotItem] = []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            hn = await client.get("https://hacker-news.firebaseio.com/v0/topstories.json")
            if hn.status_code == 200:
                ids = hn.json()[:5]
                for sid in ids:
                    story = await client.get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json")
                    if story.status_code == 200:
                        s = story.json()
                        items.append(
                            HotItem(
                                title=s.get("title", ""),
                                url=s.get("url") or f"https://news.ycombinator.com/item?id={sid}",
                                source="hackernews",
                                extra={"score": s.get("score", 0)},
                            )
                        )
    except httpx.HTTPError:
        pass

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://www.v2ex.com/api/topics/hot.json")
            if resp.status_code == 200:
                for t in resp.json()[:5]:
                    items.append(
                        HotItem(
                            title=t.get("title", ""),
                            url=t.get("url", ""),
                            source="v2ex",
                            extra={"replies": t.get("replies", 0)},
                        )
                    )
    except httpx.HTTPError:
        pass

    _set_cache("community", items)
    return items


async def get_all_hotspots() -> HotspotResponse:
    """聚合所有热点数据"""
    github = await fetch_github_trending()
    bilibili = await fetch_bilibili_hot()
    community = await fetch_community_posts()
    return HotspotResponse(github=github, bilibili=bilibili, community=community)
