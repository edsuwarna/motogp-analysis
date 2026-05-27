"""
F1-style RSS news aggregation for MotoGP.
"""

import asyncio
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from fastapi import APIRouter

router = APIRouter()

SOURCES = [
    {"name": "Crash.net", "url": "https://www.crash.net/rss/motogp", "icon": "🏁"},
    {"name": "Motorsport", "url": "https://www.motorsport.com/rss/motogp/news/", "icon": "⚡"},
    {"name": "The Guardian", "url": "https://www.theguardian.com/sport/motogp/rss", "icon": "📰"},
    {"name": "RaceFans", "url": "https://www.racefans.net/feed/", "icon": "🌍"},
]

CACHE_TTL = 900
_cache = {"data": None, "ts": 0, "errors": []}


def _fetch_feed(source: dict) -> list:
    items = []
    try:
        req = urllib.request.Request(
            source["url"],
            headers={"User-Agent": "MotoGPAnalysis/1.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read()
        root = ET.fromstring(content)
        channel = root.find("channel")
        entries = channel.findall("item") if channel is not None else root.findall("{http://www.w3.org/2005/Atom}entry")

        for item in entries:
            if channel is not None:
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                desc_raw = item.findtext("description", "") or ""
                pub_date = item.findtext("pubDate", "") or ""
                thumb = ""
                ns = {"media": "http://search.yahoo.com/mrss/"}
                media = item.find("media:thumbnail", ns)
                if media is not None:
                    thumb = media.get("url", "")
                if not thumb:
                    mc = item.find("media:content", ns)
                    if mc is not None and mc.get("type", "").startswith("image"):
                        thumb = mc.get("url", "")
            else:
                title_el = item.find("{http://www.w3.org/2005/Atom}title")
                title = title_el.text.strip() if title_el is not None and title_el.text else ""
                link_el = item.find("{http://www.w3.org/2005/Atom}link")
                link = link_el.get("href", "") if link_el is not None else ""
                desc_el = item.find("{http://www.w3.org/2005/Atom}summary")
                desc_raw = desc_el.text.strip() if desc_el is not None and desc_el.text else ""
                pub_date = item.findtext("{http://www.w3.org/2005/Atom}updated", "")
                thumb = ""

            if not title:
                continue

            desc = re.sub(r"<[^>]+>", "", desc_raw).strip()[:300] if desc_raw else ""

            # Filter MotoGP content
            if not any(kw in title.lower() or kw in desc.lower()
                       for kw in ["motogp", "moto2", "moto3", "marquez", "bagnaia",
                                  "quar", "viñales", "ducati", "aprilia", "yamaha",
                                  "honda", "ktm", "bezz", "acosta", "martin",
                                  "bradl", "binder", "miller", "aleix"]):
                continue

            items.append({
                "title": title,
                "link": link,
                "description": desc,
                "pub_date": pub_date,
                "thumbnail": thumb,
                "source": source["name"],
                "source_icon": source["icon"],
            })
    except Exception as e:
        raise

    return items


async def fetch_all() -> list:
    loop = asyncio.get_event_loop()
    tasks = [loop.run_in_executor(None, _fetch_feed, s) for s in SOURCES]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    merged = []
    for source, result in zip(SOURCES, results):
        if isinstance(result, Exception):
            print(f"[News] {source['name']}: {result}")
        else:
            merged.extend(result)

    merged.sort(key=lambda x: x.get("pub_date", ""), reverse=True)
    return merged


@router.get("/news")
async def get_news(refresh: bool = False):
    global _cache
    now = time.time()

    if not refresh and _cache["data"] and (now - _cache["ts"] < CACHE_TTL):
        return {"articles": _cache["data"], "cached": True}

    articles = await fetch_all()
    _cache = {"data": articles, "ts": now, "errors": []}
    return {"articles": articles, "cached": False}
