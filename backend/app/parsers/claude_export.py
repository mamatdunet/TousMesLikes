"""Parser for Claude conversation export files.

Claude export is typically JSON with conversation data.
"""

import json


def parse_claude(file_content: str) -> list[dict]:
    data = json.loads(file_content)
    items = []

    conversations = data if isinstance(data, list) else [data]

    for convo in conversations:
        title = convo.get("name", convo.get("title", "Untitled"))
        created_at = convo.get("created_at", convo.get("created"))

        # Extract messages
        messages_text = []
        for msg in convo.get("chat_messages", convo.get("messages", [])):
            text = msg.get("text", "")
            if isinstance(text, str) and text.strip():
                messages_text.append(text.strip())
            # Handle content blocks
            for block in msg.get("content", []):
                if isinstance(block, dict) and block.get("text"):
                    messages_text.append(block["text"].strip())

        full_content = "\n\n".join(messages_text)

        items.append({
            "platform": "claude",
            "type": "conversation",
            "title": title[:120] if title else None,
            "content": full_content,
            "url": "",
            "author": "Claude",
            "created_at": created_at,
            "raw_json": json.dumps({"title": title, "uuid": convo.get("uuid")}),
        })

    return items
