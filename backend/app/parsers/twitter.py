"""Parsers for Twitter/X export files.

Supports:
- like.js         (window.YTD.like.part0)     — likes
- tweet.js        (window.YTD.tweet.part0)     — own tweets
- tweets.js       (window.YTD.tweet.part0)     — own tweets (alternate name)
- bookmarks JSON  (third-party export, plain JSON array)
"""

import json
import re


def _strip_js_prefix(content: str) -> str:
    """Remove `window.YTD.<name>.partN = ` prefix from Twitter archive JS files."""
    content = content.strip()
    match = re.match(r"^window\.YTD\.\w+\.part\d+\s*=\s*", content)
    if match:
        content = content[match.end():]
    return content


def parse_twitter_likes(file_content: str) -> list[dict]:
    data = json.loads(_strip_js_prefix(file_content))
    items = []
    for entry in data:
        like = entry.get("like", entry)
        tweet_id = like.get("tweetId", "")
        full_text = like.get("fullText", "")
        expanded_url = like.get("expandedUrl", "")
        url = expanded_url or (f"https://x.com/i/status/{tweet_id}" if tweet_id else "")

        items.append({
            "platform": "twitter",
            "type": "like",
            "title": full_text[:120] if full_text else None,
            "content": full_text,
            "url": url,
            "author": None,
            "created_at": None,
            "raw_json": json.dumps(like),
        })
    return items


def parse_twitter_tweets(file_content: str) -> list[dict]:
    data = json.loads(_strip_js_prefix(file_content))
    items = []
    for entry in data:
        tweet = entry.get("tweet", entry)
        tweet_id = tweet.get("id_str", tweet.get("id", ""))
        full_text = tweet.get("full_text", tweet.get("text", ""))
        created_at = tweet.get("created_at")
        url = f"https://x.com/i/status/{tweet_id}" if tweet_id else ""

        # Extract hashtags
        entities = tweet.get("entities", {})
        hashtags = [h.get("text", "") for h in entities.get("hashtags", [])]

        items.append({
            "platform": "twitter",
            "type": "tweet",
            "title": full_text[:120] if full_text else None,
            "content": full_text,
            "url": url,
            "author": "moi",
            "created_at": created_at,
            "raw_json": json.dumps(tweet),
        })
    return items


def parse_twitter_bookmarks(file_content: str) -> list[dict]:
    """Parse bookmarks from third-party export tools (plain JSON or JS format)."""
    content = _strip_js_prefix(file_content)
    data = json.loads(content)
    items = []

    if not isinstance(data, list):
        data = [data]

    for entry in data:
        # Support various third-party export formats
        bookmark = entry.get("bookmark", entry)
        tweet_id = (
            bookmark.get("tweetId")
            or bookmark.get("id_str")
            or bookmark.get("id", "")
        )
        full_text = (
            bookmark.get("fullText")
            or bookmark.get("full_text")
            or bookmark.get("text", "")
        )
        url = (
            bookmark.get("expandedUrl")
            or bookmark.get("url")
            or (f"https://x.com/i/status/{tweet_id}" if tweet_id else "")
        )
        author = bookmark.get("author") or bookmark.get("username") or bookmark.get("screen_name")
        created_at = bookmark.get("created_at") or bookmark.get("date")

        items.append({
            "platform": "twitter",
            "type": "bookmark",
            "title": full_text[:120] if full_text else None,
            "content": full_text,
            "url": url,
            "author": author,
            "created_at": created_at,
            "raw_json": json.dumps(bookmark),
        })
    return items
