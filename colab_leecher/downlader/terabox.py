# copyright 2024 © Xron Trix | https://github.com/Xrontrix10

import aiohttp
import logging
from colab_leecher.utility.variables import Aria2c
from colab_leecher.utility.handler import cancelTask
from colab_leecher.downlader.aria2 import aria2_Download


# The original API host (ytshorts.savetube.me) is dead (NXDOMAIN).
# These third-party Terabox resolvers are tried in order; they rot often,
# so this list may need updating over time (best-effort).
TERABOX_APIS = [
    "https://terabox.hnn.workers.dev/api/get-info?shorturl={link}",
    "https://ytshorts.savetube.me/api/v1/terabox-downloader",
]


async def terabox_download(link: str, index):
    global Aria2c
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    }
    download_url = None

    # Derive short key if full URL was provided (e.g. /s/<key> or surl=<key>)
    short_key = link
    if "/s/" in link:
        short_key = link.split("/s/")[-1].split("?")[0].strip("/")
    elif "surl=" in link:
        short_key = link.split("surl=")[-1].split("&")[0].strip()

    async with aiohttp.ClientSession() as session:
        for api in TERABOX_APIS:
            try:
                if "{link}" in api:
                    # Try short key first, fallback to full link if different
                    candidates = [short_key]
                    if short_key != link:
                        candidates.append(link)
                    for cand in candidates:
                        url = api.format(link=cand)
                        async with session.get(url, headers=headers) as response:
                            if response.status == 200:
                                json_response = await response.json(content_type=None)
                                download_url = _extract_download_url(json_response)
                                if download_url:
                                    break
                else:
                    payload = {"url": f"{link}"}
                    async with session.post(
                        api, data=payload, headers=headers
                    ) as response:
                        response.raise_for_status()
                        json_response = await response.json(content_type=None)
                        download_url = _extract_download_url(json_response)
            except Exception as e:
                logging.error(f"Terabox API {api} failed: {e}")
                download_url = None

            if download_url:
                break

    if not download_url:
        await cancelTask(
            "Couldn't generate Terabox download link ! The public Terabox "
            "APIs used by the bot are currently unavailable. Please try "
            "again later or download the file manually."
        )
        return

    logging.info(f"Terabox download link generated: {download_url[:100]}")
    Aria2c.link_info = False
    await aria2_Download(download_url, index)


def _extract_download_url(json_response):
    """Pull a direct download URL out of the various response shapes the
    different Terabox resolver APIs return."""
    # Normalize: some APIs wrap the payload in "response"/"files"/"list"/"data"
    items = json_response
    if isinstance(items, dict):
        for key in ("response", "files", "list", "data"):
            if key in items:
                if isinstance(items[key], list):
                    items = items[key]
                    break
                elif isinstance(items[key], dict):
                    items = [items[key]]
                    break
        else:
            items = [items]
    if not isinstance(items, list) or len(items) == 0:
        return None

    # Prefer the largest file entry (main video/file, not thumbnails)
    best = None
    best_size = -1
    for item in items:
        if not isinstance(item, dict):
            continue
        size = item.get("size") or 0
        if isinstance(size, str):
            try:
                size = float(size)
            except ValueError:
                size = 0
        if size >= best_size:
            best = item
            best_size = size
    if best is None:
        return None

    # Candidate URL fields used by the different APIs
    for key in ("dlink", "download_url", "downloadUrl", "url", "link", "Fast Download", "HD Video", "direct_link"):
        value = best.get(key)
        if isinstance(value, str) and value.startswith("http"):
            return value

    # Some APIs put resolutions in a nested dict
    resolutions = best.get("resolutions")
    if isinstance(resolutions, dict):
        for key in ("Fast Download", "HD Video", "Normal Video"):
            value = resolutions.get(key)
            if isinstance(value, str) and value.startswith("http"):
                return value
    return None
