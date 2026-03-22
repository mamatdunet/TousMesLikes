"""Parser for ChatGPT export files.

ChatGPT data export contains conversations.json with all conversations.
"""

import json


def parse_chatgpt(file_content: str) -> list[dict]:
    data = json.loads(file_content)
    items = []

    conversations = data if isinstance(data, list) else [data]

    for convo in conversations:
        title = convo.get("title", "Untitled conversation")
        create_time = convo.get("create_time")

        # Extract all message contents from the conversation
        messages_text = []
        mapping = convo.get("mapping", {})
        for node in mapping.values():
            msg = node.get("message")
            if not msg:
                continue
            content = msg.get("content", {})
            parts = content.get("parts", [])
            for part in parts:
                if isinstance(part, str) and part.strip():
                    messages_text.append(part.strip())

        full_content = "\n\n".join(messages_text)

        items.append({
            "platform": "chatgpt",
            "type": "conversation",
            "title": title[:120],
            "content": full_content,
            "url": "",
            "author": "ChatGPT",
            "created_at": str(create_time) if create_time else None,
            "raw_json": json.dumps({"title": title, "id": convo.get("id")}),
        })

    return items
