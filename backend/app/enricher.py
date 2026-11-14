"""Enrich items by fetching missing data from public APIs and Apify.

Supports:
- Reddit: public .json API (free, no auth, includes media)
- Twitter/X: Apify Tweet Scraper (paid, includes media)
- Instagram: Apify Instagram Scraper (paid, includes media)
"""

import json
import logging
import os
import re
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

from .media import MEDIA_PATH, remember_media

load_dotenv(Path(__file__).parent.parent / ".env")

logger = logging.getLogger("tousmeslikes")

APIFY_API_KEY = os.getenv("APIFY_API_KEY", "")
APIFY_BASE = "https://api.apify.com/v2"
X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN", "")

# Rate limiting
REDDIT_DELAY = 1.5
APIFY_DELAY = 1.0
X_API_DELAY = 1.0  # X API: 300 requests/15min = 1 per 3s, but 1s is usually fine


# ── Helpers ──────────────────────────────────────────────────────────────────

def _download_media(url: str, filename: str) -> str | None:
    """Download a media file to the local media directory. Returns local path or None."""
    dest = MEDIA_PATH / filename
    if dest.exists():
        return str(dest)
    try:
        MEDIA_PATH.mkdir(parents=True, exist_ok=True)
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                dest.write_bytes(resp.content)
                remember_media(filename)
                return str(dest)
    except Exception as e:
        logger.debug(f"[media] Failed to download {url}: {e}")
    return None


def _extract_tweet_id(url: str) -> str | None:
    m = re.search(r"/status/(\d+)", url or "")
    return m.group(1) if m else None


# ── Reddit enrichment ────────────────────────────────────────────────────────

def enrich_reddit_items(items: list[dict], db_update_fn, progress_fn=None) -> int:
    """Fetch title/content/media for Reddit items via public .json API."""
    to_enrich = [
        item for item in items
        if item.get("platform") == "reddit"
        and item.get("url")
        and not item.get("content")
        and "reddit.com" in item.get("url", "")
    ]

    if not to_enrich:
        return 0

    logger.info(f"[enrich] Enriching {len(to_enrich)} Reddit items via public API")
    enriched = 0

    client = httpx.Client(
        timeout=10,
        headers={"User-Agent": "TousMesLikes/1.0 (personal archiving tool)"},
        follow_redirects=True,
    )

    try:
        for i, item in enumerate(to_enrich):
            url = item["url"].rstrip("/")
            json_url = f"{url}.json"

            try:
                resp = client.get(json_url)
                if resp.status_code != 200:
                    logger.debug(f"[enrich] Reddit {resp.status_code} for {url}")
                    if progress_fn:
                        progress_fn(i + 1, len(to_enrich))
                    time.sleep(REDDIT_DELAY)
                    continue

                data = resp.json()
                if not isinstance(data, list) or len(data) == 0:
                    if progress_fn:
                        progress_fn(i + 1, len(to_enrich))
                    time.sleep(REDDIT_DELAY)
                    continue

                post_data = data[0].get("data", {}).get("children", [{}])[0].get("data", {})
                title = post_data.get("title", "")
                selftext = post_data.get("selftext", "")
                author = post_data.get("author", "")
                subreddit = post_data.get("subreddit_name_prefixed", "")

                content = selftext or title
                if subreddit:
                    title_full = f"[{subreddit}] {title}"
                else:
                    title_full = title

                # Extract created date (Reddit uses Unix timestamp)
                created_utc = post_data.get("created_utc")
                created_at = ""
                if created_utc:
                    from datetime import datetime, timezone
                    created_at = datetime.fromtimestamp(created_utc, tz=timezone.utc).isoformat()

                # Extract media
                media_urls = _extract_reddit_media(post_data)
                post_id = post_data.get("id", item["id"])

                for j, media in enumerate(media_urls):
                    ext = _guess_extension(media["url"])
                    filename = f"reddit_{post_id}_{j}{ext}"
                    _download_media(media["url"], filename)

                if title:
                    db_update_fn(item["id"], title_full[:120], content, author, created_at)
                    enriched += 1

                if (i + 1) % 10 == 0:
                    logger.info(f"[enrich] Reddit progress: {i + 1}/{len(to_enrich)} ({enriched} enriched)")

            except Exception as e:
                logger.debug(f"[enrich] Reddit error for {url}: {e}")

            if progress_fn:
                progress_fn(i + 1, len(to_enrich))
            time.sleep(REDDIT_DELAY)

    finally:
        client.close()

    logger.info(f"[enrich] Reddit done: {enriched}/{len(to_enrich)} items enriched")
    return enriched


def _extract_reddit_media(post_data: dict) -> list[dict]:
    """Extract media URLs from Reddit post data."""
    media = []

    # Direct image URL (imgur, i.redd.it, etc.)
    post_url = post_data.get("url", "")
    if re.search(r"\.(jpg|jpeg|png|gif|webp)(\?|$)", post_url, re.I):
        media.append({"url": post_url, "type": "image"})

    # Reddit preview images
    preview = post_data.get("preview", {})
    if preview and "images" in preview:
        for img in preview["images"]:
            source = img.get("source", {})
            if source.get("url"):
                # Reddit HTML-encodes URLs in preview
                clean_url = source["url"].replace("&amp;", "&")
                media.append({"url": clean_url, "type": "image"})
                break  # Just take the source (highest res)

    # Reddit video
    reddit_video = post_data.get("media", {})
    if reddit_video and "reddit_video" in (reddit_video or {}):
        vid = reddit_video["reddit_video"]
        if vid.get("fallback_url"):
            media.append({"url": vid["fallback_url"], "type": "video"})

    # Gallery (multiple images)
    if post_data.get("is_gallery"):
        gallery_data = post_data.get("media_metadata", {})
        for media_id, meta in gallery_data.items():
            if meta.get("status") == "valid" and meta.get("s", {}).get("u"):
                clean_url = meta["s"]["u"].replace("&amp;", "&")
                media.append({"url": clean_url, "type": "image"})

    return media


def _guess_extension(url: str) -> str:
    """Guess file extension from URL."""
    m = re.search(r"\.(jpg|jpeg|png|gif|webp|mp4|webm|mov)(\?|$)", url, re.I)
    if m:
        return f".{m.group(1).lower()}"
    return ".jpg"  # default


# ── Twitter/X enrichment via official X API v2 ───────────────────────────────

X_API_BASE = "https://api.x.com/2"
X_TWEET_FIELDS = "text,created_at,public_metrics"
X_EXPANSIONS = "attachments.media_keys,author_id"
X_MEDIA_FIELDS = "url,preview_image_url,type,variants"
X_USER_FIELDS = "username,name"


def enrich_twitter_items(items: list[dict], db_update_fn, progress_fn=None) -> int:
    """Fetch full tweet data (text + media) via official X API v2.

    Cost: ~$0.005 per tweet read.
    """
    if not X_BEARER_TOKEN:
        logger.warning("[enrich] No X_BEARER_TOKEN set — skipping Twitter enrichment")
        return 0

    to_enrich = [
        item for item in items
        if item.get("platform") == "twitter"
        and item.get("url")
    ]

    if not to_enrich:
        return 0

    logger.info(f"[enrich] Enriching {len(to_enrich)} Twitter items via X API v2 (~${len(to_enrich) * 0.005:.2f} estimated)")
    enriched = 0
    errors = 0

    client = httpx.Client(
        timeout=15,
        headers={"Authorization": f"Bearer {X_BEARER_TOKEN}"},
    )

    try:
        for i, item in enumerate(to_enrich):
            tweet_id = _extract_tweet_id(item.get("url"))
            if not tweet_id:
                continue

            try:
                resp = client.get(
                    f"{X_API_BASE}/tweets/{tweet_id}",
                    params={
                        "tweet.fields": X_TWEET_FIELDS,
                        "expansions": X_EXPANSIONS,
                        "media.fields": X_MEDIA_FIELDS,
                        "user.fields": X_USER_FIELDS,
                    },
                )

                if resp.status_code == 429:
                    # Rate limited — wait, but cap at 60s
                    reset = int(resp.headers.get("x-rate-limit-reset", 0))
                    wait = min(max(reset - int(time.time()), 5), 60)
                    logger.warning(f"[enrich] X API rate limited at item {i}, waiting {wait}s")
                    time.sleep(wait)
                    # Don't skip — retry same item next loop? No, just skip and move on.
                    errors += 1
                    if progress_fn:
                        progress_fn(i + 1, len(to_enrich))
                    continue

                if resp.status_code != 200:
                    logger.debug(f"[enrich] X API {resp.status_code} for tweet {tweet_id}")
                    errors += 1
                    if progress_fn:
                        progress_fn(i + 1, len(to_enrich))
                    time.sleep(X_API_DELAY)
                    continue

                data = resp.json()
                tweet_data = data.get("data", {})
                includes = data.get("includes", {})

                if not tweet_data:
                    if progress_fn:
                        progress_fn(i + 1, len(to_enrich))
                    time.sleep(X_API_DELAY)
                    continue

                full_text = tweet_data.get("text", "")

                # Get author from includes.users
                author = ""
                users = includes.get("users", [])
                if users:
                    author = users[0].get("username", "")

                title = f"@{author}: {full_text[:100]}" if author else full_text[:120]
                created_at = tweet_data.get("created_at", "")  # ISO 8601

                # Download media from includes.media
                media_list = includes.get("media", [])
                for j, m in enumerate(media_list):
                    media_type = m.get("type", "photo")

                    if media_type == "photo" and m.get("url"):
                        ext = _guess_extension(m["url"])
                        filename = f"{tweet_id}-xapi_{j}{ext}"
                        _download_media(m["url"], filename)

                    elif media_type == "video" and m.get("variants"):
                        # Pick highest bitrate mp4
                        mp4s = [v for v in m["variants"] if v.get("content_type") == "video/mp4"]
                        if mp4s:
                            best = max(mp4s, key=lambda v: v.get("bit_rate", 0))
                            if best.get("url"):
                                filename = f"{tweet_id}-xapi_{j}.mp4"
                                _download_media(best["url"], filename)

                db_update_fn(item["id"], title, full_text, author, created_at)
                enriched += 1

            except Exception as e:
                logger.debug(f"[enrich] X API error for tweet {tweet_id}: {e}")
                errors += 1

            if progress_fn:
                progress_fn(i + 1, len(to_enrich))

            if (i + 1) % 100 == 0:
                logger.info(f"[enrich] Twitter progress: {i + 1}/{len(to_enrich)} ({enriched} enriched, {errors} errors)")

            time.sleep(X_API_DELAY)

    finally:
        client.close()

    if progress_fn:
        progress_fn(len(to_enrich), len(to_enrich))

    logger.info(f"[enrich] Twitter done: {enriched}/{len(to_enrich)} items enriched ({errors} errors)")
    return enriched


# ── Instagram enrichment via Apify ───────────────────────────────────────────

def enrich_instagram_items(items: list[dict], db_update_fn, progress_fn=None) -> int:
    """Fetch full Instagram post data (text + media) via Apify Instagram Scraper.

    Args:
        items: list of item dicts
        db_update_fn: callable(item_id, title, content, author, url) to update DB
        progress_fn: optional callable(done, total) for progress tracking

    Returns:
        Number of items enriched
    """
    if not APIFY_API_KEY:
        logger.warning("[enrich] No APIFY_API_KEY set — skipping Instagram enrichment")
        return 0

    # Extract Instagram URLs from items (may be in raw_json label_values)
    to_enrich = []
    for item in items:
        if item.get("platform") != "instagram":
            continue
        url = item.get("url") or ""
        if not url:
            # Try extracting from raw_json
            try:
                raw = json.loads(item.get("raw_json", "{}"))
                for lv in raw.get("label_values", []):
                    if lv.get("label") == "URL" and "instagram.com" in lv.get("value", ""):
                        url = lv["value"]
                        break
            except (json.JSONDecodeError, TypeError):
                pass
        if url and "instagram.com" in url:
            to_enrich.append({**item, "_ig_url": url})

    if not to_enrich:
        return 0

    logger.info(f"[enrich] Enriching {len(to_enrich)} Instagram items via Apify")
    enriched = 0

    # Process in small batches of 5 to avoid Apify 300s timeout
    batch_size = 5
    for batch_start in range(0, len(to_enrich), batch_size):
        batch = to_enrich[batch_start:batch_start + batch_size]
        urls = [item["_ig_url"] for item in batch]

        try:
            results = _apify_fetch_instagram(urls)
            if not results:
                continue

            # Map results by URL (shortCode or url match)
            results_by_url = {}
            for r in results:
                r_url = r.get("url", "")
                r_shortcode = r.get("shortCode", "")
                results_by_url[r_url] = r
                if r_shortcode:
                    results_by_url[r_shortcode] = r

            for item in batch:
                ig_url = item["_ig_url"]
                # Try to match by URL or shortcode
                result = results_by_url.get(ig_url)
                if not result:
                    # Try matching by shortcode extracted from URL
                    sc_match = re.search(r"/(p|reel)/([A-Za-z0-9_-]+)", ig_url)
                    if sc_match:
                        result = results_by_url.get(sc_match.group(2))

                if not result:
                    continue

                caption = result.get("caption", "") or ""
                owner = result.get("ownerUsername", "")
                owner_name = result.get("ownerFullName", "")

                title = f"@{owner}: {caption[:100]}" if owner else caption[:120]
                content = caption

                # Download media
                _download_instagram_media(result, item["id"])

                db_update_fn(item["id"], title, content, owner)
                enriched += 1

        except Exception as e:
            logger.error(f"[enrich] Instagram Apify batch error: {e}")

        if progress_fn:
            progress_fn(min(batch_start + batch_size, len(to_enrich)), len(to_enrich))

        time.sleep(APIFY_DELAY)

    logger.info(f"[enrich] Instagram done: {enriched}/{len(to_enrich)} items enriched")
    return enriched


def _apify_fetch_instagram(urls: list[str]) -> list[dict]:
    """Call Apify Instagram Scraper to fetch post data."""
    endpoint = f"{APIFY_BASE}/acts/apify~instagram-scraper/run-sync-get-dataset-items"

    with httpx.Client(timeout=300) as client:
        resp = client.post(
            endpoint,
            params={"token": APIFY_API_KEY},
            json={
                "directUrls": urls,
                "resultsType": "posts",
                "resultsLimit": len(urls),
            },
            headers={"Content-Type": "application/json"},
        )

        if resp.status_code in (200, 201):
            return resp.json()
        else:
            logger.error(f"[apify] Instagram scraper error {resp.status_code}: {resp.text[:200]}")
            return []


def _download_instagram_media(post: dict, item_id: int):
    """Download media from an Instagram post result."""
    post_type = post.get("type", "")

    # Main image/video
    if post.get("displayUrl"):
        ext = _guess_extension(post["displayUrl"])
        filename = f"ig_{item_id}_0{ext}"
        _download_media(post["displayUrl"], filename)

    if post.get("videoUrl"):
        filename = f"ig_{item_id}_0.mp4"
        _download_media(post["videoUrl"], filename)

    # Carousel / Sidecar
    children = post.get("childPosts") or post.get("sidecarPosts") or []
    for i, child in enumerate(children):
        if child.get("displayUrl"):
            ext = _guess_extension(child["displayUrl"])
            filename = f"ig_{item_id}_{i + 1}{ext}"
            _download_media(child["displayUrl"], filename)
        if child.get("videoUrl"):
            filename = f"ig_{item_id}_{i + 1}.mp4"
            _download_media(child["videoUrl"], filename)


# ── Facebook enrichment via Apify ────────────────────────────────────────────

def enrich_facebook_items(items: list[dict], db_update_fn, progress_fn=None) -> int:
    """Fetch full Facebook post data (text + images) via Apify facebook-posts-scraper."""
    if not APIFY_API_KEY:
        logger.warning("[enrich] No APIFY_API_KEY set — skipping Facebook enrichment")
        return 0

    to_enrich = [
        item for item in items
        if item.get("platform") == "facebook"
        and item.get("url")
        and "facebook.com" in item.get("url", "")
    ]

    if not to_enrich:
        return 0

    logger.info(f"[enrich] Enriching {len(to_enrich)} Facebook items via Apify (~${len(to_enrich) * 0.001:.2f} estimated)")
    enriched = 0

    batch_size = 5
    for batch_start in range(0, len(to_enrich), batch_size):
        batch = to_enrich[batch_start:batch_start + batch_size]
        urls = [{"url": item["url"]} for item in batch]

        try:
            endpoint = f"{APIFY_BASE}/acts/apify~facebook-posts-scraper/run-sync-get-dataset-items"
            with httpx.Client(timeout=300) as client:
                resp = client.post(
                    endpoint,
                    params={"token": APIFY_API_KEY},
                    json={"startUrls": urls, "resultsLimit": len(batch)},
                    headers={"Content-Type": "application/json"},
                )

            if resp.status_code not in (200, 201):
                logger.error(f"[apify] Facebook scraper error {resp.status_code}: {resp.text[:200]}")
                if progress_fn:
                    progress_fn(min(batch_start + batch_size, len(to_enrich)), len(to_enrich))
                time.sleep(APIFY_DELAY)
                continue

            results = resp.json()
            if not results:
                if progress_fn:
                    progress_fn(min(batch_start + batch_size, len(to_enrich)), len(to_enrich))
                time.sleep(APIFY_DELAY)
                continue

            # Map results by facebookUrl
            results_by_url = {}
            for r in results:
                fb_url = r.get("facebookUrl", "") or r.get("url", "")
                if fb_url:
                    results_by_url[fb_url] = r
                post_id = r.get("postId", "")
                if post_id:
                    results_by_url[post_id] = r

            for item in batch:
                result = results_by_url.get(item["url"])
                # Try matching by post ID from URL
                if not result:
                    for r in results:
                        result = r
                        break  # Take first result for single-post batches

                if not result:
                    continue

                text = result.get("text", "")
                user = result.get("user", {})
                author = user.get("name", "") if isinstance(user, dict) else ""

                title = f"{author}: {text[:100]}" if author else text[:120]
                content = text

                # Download images (not videos)
                for j, m in enumerate(result.get("media", [])):
                    img_url = None
                    if isinstance(m, dict):
                        typename = m.get("__typename", "")
                        if typename == "Photo" or "photo" in str(m.get("url", "")).lower():
                            img_url = m.get("thumbnail") or (m.get("photo_image", {}) or {}).get("uri")
                    if img_url:
                        ext = _guess_extension(img_url)
                        filename = f"fb_{item['id']}_{j}{ext}"
                        _download_media(img_url, filename)

                if text:
                    db_update_fn(item["id"], title[:120], content, author)
                    enriched += 1

        except Exception as e:
            logger.error(f"[enrich] Facebook Apify batch error: {e}")

        if progress_fn:
            progress_fn(min(batch_start + batch_size, len(to_enrich)), len(to_enrich))

        if (batch_start // batch_size + 1) % 10 == 0:
            logger.info(f"[enrich] Facebook progress: {min(batch_start + batch_size, len(to_enrich))}/{len(to_enrich)} ({enriched} enriched)")

        time.sleep(APIFY_DELAY)

    logger.info(f"[enrich] Facebook done: {enriched}/{len(to_enrich)} items enriched")
    return enriched


# ── LinkedIn enrichment via Apify ────────────────────────────────────────────

def enrich_linkedin_items(items: list[dict], db_update_fn, progress_fn=None) -> int:
    """Fetch full LinkedIn post data (text + images) via Apify supreme_coder/linkedin-post."""
    if not APIFY_API_KEY:
        logger.warning("[enrich] No APIFY_API_KEY set — skipping LinkedIn enrichment")
        return 0

    to_enrich = [
        item for item in items
        if item.get("platform") == "linkedin"
        and item.get("url")
        and "linkedin.com" in item.get("url", "")
    ]

    if not to_enrich:
        return 0

    logger.info(f"[enrich] Enriching {len(to_enrich)} LinkedIn items via Apify (~${len(to_enrich) * 0.001:.2f} estimated)")
    enriched = 0

    # Batch in groups of 10 (LinkedIn scraper handles multiple URLs well)
    batch_size = 10
    for batch_start in range(0, len(to_enrich), batch_size):
        batch = to_enrich[batch_start:batch_start + batch_size]
        # URL-decode the LinkedIn URLs
        urls = [item["url"].replace("%3A", ":") for item in batch]

        try:
            endpoint = f"{APIFY_BASE}/acts/supreme_coder~linkedin-post/run-sync-get-dataset-items"
            with httpx.Client(timeout=300) as client:
                resp = client.post(
                    endpoint,
                    params={"token": APIFY_API_KEY},
                    json={"urls": urls},
                    headers={"Content-Type": "application/json"},
                )

            if resp.status_code not in (200, 201):
                logger.error(f"[apify] LinkedIn scraper error {resp.status_code}: {resp.text[:200]}")
                if progress_fn:
                    progress_fn(min(batch_start + batch_size, len(to_enrich)), len(to_enrich))
                time.sleep(APIFY_DELAY)
                continue

            results = resp.json()
            if not results:
                if progress_fn:
                    progress_fn(min(batch_start + batch_size, len(to_enrich)), len(to_enrich))
                time.sleep(APIFY_DELAY)
                continue

            # Map results by URN or inputUrl
            results_by_key = {}
            for r in results:
                urn = r.get("shareUrn", "") or r.get("urn", "")
                input_url = r.get("inputUrl", "")
                if urn:
                    results_by_key[urn] = r
                if input_url:
                    results_by_key[input_url] = r

            for item in batch:
                item_url = item["url"].replace("%3A", ":")
                result = results_by_key.get(item_url)

                # Try matching by URN extracted from URL
                if not result:
                    urn_match = re.search(r"urn:li:(?:ugcPost|activity):(\d+)", item_url)
                    if urn_match:
                        for key, r in results_by_key.items():
                            if urn_match.group(1) in key:
                                result = r
                                break

                if not result:
                    continue

                text = result.get("text", "")
                images = result.get("images", [])
                author = ""

                # Handle reshared posts (reposts) — content is in resharedPost
                reshared = result.get("resharedPost")
                if not text and reshared:
                    text = reshared.get("text", "")
                    images = reshared.get("images", []) or images
                    # Also grab article title if present
                    article = reshared.get("article", {})
                    if article.get("title") and not text:
                        text = article["title"]
                    elif article.get("title"):
                        text = f"{text}\n\n[Article: {article['title']}]"
                    # Mark as repost
                    reshared_attrs = reshared.get("attributes", [])
                    for attr in reshared_attrs:
                        if attr.get("type") == "PROFILE_MENTION":
                            profile = attr.get("profile", {})
                            author = f"{profile.get('firstName', '')} {profile.get('lastName', '')}".strip()
                            break

                if not text:
                    continue

                # Author from main post attributes if not from reshare
                if not author:
                    attrs = result.get("attributes", [])
                    for attr in attrs:
                        if attr.get("type") == "PROFILE_MENTION":
                            profile = attr.get("profile", {})
                            author = f"{profile.get('firstName', '')} {profile.get('lastName', '')}".strip()
                            break

                title_prefix = "[Repost] " if reshared and not result.get("text") else ""
                title = f"{title_prefix}{text[:110]}"
                content = text

                # Download images (not videos)
                for j, img_url in enumerate(images):
                    if isinstance(img_url, str) and img_url.startswith("http"):
                        ext = _guess_extension(img_url)
                        filename = f"li_{item['id']}_{j}{ext}"
                        _download_media(img_url, filename)

                db_update_fn(item["id"], title, content, author)
                enriched += 1

        except Exception as e:
            logger.error(f"[enrich] LinkedIn Apify batch error: {e}")

        if progress_fn:
            progress_fn(min(batch_start + batch_size, len(to_enrich)), len(to_enrich))

        if (batch_start // batch_size + 1) % 10 == 0:
            logger.info(f"[enrich] LinkedIn progress: {min(batch_start + batch_size, len(to_enrich))}/{len(to_enrich)} ({enriched} enriched)")

        time.sleep(APIFY_DELAY)

    logger.info(f"[enrich] LinkedIn done: {enriched}/{len(to_enrich)} items enriched")
    return enriched
