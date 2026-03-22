"""Parser for YouTube Google Takeout export.

Supports:
- watch-history.json — videos watched
- likes.json or likes.csv — liked videos
- Playlist-*.csv or playlist JSON — playlist videos
- my-comments.html — comments posted
"""

import csv
import io
import json
import logging
import re
from datetime import datetime

logger = logging.getLogger("tousmeslikes")


def _extract_video_id(url: str) -> str | None:
    """Extract YouTube video ID from URL."""
    if not url:
        return None
    m = re.search(r"[?&]v=([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else None


def parse_youtube_watch_history(text: str) -> list[dict]:
    """Parse YouTube watch-history.json from Google Takeout."""
    data = json.loads(text)
    if not isinstance(data, list):
        return []

    items = []
    for entry in data:
        if entry.get("header") != "YouTube":
            continue

        raw_title = entry.get("title", "")
        url = entry.get("titleUrl", "")
        timestamp = entry.get("time", "")

        # Strip "Watched " prefix
        title = raw_title
        if title.startswith("Watched "):
            title = title[8:]

        # Skip removed/unavailable videos
        if "a video that has been removed" in title.lower():
            continue

        # Channel info
        channel = ""
        subtitles = entry.get("subtitles", [])
        if subtitles and isinstance(subtitles, list):
            channel = subtitles[0].get("name", "")

        items.append({
            "platform": "youtube",
            "type": "watch",
            "title": title[:120] if title else None,
            "content": title,
            "url": url,
            "author": channel,
            "created_at": timestamp,
            "raw_json": json.dumps(entry, ensure_ascii=False),
        })

    logger.info(f"[parser] YouTube watch history: {len(items)} items parsed")
    return items


def parse_youtube_likes_json(text: str) -> list[dict]:
    """Parse YouTube likes as JSON (activity log format)."""
    data = json.loads(text)
    if not isinstance(data, list):
        return []

    items = []
    for entry in data:
        raw_title = entry.get("title", "") or entry.get("snippet", {}).get("title", "")
        url = entry.get("titleUrl", "")
        timestamp = entry.get("time", "")

        # Strip various prefixes
        title = raw_title
        for prefix in ("Liked a video: ", "Liked ", "Disliked a video: ", "Disliked "):
            if title.startswith(prefix):
                title = title[len(prefix):]
                break

        item_type = "dislike" if "dislik" in raw_title.lower() else "like"

        channel = ""
        subtitles = entry.get("subtitles", [])
        if subtitles and isinstance(subtitles, list):
            channel = subtitles[0].get("name", "")

        items.append({
            "platform": "youtube",
            "type": item_type,
            "title": title[:120] if title else None,
            "content": title,
            "url": url,
            "author": channel,
            "created_at": timestamp,
            "raw_json": json.dumps(entry, ensure_ascii=False),
        })

    logger.info(f"[parser] YouTube likes (JSON): {len(items)} items parsed")
    return items


def parse_youtube_likes_csv(text: str) -> list[dict]:
    """Parse YouTube likes/playlist CSV (Video Id, Time Added format or with more columns)."""
    reader = csv.DictReader(io.StringIO(text))
    items = []

    for row in reader:
        video_id = row.get("Video Id") or row.get("Video ID") or row.get("video_id", "")
        title = row.get("Title") or row.get("title", "")
        time_added = row.get("Time Added") or row.get("time_added", "")

        if not video_id or video_id == "Video Id":
            continue

        url = f"https://www.youtube.com/watch?v={video_id}" if video_id else ""

        items.append({
            "platform": "youtube",
            "type": "like",
            "title": title[:120] if title else video_id,
            "content": title or video_id,
            "url": url,
            "author": "",
            "created_at": time_added,
            "raw_json": json.dumps(row, ensure_ascii=False),
        })

    logger.info(f"[parser] YouTube likes (CSV): {len(items)} items parsed")
    return items


def parse_youtube_playlist(text: str) -> list[dict]:
    """Parse YouTube playlist CSV or JSON."""
    # Try JSON first
    try:
        data = json.loads(text)
        if isinstance(data, list):
            items = []
            for entry in data:
                raw_title = entry.get("title", "")
                url = entry.get("titleUrl", "")
                timestamp = entry.get("time", "")

                title = raw_title
                for prefix in ("Added a video to a playlist: ", "Added "):
                    if title.startswith(prefix):
                        title = title[len(prefix):]
                        break

                channel = ""
                subtitles = entry.get("subtitles", [])
                if subtitles and isinstance(subtitles, list):
                    channel = subtitles[0].get("name", "")

                items.append({
                    "platform": "youtube",
                    "type": "playlist",
                    "title": title[:120] if title else None,
                    "content": title,
                    "url": url,
                    "author": channel,
                    "created_at": timestamp,
                    "raw_json": json.dumps(entry, ensure_ascii=False),
                })

            logger.info(f"[parser] YouTube playlist (JSON): {len(items)} items parsed")
            return items
    except (json.JSONDecodeError, ValueError):
        pass

    # Fall back to CSV
    reader = csv.DictReader(io.StringIO(text))
    items = []

    for row in reader:
        video_id = row.get("Video Id") or row.get("Video ID") or ""
        title = row.get("Title") or ""
        time_added = row.get("Time Added") or ""
        playlist_id = row.get("Playlist ID") or ""

        if not video_id:
            continue

        url = f"https://www.youtube.com/watch?v={video_id}" if video_id else ""

        items.append({
            "platform": "youtube",
            "type": "playlist",
            "title": title[:120] if title else video_id,
            "content": title or video_id,
            "url": url,
            "author": "",
            "created_at": time_added,
            "raw_json": json.dumps(row, ensure_ascii=False),
        })

    logger.info(f"[parser] YouTube playlist (CSV): {len(items)} items parsed")
    return items


def parse_youtube_comments_html(text: str) -> list[dict]:
    """Parse YouTube my-comments.html from Google Takeout."""
    items = []

    # Pattern: <li> block with <a href="URL">link</a><br>comment text<br>timestamp</li>
    # The HTML structure varies but generally:
    # <li><a href="...">...</a><br>COMMENT_TEXT<br>TIMESTAMP</li>
    pattern = re.compile(
        r'<li[^>]*>.*?<a[^>]*href="([^"]*)"[^>]*>.*?</a>\s*<br>\s*(.*?)\s*<br>\s*(\d{4}-\d{2}-\d{2}T[^\s<]+)',
        re.DOTALL | re.IGNORECASE,
    )

    for match in pattern.finditer(text):
        url = match.group(1)
        comment = match.group(2).strip()
        timestamp = match.group(3).strip()

        # Clean HTML from comment
        comment = re.sub(r"<[^>]+>", "", comment).strip()

        if not comment:
            continue

        items.append({
            "platform": "youtube",
            "type": "comment",
            "title": comment[:120],
            "content": comment,
            "url": url,
            "author": "me",
            "created_at": timestamp,
            "raw_json": json.dumps({"url": url, "comment": comment, "time": timestamp}, ensure_ascii=False),
        })

    logger.info(f"[parser] YouTube comments (HTML): {len(items)} items parsed")
    return items
