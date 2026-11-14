"""TousMesLikes — API backend."""

import logging
import re
import threading
import time
import glob as globmod
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import json

from .database import init_db, get_db
from .media import MEDIA_PATH, find_media, media_names
from .parsers import PARSERS
from .enricher import (
    enrich_reddit_items, enrich_twitter_items, enrich_instagram_items,
    enrich_facebook_items, enrich_linkedin_items,
    APIFY_API_KEY, X_BEARER_TOKEN,
)
from .vector_store import add_items_to_vector_store, semantic_search, init_vector_store
from .categorizer import categorize_items
from . import ollama_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("tousmeslikes")

# Background indexing state
_indexing_state = {"running": False, "total": 0, "done": 0, "platform": None, "error": None}
_indexing_lock = threading.Lock()


def _background_index(db_items: list[dict], platform: str):
    """Index items into ChromaDB in background thread."""
    with _indexing_lock:
        _indexing_state.update(running=True, total=len(db_items), done=0, platform=platform, error=None)

    logger.info(f"[indexing] Starting background indexing of {len(db_items)} items from {platform}")
    batch_size = 50
    try:
        for i in range(0, len(db_items), batch_size):
            batch = db_items[i:i + batch_size]
            add_items_to_vector_store(batch)
            with _indexing_lock:
                _indexing_state["done"] = min(i + batch_size, len(db_items))
            logger.info(f"[indexing] Progress: {_indexing_state['done']}/{len(db_items)}")
    except Exception as e:
        logger.error(f"[indexing] Error: {e}")
        with _indexing_lock:
            _indexing_state["error"] = str(e)
    finally:
        with _indexing_lock:
            _indexing_state["running"] = False
        logger.info(f"[indexing] Done for {platform}")


_categorizing_state = {"running": False, "error": None}
_categorizing_lock = threading.Lock()


def _background_categorize():
    """Run topic modeling on all items in background."""
    with _categorizing_lock:
        _categorizing_state.update(running=True, error=None)

    logger.info("[categorize] Starting background categorization")
    try:
        conn = get_db()
        rows = conn.execute("SELECT * FROM items").fetchall()
        items = [dict(r) for r in rows]
        conn.close()

        if not items:
            logger.info("[categorize] No items to categorize")
            return

        result = categorize_items(items)

        # Save categories to DB
        conn = get_db()
        # Reset all categories first
        conn.execute("UPDATE items SET categories = '[]'")
        for item_id, labels in result["assignments"].items():
            conn.execute(
                "UPDATE items SET categories = ? WHERE id = ?",
                (json.dumps(labels, ensure_ascii=False), item_id),
            )
        conn.commit()
        conn.close()
        logger.info(f"[categorize] Done — {len(result['topics'])} topics, {len(result['assignments'])} items categorized")
    except Exception as e:
        logger.error(f"[categorize] Error: {e}")
        with _categorizing_lock:
            _categorizing_state["error"] = str(e)
    finally:
        with _categorizing_lock:
            _categorizing_state["running"] = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Auto-detect Ollama and enable better embeddings if available
    if ollama_client.is_ollama_available():
        has_embed = ollama_client.has_model(ollama_client.EMBED_MODEL)
        has_chat = ollama_client.has_model(ollama_client.CHAT_MODEL)
        logger.info(f"[ollama] Ollama detected! embed={has_embed}, chat={has_chat}")
        if has_embed:
            init_vector_store(use_ollama=True, embed_model=ollama_client.EMBED_MODEL)
        else:
            logger.info(f"[ollama] Run 'ollama pull {ollama_client.EMBED_MODEL}' for better semantic search")
            init_vector_store(use_ollama=False)
        if not has_chat:
            logger.info(f"[ollama] Run 'ollama pull {ollama_client.CHAT_MODEL}' for RAG chat")
    else:
        logger.info("[ollama] Ollama not detected — using default embeddings. Install Ollama for better search & chat.")
        init_vector_store(use_ollama=False)
    yield


app = FastAPI(title="TousMesLikes", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve media files statically
try:
    MEDIA_PATH.mkdir(parents=True, exist_ok=True)
except OSError as e:
    logger.warning(f"[media] Folder unavailable ({MEDIA_PATH}): {e}")
app.mount("/media", StaticFiles(directory=str(MEDIA_PATH), check_dir=False), name="media")


# ── Media lookup ──────────────────────────────────────────────────────────────

@app.get("/api/media/{tweet_id}")
def get_media_for_tweet(tweet_id: str):
    """Find all media files associated with a tweet ID."""
    files = find_media(f"{tweet_id}-")
    if not files:
        return {"media": []}

    media = []
    for f in sorted(files):
        ext = f.suffix.lower()
        if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
            media_type = "image"
        elif ext in (".mp4", ".webm", ".mov"):
            media_type = "video"
        else:
            media_type = "other"
        media.append({
            "filename": f.name,
            "url": f"/media/{f.name}",
            "type": media_type,
        })
    return {"media": media}


def _extract_tweet_id(url: str | None) -> str | None:
    """Extract tweet ID from a Twitter/X URL."""
    if not url:
        return None
    import re
    m = re.search(r"/status/(\d+)", url)
    return m.group(1) if m else None


def _enrich_with_media(items: list[dict]) -> list[dict]:
    """Add media URLs to items that have associated media files."""
    for item in items:
        media = []
        platform = item.get("platform", "")

        if platform == "twitter":
            tweet_id = _extract_tweet_id(item.get("url"))
            if not tweet_id:
                try:
                    raw = json.loads(item.get("raw_json", "{}"))
                    tweet_id = raw.get("tweetId") or raw.get("id_str") or raw.get("id")
                except (json.JSONDecodeError, TypeError):
                    pass
            if tweet_id:
                files = find_media(f"{tweet_id}-")
                for f in sorted(files):
                    ext = f.suffix.lower()
                    if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
                        media.append({"url": f"/media/{f.name}", "type": "image"})
                    elif ext in (".mp4", ".webm", ".mov"):
                        media.append({"url": f"/media/{f.name}", "type": "video"})

        elif platform == "reddit":
            # Reddit media files: reddit_{post_id}_{index}.ext
            try:
                raw = json.loads(item.get("raw_json", "{}"))
                post_id = raw.get("id", "")
            except (json.JSONDecodeError, TypeError):
                post_id = ""
            if post_id:
                files = find_media(f"reddit_{post_id}_")
                for f in sorted(files):
                    ext = f.suffix.lower()
                    if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
                        media.append({"url": f"/media/{f.name}", "type": "image"})
                    elif ext in (".mp4", ".webm", ".mov"):
                        media.append({"url": f"/media/{f.name}", "type": "video"})

        elif platform == "instagram":
            # Instagram media files: ig_{item_id}_{index}.ext
            item_id = item.get("id", "")
            if item_id:
                files = find_media(f"ig_{item_id}_")
                for f in sorted(files):
                    ext = f.suffix.lower()
                    if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
                        media.append({"url": f"/media/{f.name}", "type": "image"})
                    elif ext in (".mp4", ".webm", ".mov"):
                        media.append({"url": f"/media/{f.name}", "type": "video"})

        elif platform == "facebook":
            item_id = item.get("id", "")
            if item_id:
                files = find_media(f"fb_{item_id}_")
                for f in sorted(files):
                    ext = f.suffix.lower()
                    if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
                        media.append({"url": f"/media/{f.name}", "type": "image"})

        elif platform == "linkedin":
            item_id = item.get("id", "")
            if item_id:
                files = find_media(f"li_{item_id}_")
                for f in sorted(files):
                    ext = f.suffix.lower()
                    if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
                        media.append({"url": f"/media/{f.name}", "type": "image"})

        item["media"] = media
    return items


# ── Upload & Import ──────────────────────────────────────────────────────────

@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    platform: str = Form(...),
):
    if platform not in PARSERS:
        raise HTTPException(400, f"Unsupported platform: {platform}. Supported: {list(PARSERS.keys())}")

    logger.info(f"[upload] Receiving file '{file.filename}' for platform '{platform}'")
    content = await file.read()
    logger.info(f"[upload] File size: {len(content)} bytes")

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    try:
        items = PARSERS[platform](text)
    except Exception as e:
        logger.error(f"[upload] Parse error: {e}")
        raise HTTPException(422, f"Failed to parse file: {e}")

    if not items:
        raise HTTPException(422, "No items found in file")

    logger.info(f"[upload] Parsed {len(items)} items from {platform}")

    conn = get_db()
    inserted_ids = []
    skipped = 0

    # Build set of existing raw_json hashes for fast dedup (batch check)
    platform_name = items[0]["platform"] if items else platform
    existing_hashes = set()
    rows = conn.execute(
        "SELECT raw_json FROM items WHERE platform = ?", (platform_name,)
    ).fetchall()
    for r in rows:
        if r[0]:
            existing_hashes.add(r[0])
    logger.info(f"[upload] Loaded {len(existing_hashes)} existing items for dedup")

    for item in items:
        raw = item.get("raw_json", "")
        if raw in existing_hashes:
            skipped += 1
            continue

        cursor = conn.execute(
            """INSERT INTO items (platform, type, title, content, url, author, created_at, raw_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (item["platform"], item["type"], item.get("title"), item.get("content"),
             item.get("url"), item.get("author"), item.get("created_at"), item.get("raw_json")),
        )
        inserted_ids.append(cursor.lastrowid)
        existing_hashes.add(raw)

    conn.commit()
    if skipped:
        logger.info(f"[upload] Skipped {skipped} duplicates")
    logger.info(f"[upload] Inserted {len(inserted_ids)} new items into DB")

    # Fetch inserted items for vector indexing
    db_items = []
    for id_ in inserted_ids:
        row = conn.execute("SELECT * FROM items WHERE id = ?", (id_,)).fetchone()
        if row:
            db_items.append(dict(row))
    conn.close()

    # Index in background thread — don't block the HTTP response
    thread = threading.Thread(target=_background_index, args=(db_items, platform), daemon=True)
    thread.start()
    logger.info(f"[upload] Background indexing started for {len(db_items)} items")

    return {"imported": len(inserted_ids), "platform": platform, "indexing": True}


# ── Indexing status ───────────────────────────────────────────────────────────

@app.get("/api/indexing-status")
def indexing_status():
    with _indexing_lock:
        return dict(_indexing_state)


@app.post("/api/reindex")
def reindex_all():
    """Re-index all items into the vector store (e.g. after switching to Ollama embeddings)."""
    with _indexing_lock:
        if _indexing_state["running"]:
            return {"status": "already_running"}

    conn = get_db()
    rows = conn.execute("SELECT * FROM items").fetchall()
    db_items = [dict(r) for r in rows]
    conn.close()

    if not db_items:
        return {"status": "no_items"}

    thread = threading.Thread(target=_background_index, args=(db_items, "all"), daemon=True)
    thread.start()
    return {"status": "started", "total": len(db_items)}


# ── Enrichment ────────────────────────────────────────────────────────────────

_enriching_states = {
    "reddit": {"running": False, "total": 0, "done": 0, "error": None},
    "twitter": {"running": False, "total": 0, "done": 0, "error": None},
    "instagram": {"running": False, "total": 0, "done": 0, "error": None},
    "facebook": {"running": False, "total": 0, "done": 0, "error": None},
    "linkedin": {"running": False, "total": 0, "done": 0, "error": None},
}
_enriching_lock = threading.Lock()


def _background_enrich_platform(platform: str):
    """Enrich items for a single platform in background."""
    state = _enriching_states[platform]
    with _enriching_lock:
        state.update(running=True, total=0, done=0, error=None)

    def update_fn(item_id, title, content, author, created_at=None):
        c = get_db()
        if created_at:
            c.execute(
                "UPDATE items SET title = ?, content = ?, author = ?, created_at = ? WHERE id = ?",
                (title, content, author, created_at, item_id),
            )
        else:
            c.execute(
                "UPDATE items SET title = ?, content = ?, author = ? WHERE id = ?",
                (title, content, author, item_id),
            )
        c.commit()
        c.close()
        with _enriching_lock:
            state["done"] += 1

    def progress_fn(done, total):
        with _enriching_lock:
            state["done"] = done
            state["total"] = total

    try:
        if platform == "reddit":
            conn = get_db()
            rows = conn.execute(
                "SELECT * FROM items WHERE platform = 'reddit' AND (content = '' OR content IS NULL)"
            ).fetchall()
            items = [dict(r) for r in rows]
            conn.close()
            if items:
                with _enriching_lock:
                    state["total"] = len(items)
                enrich_reddit_items(items, update_fn, progress_fn)

        elif platform == "twitter" and X_BEARER_TOKEN:
            conn = get_db()
            rows = conn.execute(
                "SELECT * FROM items WHERE platform = 'twitter' AND (content = '' OR content IS NULL OR content = title)"
            ).fetchall()
            items = [dict(r) for r in rows]
            conn.close()
            if items:
                with _enriching_lock:
                    state["total"] = len(items)
                enrich_twitter_items(items, update_fn, progress_fn)

        elif platform == "instagram" and APIFY_API_KEY:
            conn = get_db()
            # Instagram items often only have the profile name as content, not the actual caption
            rows = conn.execute(
                "SELECT * FROM items WHERE platform = 'instagram' AND (content = '' OR content IS NULL OR length(content) < 50)"
            ).fetchall()
            items = [dict(r) for r in rows]
            conn.close()
            if items:
                with _enriching_lock:
                    state["total"] = len(items)
                enrich_instagram_items(items, update_fn, progress_fn)

        elif platform == "facebook" and APIFY_API_KEY:
            conn = get_db()
            rows = conn.execute(
                "SELECT * FROM items WHERE platform = 'facebook' AND url != '' AND url IS NOT NULL AND url LIKE '%facebook.com%' AND (content = '' OR content IS NULL OR length(content) < 30)"
            ).fetchall()
            items = [dict(r) for r in rows]
            conn.close()
            if items:
                with _enriching_lock:
                    state["total"] = len(items)
                enrich_facebook_items(items, update_fn, progress_fn)

        elif platform == "linkedin" and APIFY_API_KEY:
            conn = get_db()
            rows = conn.execute(
                "SELECT * FROM items WHERE platform = 'linkedin' AND url != '' AND url IS NOT NULL AND url LIKE '%linkedin.com%' AND (content = '' OR content IS NULL OR content = url)"
            ).fetchall()
            items = [dict(r) for r in rows]
            conn.close()
            if items:
                with _enriching_lock:
                    state["total"] = len(items)
                enrich_linkedin_items(items, update_fn, progress_fn)

        logger.info(f"[enrich] {platform} done")

    except Exception as e:
        logger.error(f"[enrich] {platform} error: {e}")
        with _enriching_lock:
            state["error"] = str(e)
    finally:
        with _enriching_lock:
            state["running"] = False


@app.post("/api/reparse-instagram")
def reparse_instagram():
    """Re-extract URL/author from Instagram items using updated parser logic."""
    from .parsers.instagram import _extract_from_label_values
    conn = get_db()
    rows = conn.execute(
        "SELECT id, raw_json FROM items WHERE platform = 'instagram'"
    ).fetchall()

    updated = 0
    for row in rows:
        try:
            entry = json.loads(row[1])
            if "label_values" in entry:
                info = _extract_from_label_values(entry)
                title = ""
                if info["profile"]:
                    title = f"{info['author']} (@{info['profile']})" if info["author"] else f"@{info['profile']}"
                elif info["author"]:
                    title = info["author"]

                conn.execute(
                    "UPDATE items SET title = ?, content = ?, url = ?, author = ? WHERE id = ?",
                    (title[:120] if title else None, title, info["url"], info["profile"] or info["author"], row[0]),
                )
                updated += 1
        except Exception:
            pass

    conn.commit()
    conn.close()
    logger.info(f"[reparse] Instagram: {updated} items updated")
    return {"updated": updated}


@app.post("/api/enrich")
def run_enrich(platform: str = Query("all")):
    """Enrich items. platform can be: all, reddit, twitter, instagram."""
    platforms = ["reddit", "twitter", "instagram"] if platform == "all" else [platform]
    started = []

    for p in platforms:
        if p not in _enriching_states:
            continue
        with _enriching_lock:
            if _enriching_states[p]["running"]:
                continue
        thread = threading.Thread(target=_background_enrich_platform, args=(p,), daemon=True)
        thread.start()
        started.append(p)

    return {"status": "started", "platforms": started, "apify_configured": bool(APIFY_API_KEY)}


@app.get("/api/enrich-status")
def enrich_status():
    with _enriching_lock:
        return {p: dict(s) for p, s in _enriching_states.items()}


# ── Categorization ────────────────────────────────────────────────────────────

@app.post("/api/categorize")
def run_categorization():
    with _categorizing_lock:
        if _categorizing_state["running"]:
            return {"status": "already_running"}
    thread = threading.Thread(target=_background_categorize, daemon=True)
    thread.start()
    return {"status": "started"}


@app.get("/api/import-history")
def import_history():
    """Get a summary of what has been imported, grouped by platform+type, with dates."""
    conn = get_db()
    rows = conn.execute("""
        SELECT platform, type, COUNT(*) as count,
               MIN(imported_at) as first_import,
               MAX(imported_at) as last_import
        FROM items
        GROUP BY platform, type
        ORDER BY platform, type
    """).fetchall()
    conn.close()

    return {
        "imports": [
            {
                "platform": r[0],
                "type": r[1],
                "count": r[2],
                "first_import": r[3],
                "last_import": r[4],
            }
            for r in rows
        ]
    }


@app.get("/api/categorize-status")
def categorize_status():
    with _categorizing_lock:
        return dict(_categorizing_state)


@app.get("/api/topics")
def get_topics():
    """Get all topics with counts, sorted by frequency."""
    conn = get_db()
    rows = conn.execute("SELECT categories FROM items WHERE categories != '[]'").fetchall()
    conn.close()

    topic_counts: dict[str, int] = {}
    for row in rows:
        try:
            cats = json.loads(row[0])
            for cat in cats:
                topic_counts[cat] = topic_counts.get(cat, 0) + 1
        except (json.JSONDecodeError, TypeError):
            pass

    topics = sorted(
        [{"label": label, "count": count} for label, count in topic_counts.items()],
        key=lambda t: t["count"],
        reverse=True,
    )
    return {"topics": topics}


@app.get("/api/topic-graph")
def get_topic_graph(min_count: int = Query(20), min_link: int = Query(5)):
    """Get topic graph data: nodes (categories) and links (co-occurrences).

    Returns nodes with size based on count, and links between co-occurring categories.
    Only includes categories with at least min_count items and links with at least min_link co-occurrences.
    """
    from collections import Counter

    conn = get_db()
    rows = conn.execute("SELECT categories FROM items WHERE categories != '[]'").fetchall()
    conn.close()

    cat_counts = Counter()
    co_occur = Counter()

    for row in rows:
        try:
            cats = json.loads(row[0])
            for c in cats:
                cat_counts[c] += 1
            for i, c1 in enumerate(cats):
                for c2 in cats[i + 1:]:
                    pair = tuple(sorted([c1, c2]))
                    co_occur[pair] += 1
        except (json.JSONDecodeError, TypeError):
            pass

    # Filter by min_count
    valid_cats = {c for c, n in cat_counts.items() if n >= min_count}

    nodes = [
        {"id": cat, "count": count, "size": max(8, min(60, count // 10))}
        for cat, count in cat_counts.items()
        if cat in valid_cats
    ]

    links = [
        {"source": pair[0], "target": pair[1], "weight": count}
        for pair, count in co_occur.items()
        if pair[0] in valid_cats and pair[1] in valid_cats and count >= min_link
    ]

    return {"nodes": nodes, "links": links}


@app.get("/api/collections")
def get_collections(limit: int = Query(16)):
    """Get auto-generated thematic collections (like Google Photos Memories).

    Fast version: uses pre-built media index instead of scanning disk per item.
    """
    import re as _re
    from collections import defaultdict

    conn = get_db()

    # 1. Get category counts (fast SQL)
    rows = conn.execute("SELECT categories FROM items WHERE categories != '[]'").fetchall()
    cat_counts: dict[str, int] = {}
    for row in rows:
        try:
            for cat in json.loads(row[0]):
                cat_counts[cat] = cat_counts.get(cat, 0) + 1
        except (json.JSONDecodeError, TypeError):
            pass

    top_cats = sorted(cat_counts.keys(), key=lambda c: cat_counts[c], reverse=True)[:limit]

    # 2. Build media index ONCE (scan disk once, not per item)
    media_files = set(f.name for f in map(Path, media_names()) if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"))

    # 3. For each top category, find ONE cover image efficiently
    collections = []
    for cat in top_cats:
        # Get a few items from this category with URLs
        sample_rows = conn.execute(
            """SELECT id, platform, title, url, raw_json FROM items
               WHERE categories LIKE ? AND url != '' AND url IS NOT NULL
               LIMIT 30""",
            (f'%"{cat}"%',),
        ).fetchall()

        # Get platforms
        platform_rows = conn.execute(
            """SELECT DISTINCT platform FROM items WHERE categories LIKE ? LIMIT 6""",
            (f'%"{cat}"%',),
        ).fetchall()
        platforms = [r[0] for r in platform_rows]

        # Find cover: check if any sample item has a media file
        cover = None
        for sr in sample_rows:
            item_id, platform, title, url, raw_json = sr
            if platform == "twitter":
                m = _re.search(r"/status/(\d+)", url or "")
                if m:
                    prefix = m.group(1) + "-"
                    match = next((f for f in media_files if f.startswith(prefix)), None)
                    if match:
                        cover = f"/media/{match}"
                        break
            elif platform == "instagram":
                prefix = f"ig_{item_id}_"
                match = next((f for f in media_files if f.startswith(prefix)), None)
                if match:
                    cover = f"/media/{match}"
                    break
            elif platform == "facebook":
                prefix = f"fb_{item_id}_"
                match = next((f for f in media_files if f.startswith(prefix)), None)
                if match:
                    cover = f"/media/{match}"
                    break
            elif platform == "linkedin":
                prefix = f"li_{item_id}_"
                match = next((f for f in media_files if f.startswith(prefix)), None)
                if match:
                    cover = f"/media/{match}"
                    break
            elif platform == "reddit":
                try:
                    raw = json.loads(raw_json or "{}")
                    post_id = raw.get("id", "")
                    if post_id:
                        prefix = f"reddit_{post_id}_"
                        match = next((f for f in media_files if f.startswith(prefix)), None)
                        if match:
                            cover = f"/media/{match}"
                            break
                except:
                    pass

        collections.append({
            "category": cat,
            "count": cat_counts[cat],
            "platforms": platforms,
            "cover": cover,
        })

    conn.close()
    return {"collections": collections}


# ── Items listing ─────────────────────────────────────────────────────────────

@app.get("/api/items")
def list_items(
    platform: str | None = Query(None),
    type: str | None = Query(None),
    category: str | None = Query(None),
    month: str | None = Query(None),  # format: YYYY-MM
    sort: str = Query("date_desc"),  # date_desc, date_asc, imported_desc
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
):
    conn = get_db()
    conditions = []
    params = []

    if platform:
        conditions.append("platform = ?")
        params.append(platform)
    if type:
        conditions.append("type = ?")
        params.append(type)
    if category:
        conditions.append("categories LIKE ?")
        params.append(f'%"{category}"%')
    if month:
        month_list = [m.strip() for m in month.split(',') if m.strip()]
        if len(month_list) == 1:
            conditions.append("strftime('%Y-%m', COALESCE(created_at, imported_at)) = ?")
            params.append(month_list[0])
        elif month_list:
            placeholders = ','.join('?' * len(month_list))
            conditions.append(f"strftime('%Y-%m', COALESCE(created_at, imported_at)) IN ({placeholders})")
            params.extend(month_list)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    offset = (page - 1) * per_page

    # Sort order
    sort_map = {
        # Items with an unknown date go last in both directions
        "date_desc": "created_at IS NULL, COALESCE(created_at, imported_at) DESC",
        "date_asc": "created_at IS NULL, COALESCE(created_at, imported_at) ASC",
        "imported_desc": "imported_at DESC",
    }
    order_by = sort_map.get(sort, sort_map["date_desc"])

    total = conn.execute(f"SELECT COUNT(*) FROM items {where}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT * FROM items {where} ORDER BY {order_by} LIMIT ? OFFSET ?",
        params + [per_page, offset],
    ).fetchall()

    # Get available months for the current filter (without month filter)
    month_conditions = [c for c in conditions if "strftime" not in c]
    month_params = [p for i, p in enumerate(params) if "strftime" not in (conditions[i] if i < len(conditions) else "")]
    # Simpler approach: get months from all items matching platform/category
    month_where_parts = []
    month_where_params = []
    if platform:
        month_where_parts.append("platform = ?")
        month_where_params.append(platform)
    if category:
        month_where_parts.append("categories LIKE ?")
        month_where_params.append(f'%"{category}"%')
    month_where = f"WHERE {' AND '.join(month_where_parts)}" if month_where_parts else ""

    months = conn.execute(
        f"""SELECT strftime('%Y-%m', COALESCE(created_at, imported_at)) as m, COUNT(*) as c
            FROM items {month_where}
            GROUP BY m HAVING m IS NOT NULL
            ORDER BY m DESC""",
        month_where_params,
    ).fetchall()

    conn.close()

    items_list = _enrich_with_media([dict(r) for r in rows])
    return {
        "items": items_list,
        "total": total,
        "page": page,
        "per_page": per_page,
        "months": [{"month": r[0], "count": r[1]} for r in months],
    }


# ── Text Search (FTS5) ───────────────────────────────────────────────────────

@app.get("/api/search")
def search_items(
    q: str = Query(..., min_length=1),
    platform: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
):
    conn = get_db()
    offset = (page - 1) * per_page

    # FTS5 search
    fts_query = q.replace('"', '""')

    if platform:
        rows = conn.execute(
            """SELECT items.* FROM items_fts
               JOIN items ON items.id = items_fts.rowid
               WHERE items_fts MATCH ? AND items.platform = ?
               ORDER BY rank
               LIMIT ? OFFSET ?""",
            (fts_query, platform, per_page, offset),
        ).fetchall()
        total = conn.execute(
            """SELECT COUNT(*) FROM items_fts
               JOIN items ON items.id = items_fts.rowid
               WHERE items_fts MATCH ? AND items.platform = ?""",
            (fts_query, platform),
        ).fetchone()[0]
    else:
        rows = conn.execute(
            """SELECT items.* FROM items_fts
               JOIN items ON items.id = items_fts.rowid
               WHERE items_fts MATCH ?
               ORDER BY rank
               LIMIT ? OFFSET ?""",
            (fts_query, per_page, offset),
        ).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) FROM items_fts WHERE items_fts MATCH ?",
            (fts_query,),
        ).fetchone()[0]

    conn.close()
    items_list = _enrich_with_media([dict(r) for r in rows])
    return {
        "items": items_list,
        "total": total,
        "page": page,
        "query": q,
    }


# ── Semantic Search (RAG) ────────────────────────────────────────────────────

@app.get("/api/semantic-search")
def semantic_search_items(
    q: str = Query(..., min_length=1),
    platform: str | None = Query(None),
    n: int = Query(20, ge=1, le=100),
):
    try:
        results = semantic_search(q, n_results=n, platform=platform)
    except Exception as e:
        raise HTTPException(500, f"Semantic search failed: {e}")

    if not results:
        return {"items": [], "query": q}

    conn = get_db()
    items = []
    for r in results:
        row = conn.execute("SELECT * FROM items WHERE id = ?", (r["id"],)).fetchone()
        if row:
            item = dict(row)
            item["relevance_score"] = 1 - r["distance"]
            items.append(item)
    conn.close()

    return {"items": _enrich_with_media(items), "query": q}


# ── Ollama / RAG Chat ────────────────────────────────────────────────────────

@app.get("/api/ollama/status")
def ollama_status():
    """Check Ollama availability and which models are installed."""
    available = ollama_client.is_ollama_available()
    if not available:
        return {
            "available": False,
            "models": [],
            "embed_model": ollama_client.EMBED_MODEL,
            "chat_model": ollama_client.CHAT_MODEL,
            "has_embed": False,
            "has_chat": False,
        }

    models = ollama_client.list_models()
    return {
        "available": True,
        "models": models,
        "embed_model": ollama_client.EMBED_MODEL,
        "chat_model": ollama_client.CHAT_MODEL,
        "has_embed": ollama_client.has_model(ollama_client.EMBED_MODEL),
        "has_chat": ollama_client.has_model(ollama_client.CHAT_MODEL),
    }


@app.post("/api/chat")
def rag_chat(body: dict):
    """RAG chat — semantic search + LLM answer."""
    query = body.get("query", "").strip()
    if not query:
        raise HTTPException(400, "query is required")

    if not ollama_client.is_ollama_available():
        raise HTTPException(503, "Ollama is not running. Start it with 'ollama serve'.")
    if not ollama_client.has_model(ollama_client.CHAT_MODEL):
        raise HTTPException(503, f"Chat model not found. Run 'ollama pull {ollama_client.CHAT_MODEL}'.")

    # 1. FTS search FIRST (best for keyword-based queries)
    conn = get_db()
    # Extract individual words for FTS query
    fts_words = [w for w in query.split() if len(w) > 2]
    fts_query = " OR ".join(f'"{w}"' for w in fts_words) if fts_words else query.replace('"', '""')
    fts_rows = []
    try:
        fts_rows = conn.execute(
            """SELECT items.* FROM items_fts
               JOIN items ON items.id = items_fts.rowid
               WHERE items_fts MATCH ?
               ORDER BY rank LIMIT 15""",
            (fts_query,),
        ).fetchall()
    except Exception:
        pass

    # 2. Semantic search as complement
    try:
        results = semantic_search(query, n_results=10)
    except Exception:
        results = []

    # 3. Combine results — FTS FIRST (more precise for keyword queries), then semantic
    seen_ids = set()
    context_items = []

    # FTS results first (more relevant for keyword queries)
    for row in fts_rows:
        item = dict(row)
        if item["id"] not in seen_ids:
            context_items.append(item)
            seen_ids.add(item["id"])

    # Then semantic results
    for r in results:
        if r["id"] not in seen_ids:
            row = conn.execute("SELECT * FROM items WHERE id = ?", (r["id"],)).fetchone()
            if row:
                context_items.append(dict(row))
                seen_ids.add(r["id"])

    # Then FTS results
    for row in fts_rows:
        item = dict(row)
        if item["id"] not in seen_ids:
            context_items.append(item)
            seen_ids.add(item["id"])

    conn.close()

    # 4. Build context string for the LLM
    context_items = context_items[:15]  # Limit context size
    context_parts = []
    for n, item in enumerate(context_items, 1):
        parts = [f"[{n}]"]
        if item.get("platform"):
            parts.append(f"[{item['platform']}]")
        if item.get("type"):
            parts.append(f"({item['type']})")
        if item.get("title"):
            parts.append(item["title"])
        if item.get("content") and item.get("content") != item.get("title"):
            content = item["content"][:500]  # Truncate long content
            parts.append(content)
        if item.get("url"):
            parts.append(f"URL: {item['url']}")
        context_parts.append(" ".join(parts))

    context = "\n\n".join(context_parts)

    if not context:
        return {
            "answer": "Je n'ai trouvé aucun contenu pertinent dans tes données pour répondre à cette question.",
            "sources": [],
            "query": query,
        }

    # 5. Call LLM
    try:
        answer = ollama_client.chat(
            query=query,
            context=context,
            system_prompt=ollama_client.RAG_SYSTEM_PROMPT,
        )
    except Exception as e:
        raise HTTPException(500, f"LLM error: {e}")

    # Return answer + sources, the ones the answer cites as [n] first
    cited = []
    for m in re.finditer(r"\[(\d+)\]", answer):
        n = int(m.group(1))
        if 1 <= n <= len(context_items) and n not in cited:
            cited.append(n)
    order = cited + [n for n in range(1, len(context_items) + 1) if n not in cited]
    sources = _enrich_with_media([
        dict(context_items[n - 1], source_number=n, cited=n in cited) for n in order
    ])

    return {
        "answer": answer,
        "sources": sources,
        "query": query,
    }


# ── Stats / Dashboard ────────────────────────────────────────────────────────

@app.get("/api/stats")
def get_stats():
    conn = get_db()

    total = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    by_platform = conn.execute(
        "SELECT platform, COUNT(*) as count FROM items GROUP BY platform ORDER BY count DESC"
    ).fetchall()
    by_type = conn.execute(
        "SELECT type, COUNT(*) as count FROM items GROUP BY type ORDER BY count DESC"
    ).fetchall()

    # Top categories (from the categories JSON field)
    all_categories = conn.execute("SELECT categories FROM items WHERE categories != '[]'").fetchall()
    cat_counts: dict[str, int] = {}
    for row in all_categories:
        try:
            cats = json.loads(row[0])
            for cat in cats:
                cat_counts[cat] = cat_counts.get(cat, 0) + 1
        except (json.JSONDecodeError, TypeError):
            pass

    top_categories = sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)[:20]

    # Timeline: items per month
    timeline = conn.execute(
        """SELECT strftime('%Y-%m', COALESCE(created_at, imported_at)) as month,
                  COUNT(*) as count
           FROM items
           GROUP BY month
           ORDER BY month"""
    ).fetchall()

    conn.close()

    return {
        "total": total,
        "by_platform": [{"platform": r[0], "count": r[1]} for r in by_platform],
        "by_type": [{"type": r[0], "count": r[1]} for r in by_type],
        "top_categories": [{"category": c, "count": n} for c, n in top_categories],
        "timeline": [{"month": r[0], "count": r[1]} for r in timeline],
    }


@app.delete("/api/items")
def delete_all_items():
    conn = get_db()
    conn.execute("DELETE FROM items")
    conn.commit()
    conn.close()

    # Clear vector store
    try:
        from .vector_store import get_collection
        import chromadb
        client = chromadb.PersistentClient(path=str(__import__('pathlib').Path(__file__).parent.parent / "data" / "chroma"))
        client.delete_collection("items")
        logger.info("[delete] All items and vector store cleared")
    except Exception as e:
        logger.warning(f"[delete] Could not clear vector store: {e}")

    return {"deleted": True}
