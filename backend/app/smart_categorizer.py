"""Smart categorization using Ollama LLM (text) and LLaVA (images).

Run as a standalone script:
    python -m app.smart_categorizer
"""

import json
import logging
import os
import sys
from pathlib import Path

import ollama as _ollama

sys.path.insert(0, str(Path(__file__).parent.parent))
from app.database import get_db
import time as _time


def _exec_with_retry(conn, sql, params=(), max_retries=20, delay=2):
    """Execute SQL with retries in case DB is locked."""
    for attempt in range(max_retries):
        try:
            return conn.execute(sql, params)
        except Exception as e:
            if "locked" in str(e).lower() and attempt < max_retries - 1:
                _time.sleep(delay)
            else:
                raise


def _commit_with_retry(conn, max_retries=30, delay=3):
    """Commit with retries in case DB is locked by another process."""
    for attempt in range(max_retries):
        try:
            conn.commit()
            return
        except Exception as e:
            if "locked" in str(e).lower() and attempt < max_retries - 1:
                logger.debug(f"DB locked, retry {attempt + 1}/{max_retries}...")
                _time.sleep(delay)
            else:
                raise

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("smart_categorizer")

CHAT_MODEL = "mistral"
VISION_MODEL = "llava"
MEDIA_PATH = Path(__file__).parent.parent / "data" / "media"

CATEGORIZE_PROMPT = """Tu es un expert en catégorisation de contenu. Analyse les contenus suivants et attribue 1 à 3 catégories pertinentes à chacun.

Utilise des catégories claires et concises en français (ex: "IA & Machine Learning", "Cartographie", "Art & Design", "Politique", "Humour", "Transport", "Urbanisme", "Impression 3D", "Musique", "Science", "Éducation", "Histoire", "Environnement", "Gastronomie", "Photographie", "Architecture", "Jeux vidéo", "Open Source", "Santé", "Économie", "Sport", etc.).

Ne te limite PAS à cette liste — invente des catégories si le contenu le mérite. Sois précis : préfère "Cartographie interactive" à "Technologie", préfère "Rénovation urbaine" à "Société".

Réponds UNIQUEMENT au format JSON, un objet où les clés sont les IDs et les valeurs sont des listes de catégories :

{"id1": ["Catégorie1", "Catégorie2"], "id2": ["Catégorie3"]}

Contenus à catégoriser :
"""

IMAGE_PROMPT = """Décris cette image en une phrase courte et précise en français.
Indique le sujet principal, le contexte, et si pertinent le style (photo, illustration, capture d'écran, mème, etc.).
Réponds uniquement avec la description, rien d'autre."""


def categorize_text_batch(items: list[dict]) -> dict[int, list[str]]:
    """Categorize a batch of items using Mistral LLM."""
    content_parts = []
    for item in items:
        text = item.get("content") or item.get("title") or ""
        if len(text) < 10:
            continue
        # Truncate to save context
        text = text[:300]
        content_parts.append(f'[ID:{item["id"]}] {text}')

    if not content_parts:
        return {}

    prompt = CATEGORIZE_PROMPT + "\n".join(content_parts)

    try:
        response = _ollama.chat(
            model=CHAT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.3, "num_predict": 2000},
        )
        answer = response.message.content.strip()

        # Extract JSON from response (may have markdown fences)
        if "```" in answer:
            import re
            m = re.search(r"```(?:json)?\s*(.*?)```", answer, re.DOTALL)
            if m:
                answer = m.group(1).strip()

        # Try to fix common JSON issues from LLM
        answer = answer.replace("'", '"')  # single to double quotes
        # Remove trailing commas before } or ]
        import re as _re
        answer = _re.sub(r',\s*([}\]])', r'\1', answer)

        try:
            result = json.loads(answer)
        except json.JSONDecodeError:
            # Try extracting individual assignments with regex
            result = {}
            for m in _re.finditer(r'"?(\d+)"?\s*:\s*\[([^\]]*)\]', answer):
                item_id = m.group(1)
                cats = [c.strip().strip('"').strip("'") for c in m.group(2).split(',') if c.strip()]
                if cats:
                    result[item_id] = cats

        # Convert string IDs to int
        assignments = {}
        for k, v in result.items():
            try:
                item_id = int(str(k).replace("id", "").replace("ID:", "").strip())
                if isinstance(v, list):
                    assignments[item_id] = [str(c) for c in v[:3]]
            except (ValueError, TypeError):
                pass

        return assignments

    except Exception as e:
        logger.error(f"LLM categorization error: {e}")
        return {}


def describe_image(image_path: str) -> str:
    """Describe an image using LLaVA vision model."""
    try:
        response = _ollama.chat(
            model=VISION_MODEL,
            messages=[{
                "role": "user",
                "content": IMAGE_PROMPT,
                "images": [image_path],
            }],
            options={"temperature": 0.2, "num_predict": 150},
        )
        return response.message.content.strip()
    except Exception as e:
        logger.debug(f"Image description error for {image_path}: {e}")
        return ""


def find_item_images(item: dict) -> list[str]:
    """Find local image files associated with an item."""
    import re
    item_id = item["id"]
    platform = item.get("platform", "")

    patterns = []
    if platform == "twitter":
        tweet_id = None
        m = re.search(r"/status/(\d+)", item.get("url", ""))
        if m:
            tweet_id = m.group(1)
        if not tweet_id:
            try:
                raw = json.loads(item.get("raw_json", "{}"))
                tweet_id = raw.get("tweetId")
            except:
                pass
        if tweet_id:
            patterns.append(f"{tweet_id}-*")
    elif platform == "reddit":
        try:
            raw = json.loads(item.get("raw_json", "{}"))
            post_id = raw.get("id", "")
            if post_id:
                patterns.append(f"reddit_{post_id}_*")
        except:
            pass
    elif platform == "instagram":
        patterns.append(f"ig_{item_id}_*")
    elif platform == "facebook":
        patterns.append(f"fb_{item_id}_*")
    elif platform == "linkedin":
        patterns.append(f"li_{item_id}_*")

    images = []
    for pattern in patterns:
        for f in MEDIA_PATH.glob(pattern):
            if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
                images.append(str(f))
    return images[:3]  # Max 3 images per item


def run_smart_categorization():
    """Run full smart categorization: text + images."""
    import sqlite3
    conn = sqlite3.connect(str(Path(__file__).parent.parent / "data" / "tousmeslikes.db"), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")

    # Get all items
    rows = conn.execute("SELECT * FROM items").fetchall()
    all_items = [dict(r) for r in rows]
    logger.info(f"Total items: {len(all_items)}")

    # === PHASE 1: Text categorization via LLM ===
    logger.info("=== Phase 1: Text categorization via Mistral ===")

    # Process items that have content (>10 chars)
    items_with_text = [i for i in all_items if len(i.get("content") or i.get("title") or "") > 10]
    logger.info(f"Items with text: {len(items_with_text)}")

    batch_size = 15  # ~15 items per LLM call for context efficiency
    total_categorized = 0

    for batch_start in range(0, len(items_with_text), batch_size):
        batch = items_with_text[batch_start:batch_start + batch_size]

        assignments = categorize_text_batch(batch)

        # Save to DB
        for item_id, categories in assignments.items():
            _exec_with_retry(conn,
                "UPDATE items SET categories = ? WHERE id = ?",
                (json.dumps(categories, ensure_ascii=False), item_id),
            )
            total_categorized += 1

        if (batch_start + batch_size) % 150 == 0 or batch_start + batch_size >= len(items_with_text):
            _commit_with_retry(conn)
            logger.info(f"Text categorization: {min(batch_start + batch_size, len(items_with_text))}/{len(items_with_text)} ({total_categorized} categorized)")

    _commit_with_retry(conn)
    logger.info(f"Phase 1 done: {total_categorized} items categorized via LLM")

    # === PHASE 2: Image analysis via LLaVA ===
    has_llava = any(VISION_MODEL in m for m in [m.model for m in _ollama.list().models])
    if not has_llava:
        logger.info("LLaVA not available, skipping image analysis")
        conn.close()
        return

    logger.info("=== Phase 2: Image analysis via LLaVA ===")

    # Find items that have images but short/no content
    items_for_vision = [
        i for i in all_items
        if len(i.get("content") or "") < 50  # Short or no text content
    ]

    described = 0
    for i, item in enumerate(items_for_vision):
        images = find_item_images(item)
        if not images:
            continue

        # Describe first image
        desc = describe_image(images[0])
        if not desc:
            continue

        # Append description to content
        current_content = item.get("content") or ""
        new_content = f"{current_content}\n[Image: {desc}]" if current_content else f"[Image: {desc}]"
        new_title = item.get("title") or desc[:120]

        _exec_with_retry(conn,
            "UPDATE items SET content = ?, title = COALESCE(NULLIF(title, ''), ?) WHERE id = ?",
            (new_content, new_title, item["id"]),
        )
        described += 1

        if (i + 1) % 20 == 0:
            _commit_with_retry(conn)
            logger.info(f"Image analysis: {i + 1}/{len(items_for_vision)} ({described} described)")

    _commit_with_retry(conn)
    logger.info(f"Phase 2 done: {described} images described via LLaVA")

    conn.close()
    logger.info("Smart categorization complete!")


if __name__ == "__main__":
    run_smart_categorization()
