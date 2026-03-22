"""Automatic topic categorization using a predefined taxonomy with keyword matching."""

import json
import logging
import re
from collections import defaultdict

logger = logging.getLogger("tousmeslikes")

# Predefined taxonomy: each category has keywords (matched case-insensitive)
TAXONOMY = {
    "IA & Machine Learning": [
        "ai", "artificial intelligence", "machine learning", "deep learning",
        "neural network", "llm", "gpt", "chatgpt", "openai", "anthropic", "claude",
        "gemini", "mistral", "llama", "transformer", "nlp", "ia", "intelligence artificielle",
        "apprentissage", "modèle de langage", "hugging face", "huggingface",
    ],
    "IA générative & Midjourney": [
        "midjourney", "stable diffusion", "dall-e", "dalle", "generative",
        "génératif", "générative", "text to image", "image generation",
        "diffusion model", "controlnet", "comfyui", "automatic1111",
        "runway", "gen-2", "sora", "flux", "prompt engineering", "prompting",
    ],
    "Cartographie & Géographie": [
        "map", "carte", "cartographie", "cartography", "geography", "géographie",
        "mapbox", "leaflet", "openstreetmap", "osm", "qgis", "gis", "sig",
        "30daymapchallenge", "dataviz map", "world map", "atlas",
        "géolocalisation", "geolocation", "coordinates", "satellite",
    ],
    "Développement & Code": [
        "code", "coding", "programming", "developer", "développeur",
        "javascript", "python", "typescript", "rust", "golang",
        "react", "vue", "svelte", "nextjs", "node", "api", "backend", "frontend",
        "git", "github", "gitlab", "devops", "docker", "kubernetes",
        "debug", "refactor", "algorithm", "algorithme", "framework",
    ],
    "Open Source": [
        "open source", "opensource", "foss", "libre", "logiciel libre",
        "apache", "mit license", "gpl", "contribut", "maintainer",
    ],
    "Data & Visualisation": [
        "data", "dataviz", "visualization", "visualisation", "dashboard",
        "d3js", "d3.js", "observable", "tableau", "chart", "graphique",
        "dataset", "données", "statistiques", "statistics", "analytics",
        "infographie", "infographic",
    ],
    "Art & Design": [
        "art", "artist", "artiste", "design", "designer", "creative",
        "créatif", "illustration", "graphic", "graphisme", "typography",
        "typographie", "esthétique", "aesthetic", "musée", "museum",
        "sculpture", "peinture", "painting", "gallery", "galerie",
        "interactive art", "digital art", "art numérique",
    ],
    "Photo & Vidéo": [
        "photo", "photography", "photographie", "photographe", "photographer",
        "vidéo", "video", "film", "cinéma", "cinema", "réalisateur",
        "camera", "caméra", "drone", "timelapse", "portrait",
        "documentaire", "documentary", "court métrage", "short film",
    ],
    "Impression 3D & Fabrication": [
        "3d print", "impression 3d", "3d printed", "printing",
        "maker", "fablab", "cnc", "laser cut", "arduino", "raspberry",
        "électronique", "electronics", "soudure", "prototype",
    ],
    "Jeux vidéo & Gaming": [
        "game", "gaming", "jeu vidéo", "jeux vidéo", "videogame",
        "nintendo", "playstation", "xbox", "steam", "indie game",
        "pixel art", "retro gaming", "rétrogaming", "gameplay",
        "unity", "unreal", "godot",
    ],
    "Transport & Mobilité": [
        "train", "sncf", "tgv", "métro", "metro", "transport",
        "mobilité", "mobility", "vélo", "bike", "cycling",
        "voiture", "car", "bus", "tramway", "aviation", "avion",
        "urbanisme", "urbanism", "ville", "city planning",
    ],
    "Paris & Île-de-France": [
        "paris", "parisien", "île-de-france", "idf",
        "montmartre", "marais", "bastille", "châtelet",
        "tour eiffel", "seine", "rer", "ratp",
    ],
    "France & Régions": [
        "france", "français", "française", "république",
        "bretagne", "normandie", "provence", "occitanie", "alsace",
        "lyon", "marseille", "bordeaux", "toulouse", "nantes", "lille",
    ],
    "Sport & JO": [
        "sport", "paris2024", "paris 2024", "olympics", "olympique",
        "jeux olympiques", "jo", "athlète", "athlete", "médaille",
        "football", "rugby", "tennis", "basketball", "natation",
        "marathon", "course", "compétition",
    ],
    "Science & Technologie": [
        "science", "scientific", "scientifique", "research", "recherche",
        "physics", "physique", "chemistry", "chimie", "biology", "biologie",
        "space", "espace", "nasa", "esa", "satellite", "astronomie",
        "quantum", "quantique", "robotique", "robotics", "innovation",
        "tech", "technology", "technologie",
    ],
    "Politique & Société": [
        "politique", "politics", "élection", "election", "vote",
        "gouvernement", "government", "président", "president",
        "démocratie", "democracy", "loi", "law", "justice",
        "social", "société", "society", "inégalité", "inequality",
        "féminisme", "feminism", "écologie", "ecology", "climat", "climate",
    ],
    "Culture & Histoire": [
        "histoire", "history", "historique", "historical",
        "culture", "culturel", "patrimoine", "heritage",
        "archéologie", "archaeology", "antiquité", "médiéval", "medieval",
        "livre", "book", "littérature", "literature", "auteur", "author",
        "philosophie", "philosophy",
    ],
    "Éducation & Apprentissage": [
        "éducation", "education", "apprendre", "learn", "learning",
        "cours", "course", "tutorial", "tutoriel", "formation",
        "école", "school", "université", "university", "étudiant", "student",
    ],
    "Musique & Audio": [
        "musique", "music", "album", "concert", "spotify",
        "musicien", "musician", "chanson", "song", "playlist",
        "synthétiseur", "synthesizer", "audio", "podcast",
    ],
    "Environnement & Climat": [
        "environnement", "environment", "climat", "climate",
        "réchauffement", "warming", "durable", "sustainable",
        "énergie", "energy", "renouvelable", "renewable",
        "biodiversité", "biodiversity", "pollution", "carbone", "carbon",
    ],
    "Web & Internet": [
        "website", "site web", "navigateur", "browser",
        "html", "css", "web design", "ux", "ui", "accessibilité",
        "accessibility", "seo", "wordpress", "cms",
        "fediverse", "mastodon", "bluesky", "réseau social", "social network",
    ],
}

# Compile keyword patterns for fast matching
_COMPILED_TAXONOMY: dict[str, list[re.Pattern]] = {}
for _cat, _keywords in TAXONOMY.items():
    _COMPILED_TAXONOMY[_cat] = [
        re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE)
        for kw in _keywords
    ]


def _clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[@#]", " ", text)
    return text.strip().lower()


def categorize_items(items: list[dict], **_kwargs) -> dict:
    """
    Categorize items using keyword-based taxonomy matching.
    Each item can belong to multiple categories.
    """
    if not items:
        return {"topics": [], "assignments": {}}

    logger.info(f"[categorize] Categorizing {len(items)} items with taxonomy ({len(TAXONOMY)} categories)")

    topic_counts = defaultdict(int)
    assignments = {}

    for item in items:
        text = _clean_text(f"{item.get('title', '')} {item.get('content', '')}")
        if len(text) < 5:
            continue

        matched_cats = []
        for cat, patterns in _COMPILED_TAXONOMY.items():
            score = sum(1 for p in patterns if p.search(text))
            if score >= 1:
                matched_cats.append((cat, score))

        # Sort by score descending, keep top 3
        matched_cats.sort(key=lambda x: x[1], reverse=True)
        labels = [cat for cat, _ in matched_cats[:3]]

        if labels:
            assignments[item["id"]] = labels
            for label in labels:
                topic_counts[label] += 1

    topics = sorted(
        [{"label": label, "count": count} for label, count in topic_counts.items()],
        key=lambda t: t["count"],
        reverse=True,
    )

    logger.info(f"[categorize] Found {len(topics)} categories, {len(assignments)} items categorized")
    return {"topics": topics, "assignments": assignments}
