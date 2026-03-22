"""Parser for LinkedIn data export files (Complete export).

Supports:
- Reactions.csv — posts you liked/reacted to
- Comments.csv — comments you posted
- Shares.csv — your own posts/shares
- SavedItems.csv (or "Saved Items.csv") — saved/bookmarked posts
"""

import csv
import json
import io
import logging

logger = logging.getLogger("tousmeslikes")


def parse_linkedin(file_content: str) -> list[dict]:
    """Legacy parser — tries to auto-detect the LinkedIn file type."""
    items = []

    # Try JSON first
    try:
        data = json.loads(file_content)
        if isinstance(data, list):
            for entry in data:
                items.append({
                    "platform": "linkedin",
                    "type": entry.get("type", "like"),
                    "title": entry.get("title", "")[:120] if entry.get("title") else None,
                    "content": entry.get("text") or entry.get("commentary") or entry.get("title", ""),
                    "url": entry.get("link") or entry.get("url", ""),
                    "author": entry.get("author", ""),
                    "created_at": entry.get("date") or entry.get("created_at"),
                    "raw_json": json.dumps(entry),
                })
            return items
    except (json.JSONDecodeError, ValueError):
        pass

    # Try CSV — auto-detect type from headers
    reader = csv.DictReader(io.StringIO(file_content))
    headers = reader.fieldnames or []

    if "Message" in headers and "Link" in headers:
        return parse_linkedin_comments(file_content)
    elif "ShareCommentary" in headers or "ShareLink" in headers:
        return parse_linkedin_shares(file_content)
    elif "Type" in headers and "Link" in headers:
        return parse_linkedin_reactions(file_content)
    else:
        # Generic CSV fallback
        for row in reader:
            items.append({
                "platform": "linkedin",
                "type": row.get("Type", "like").lower() if row.get("Type") else "like",
                "title": None,
                "content": row.get("Link", "") or row.get("Message", ""),
                "url": row.get("Link", ""),
                "author": None,
                "created_at": row.get("Date", None),
                "raw_json": json.dumps(dict(row)),
            })

    return items


def parse_linkedin_reactions(file_content: str) -> list[dict]:
    """Parse LinkedIn Reactions.csv — posts you liked/reacted to."""
    reader = csv.DictReader(io.StringIO(file_content))
    items = []

    for row in reader:
        reaction_type = (row.get("Type") or "like").lower()
        url = row.get("Link", "")

        items.append({
            "platform": "linkedin",
            "type": reaction_type,
            "title": f"{reaction_type} — {url[:80]}" if url else reaction_type,
            "content": url,
            "url": url,
            "author": None,
            "created_at": row.get("Date"),
            "raw_json": json.dumps(dict(row)),
        })

    logger.info(f"[parser] LinkedIn reactions: {len(items)} items parsed")
    return items


def parse_linkedin_comments(file_content: str) -> list[dict]:
    """Parse LinkedIn Comments.csv — comments you posted."""
    reader = csv.DictReader(io.StringIO(file_content))
    items = []

    for row in reader:
        message = row.get("Message", "")
        url = row.get("Link", "")

        items.append({
            "platform": "linkedin",
            "type": "comment",
            "title": message[:120] if message else None,
            "content": message,
            "url": url,
            "author": "me",
            "created_at": row.get("Date"),
            "raw_json": json.dumps(dict(row)),
        })

    logger.info(f"[parser] LinkedIn comments: {len(items)} items parsed")
    return items


def parse_linkedin_shares(file_content: str) -> list[dict]:
    """Parse LinkedIn Shares.csv — your own posts/shares."""
    reader = csv.DictReader(io.StringIO(file_content))
    items = []

    for row in reader:
        commentary = row.get("ShareCommentary", "")
        share_url = row.get("ShareLink", "")
        shared_url = row.get("SharedUrl", "")
        media_url = row.get("MediaUrl", "")

        content = commentary
        if shared_url and shared_url not in commentary:
            content = f"{commentary}\n{shared_url}" if commentary else shared_url

        items.append({
            "platform": "linkedin",
            "type": "post",
            "title": commentary[:120] if commentary else shared_url[:120] if shared_url else None,
            "content": content,
            "url": share_url,
            "author": "me",
            "created_at": row.get("Date"),
            "raw_json": json.dumps(dict(row)),
        })

    logger.info(f"[parser] LinkedIn shares: {len(items)} items parsed")
    return items


def parse_linkedin_saved(file_content: str) -> list[dict]:
    """Parse LinkedIn SavedItems.csv — saved/bookmarked posts."""
    reader = csv.DictReader(io.StringIO(file_content))
    items = []

    for row in reader:
        url = row.get("Link", "") or row.get("Url", "")
        title = row.get("Title", "") or row.get("Content", "")

        items.append({
            "platform": "linkedin",
            "type": "saved",
            "title": title[:120] if title else url[:120] if url else None,
            "content": title or url,
            "url": url,
            "author": None,
            "created_at": row.get("Date"),
            "raw_json": json.dumps(dict(row)),
        })

    logger.info(f"[parser] LinkedIn saved items: {len(items)} items parsed")
    return items
