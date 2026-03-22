"""Parser for Instagram export files.

Instagram data export contains JSON files for liked posts, comments, etc.
Supports both older (string_list_data) and newer (label_values) export formats.
"""

import json


def _extract_from_label_values(entry: dict) -> dict:
    """Extract URL, author, and profile from the label_values format."""
    url = ""
    author = ""
    profile = ""

    for lv in entry.get("label_values", []):
        label = lv.get("label", "")
        value = lv.get("value", "")
        href = lv.get("href", "")

        if label == "URL":
            url = href or value

        # Nested dict contains owner info
        for d in lv.get("dict", []):
            for inner in d.get("dict", []):
                inner_label = inner.get("label", "")
                inner_value = inner.get("value", "")
                if inner_label == "Nom de profil":
                    profile = inner_value
                elif inner_label == "Nom":
                    author = inner_value
                elif inner_label == "URL" and not url:
                    url = inner_value

    return {"url": url, "author": author, "profile": profile}


def parse_instagram(file_content: str) -> list[dict]:
    data = json.loads(file_content)
    items = []

    # Instagram liked_posts.json format
    likes_list = data if isinstance(data, list) else data.get("likes_media_likes", data.get("likes", []))

    for entry in likes_list:
        # New format with label_values
        if isinstance(entry, dict) and "label_values" in entry:
            info = _extract_from_label_values(entry)
            timestamp = entry.get("timestamp")
            title = info["author"] or info["profile"] or ""
            if info["profile"]:
                title = f"{info['author']} (@{info['profile']})" if info["author"] else f"@{info['profile']}"

            items.append({
                "platform": "instagram",
                "type": "like",
                "title": title[:120] if title else None,
                "content": title,
                "url": info["url"],
                "author": info["profile"] or info["author"],
                "created_at": str(timestamp) if timestamp else None,
                "raw_json": json.dumps(entry),
            })

        # Older format with string_list_data
        elif isinstance(entry, dict) and "string_list_data" in entry:
            for item in entry.get("string_list_data", []):
                href = item.get("href", "")
                value = item.get("value", "")
                timestamp = item.get("timestamp")
                items.append({
                    "platform": "instagram",
                    "type": "like",
                    "title": entry.get("title", value[:120] if value else None),
                    "content": value or entry.get("title", ""),
                    "url": href,
                    "author": entry.get("title", ""),
                    "created_at": str(timestamp) if timestamp else None,
                    "raw_json": json.dumps(entry),
                })
        else:
            # Simpler format
            items.append({
                "platform": "instagram",
                "type": "like",
                "title": entry.get("title", "")[:120] if entry.get("title") else None,
                "content": entry.get("caption", entry.get("title", "")),
                "url": entry.get("url", ""),
                "author": entry.get("author", entry.get("username", "")),
                "created_at": entry.get("taken_at") or entry.get("timestamp"),
                "raw_json": json.dumps(entry),
            })

    return items
