"""Parser for Facebook data export (JSON format).

Supports:
- likes_and_reactions*.json — posts you liked/reacted to
- pages_you've_liked.json — pages you liked
- your_posts__check_ins__photos_and_videos*.json — your own posts
"""

import json
import logging
from datetime import datetime

logger = logging.getLogger("tousmeslikes")


def _fix_fb_encoding(text: str) -> str:
    """Fix Facebook's broken UTF-8 encoding (mojibake).

    Facebook exports encode UTF-8 chars as latin-1 bytes in JSON strings.
    e.g. "é" becomes "\u00c3\u00a9" instead of "\u00e9".
    """
    if not text:
        return text
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def _ts_to_iso(ts: int | None) -> str | None:
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(ts).isoformat()
    except (ValueError, OSError):
        return None


def parse_facebook_likes(text: str) -> list[dict]:
    """Parse Facebook likes_and_reactions JSON."""
    data = json.loads(text)
    if not isinstance(data, list):
        return []

    items = []
    for entry in data:
        url = ""
        reaction = ""
        author = ""
        name = ""

        for lv in entry.get("label_values", []):
            label = lv.get("label", "")
            value = lv.get("value", "")

            if label == "URL":
                url = value
            elif label == "Réaction" or label == "R\u00c3\u00a9action":
                reaction = _fix_fb_encoding(value)
            elif label == "Nom":
                name = _fix_fb_encoding(value)

            # Nested dict for owner info
            if "dict" in lv:
                for d in lv["dict"]:
                    for dd in d.get("dict", []):
                        if dd.get("label") == "Nom":
                            author = _fix_fb_encoding(dd.get("value", ""))

        if not author and name:
            author = name

        title = f"{reaction} — {author}" if author else reaction or ""
        title = title[:120] if title else None

        items.append({
            "platform": "facebook",
            "type": "reaction",
            "title": title,
            "content": _fix_fb_encoding(reaction),
            "url": url,
            "author": author,
            "created_at": _ts_to_iso(entry.get("timestamp")),
            "raw_json": json.dumps(entry, ensure_ascii=False),
        })

    logger.info(f"[parser] Facebook likes/reactions: {len(items)} items parsed")
    return items


def parse_facebook_pages(text: str) -> list[dict]:
    """Parse Facebook pages_you've_liked JSON."""
    data = json.loads(text)

    pages = data.get("page_likes_v2", [])
    if not pages:
        # Try as raw list
        if isinstance(data, list):
            pages = data

    items = []
    for page in pages:
        name = _fix_fb_encoding(page.get("name", ""))
        url = page.get("url", "")

        items.append({
            "platform": "facebook",
            "type": "page_like",
            "title": name[:120] if name else None,
            "content": name,
            "url": url,
            "author": None,
            "created_at": _ts_to_iso(page.get("timestamp")),
            "raw_json": json.dumps(page, ensure_ascii=False),
        })

    logger.info(f"[parser] Facebook pages liked: {len(items)} items parsed")
    return items


def parse_facebook_posts(text: str) -> list[dict]:
    """Parse Facebook your_posts JSON."""
    data = json.loads(text)
    if not isinstance(data, list):
        return []

    items = []
    for entry in data:
        # Extract post text from data array
        post_text = ""
        for d in entry.get("data", []):
            if "post" in d:
                post_text = _fix_fb_encoding(d["post"])
                break

        title_raw = _fix_fb_encoding(entry.get("title", ""))

        # Extract external URL from attachments
        url = ""
        for att in entry.get("attachments", []):
            for d in att.get("data", []):
                ext_ctx = d.get("external_context", {})
                if ext_ctx.get("url"):
                    url = ext_ctx["url"]
                    break

        content = post_text or title_raw or ""
        title = (post_text[:120] if post_text else title_raw[:120]) if (post_text or title_raw) else None

        items.append({
            "platform": "facebook",
            "type": "post",
            "title": title,
            "content": content,
            "url": url,
            "author": "me",
            "created_at": _ts_to_iso(entry.get("timestamp")),
            "raw_json": json.dumps(entry, ensure_ascii=False),
        })

    logger.info(f"[parser] Facebook posts: {len(items)} items parsed")
    return items


def parse_facebook_comments(text: str) -> list[dict]:
    """Parse Facebook comments.json (comments_v2 format)."""
    data = json.loads(text)

    entries = data.get("comments_v2", [])
    if not entries and isinstance(data, list):
        entries = data

    items = []
    for entry in entries:
        title_raw = _fix_fb_encoding(entry.get("title", ""))

        # Extract comment text from data array
        comment_text = ""
        for d in entry.get("data", []):
            if "comment" in d:
                c = d["comment"]
                if isinstance(c, dict):
                    comment_text = _fix_fb_encoding(c.get("comment", ""))
                elif isinstance(c, str):
                    comment_text = _fix_fb_encoding(c)
                break

        content = comment_text or title_raw
        title = content[:120] if content else None

        items.append({
            "platform": "facebook",
            "type": "comment",
            "title": title,
            "content": content,
            "url": "",
            "author": "me",
            "created_at": _ts_to_iso(entry.get("timestamp")),
            "raw_json": json.dumps(entry, ensure_ascii=False),
        })

    logger.info(f"[parser] Facebook comments: {len(items)} items parsed")
    return items


def parse_facebook_group_posts(text: str) -> list[dict]:
    """Parse Facebook group_posts_and_comments.json (group_posts_v2 format)."""
    data = json.loads(text)

    entries = data.get("group_posts_v2", [])
    if not entries and isinstance(data, list):
        entries = data

    items = []
    for entry in entries:
        title_raw = _fix_fb_encoding(entry.get("title", ""))

        # Extract post text
        post_text = ""
        for d in entry.get("data", []):
            if "post" in d:
                post_text = _fix_fb_encoding(d["post"])
                break

        # Extract URL from attachments
        url = ""
        for att in entry.get("attachments", []):
            for d in att.get("data", []):
                ext_ctx = d.get("external_context", {})
                if ext_ctx.get("url"):
                    url = ext_ctx["url"]
                    break

        content = post_text or title_raw
        title = content[:120] if content else None

        items.append({
            "platform": "facebook",
            "type": "group_post",
            "title": title,
            "content": content,
            "url": url,
            "author": "me",
            "created_at": _ts_to_iso(entry.get("timestamp")),
            "raw_json": json.dumps(entry, ensure_ascii=False),
        })

    logger.info(f"[parser] Facebook group posts: {len(items)} items parsed")
    return items


def parse_facebook_group_comments(text: str) -> list[dict]:
    """Parse Facebook your_comments_in_groups.json (group_comments_v2 format)."""
    data = json.loads(text)

    entries = data.get("group_comments_v2", [])
    if not entries and isinstance(data, list):
        entries = data

    items = []
    for entry in entries:
        title_raw = _fix_fb_encoding(entry.get("title", ""))

        comment_text = ""
        group_name = ""
        for d in entry.get("data", []):
            if "comment" in d:
                c = d["comment"]
                if isinstance(c, dict):
                    comment_text = _fix_fb_encoding(c.get("comment", ""))
                    group_name = _fix_fb_encoding(c.get("group", ""))
                break

        content = comment_text or title_raw
        title = f"[{group_name}] {content[:100]}" if group_name else content[:120]
        title = title[:120] if title else None

        items.append({
            "platform": "facebook",
            "type": "group_comment",
            "title": title,
            "content": content,
            "url": "",
            "author": "me",
            "created_at": _ts_to_iso(entry.get("timestamp")),
            "raw_json": json.dumps(entry, ensure_ascii=False),
        })

    logger.info(f"[parser] Facebook group comments: {len(items)} items parsed")
    return items


def parse_facebook_other_pages_posts(text: str) -> list[dict]:
    """Parse Facebook posts_on_other_pages_and_profiles.json (label_values format)."""
    data = json.loads(text)
    if not isinstance(data, list):
        return []

    items = []
    for entry in data:
        message = ""
        for lv in entry.get("label_values", []):
            if lv.get("label") == "Message":
                message = _fix_fb_encoding(lv.get("value", ""))
                break

        content = message
        title = content[:120] if content else None

        items.append({
            "platform": "facebook",
            "type": "wall_post",
            "title": title,
            "content": content,
            "url": "",
            "author": "me",
            "created_at": _ts_to_iso(entry.get("timestamp")),
            "raw_json": json.dumps(entry, ensure_ascii=False),
        })

    logger.info(f"[parser] Facebook other pages posts: {len(items)} items parsed")
    return items
