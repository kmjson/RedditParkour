import re
import requests
from urllib.parse import urlparse


def fetch_reddit_post(url: str):
    url = url.strip().split("?")[0].rstrip("/")

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("URL must use http or https")
    hostname = parsed.hostname or ""
    if not re.fullmatch(r"(old\.|www\.)?reddit\.com", hostname):
        raise ValueError("URL must be a reddit.com link")

    # Normalise to www.reddit.com
    url = f"https://www.reddit.com{parsed.path}"
    json_url = url + ".json"

    headers = {"User-Agent": "reddit-parkour-video-app/1.0"}
    resp = requests.get(json_url, headers=headers, timeout=15)
    resp.raise_for_status()

    data = resp.json()
    post = data[0]["data"]["children"][0]["data"]
    title = post.get("title", "")
    selftext = post.get("selftext", "")

    if selftext in ("[deleted]", "[removed]", ""):
        selftext = ""

    return title, clean_reddit_text(selftext)


def clean_reddit_text(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)        # links
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)   # headers
    text = re.sub(r"\*{1,3}([^\*\n]+)\*{1,3}", r"\1", text)      # bold/italic
    text = re.sub(r"_{1,3}([^_\n]+)_{1,3}", r"\1", text)
    text = re.sub(r"~~([^~]+)~~", r"\1", text)                    # strikethrough
    text = re.sub(r"```[\s\S]*?```", "", text)                    # code blocks
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"^[-*_]{3,}$", "", text, flags=re.MULTILINE)   # hr
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
