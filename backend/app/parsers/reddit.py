"""Parser for Reddit export files.

Reddit GDPR export contains CSV files for upvoted/saved posts and comments.
"""

import csv
import json
import io


def parse_reddit(file_content: str) -> list[dict]:
    items = []

    # Try JSON first (some tools export as JSON)
    try:
        data = json.loads(file_content)
        if isinstance(data, list):
            for entry in data:
                items.append({
                    "platform": "reddit",
                    "type": entry.get("type", "upvote"),
                    "title": entry.get("title", "")[:120] if entry.get("title") else None,
                    "content": entry.get("body") or entry.get("title", ""),
                    "url": entry.get("permalink") or entry.get("url", ""),
                    "author": entry.get("author", ""),
                    "created_at": entry.get("date") or entry.get("created_utc"),
                    "raw_json": json.dumps(entry),
                })
            return items
    except (json.JSONDecodeError, ValueError):
        pass

    # CSV format (Reddit GDPR export)
    reader = csv.DictReader(io.StringIO(file_content))
    for row in reader:
        permalink = row.get("permalink", row.get("url", ""))
        items.append({
            "platform": "reddit",
            "type": "upvote",
            "title": row.get("title", "")[:120] if row.get("title") else None,
            "content": row.get("body") or row.get("title", ""),
            "url": f"https://reddit.com{permalink}" if permalink.startswith("/") else permalink,
            "author": row.get("author", ""),
            "created_at": row.get("date", None),
            "raw_json": json.dumps(dict(row)),
        })

    return items
